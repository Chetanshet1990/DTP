from __future__ import annotations

import json
import math
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from dtp.cost_model import PRICE_GAP_THRESHOLD, calculate_should_cost
from dtp.drawing_extractor import extract_specs_from_text
from dtp.drawing_preview import (
    build_zoomable_preview_html,
    load_raster_image,
    pdf_page_count,
    render_pdf_page,
)
from dtp.drawing_review import (
    build_vertical_review_table,
    reviewed_specs_from_vertical_table,
)
from dtp.drawing_store import store_committed_drawing
from dtp.erp_pipeline import clean_erp_data
from dtp.market_data import get_market_adjustment
from dtp.ml_models import run_ai_pricing_models
from dtp.procurement_explain import build_procurement_explanations
from dtp.procurement_report import build_procurement_report


# REVIEW EXPLANATION:
# This is the Streamlit dashboard. It connects all backend modules:
# data upload -> market data -> should-cost -> ML fair price -> anomaly/XAI
# outputs -> portfolio and part-level review screens.

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
BASE_PARTS_PATH = DATA_DIR / "sample_parts.csv"
ACTIVE_PARTS_PATH = DATA_DIR / "processed" / "active_parts_master.csv"
DRAWINGS_DIR = DATA_DIR / "drawings"
APP_HOME_URL = "./"
USD_TO_INR = 83.0


st.set_page_config(
    page_title="Digital Twin Pricing",
    page_icon="DTP",
    layout="wide",
)


REQUIRED_PART_COLUMNS = [
    # Uploaded part datasets must contain these engineering and commercial fields.
    # In the thesis story these come from drawing/OCR or engineering master data.
    "part_id",
    "part_name",
    "category",
    "material",
    "material_grade",
    "thickness_mm",
    "length_mm",
    "width_mm",
    "weight_kg",
    "bend_count",
    "hole_count",
    "surface_finish",
    "finish_cost_per_part",
    "material_rate_per_kg",
    "cycle_time_min",
    "energy_kwh_per_part",
    "energy_rate_per_kwh",
    "labour_hours",
    "labour_rate_per_hour",
    "overhead_pct",
    "supplier_margin_pct",
    "current_supplier",
    "supplier_region",
    "erp_price",
    "annual_volume",
]

DRAWING_SPEC_COLUMNS = [
    "category",
    "material",
    "material_grade",
    "thickness_mm",
    "length_mm",
    "width_mm",
    "weight_kg",
    "bend_count",
    "hole_count",
    "surface_finish",
]


def load_csv(name: str) -> pd.DataFrame:
    """Load one default demo CSV from the data folder."""
    return pd.read_csv(DATA_DIR / name)


def read_parts(uploaded_file) -> pd.DataFrame:
    """Read the sheet-metal part master used by cost twin and ML models."""
    if uploaded_file is None:
        source = ACTIVE_PARTS_PATH if ACTIVE_PARTS_PATH.exists() else BASE_PARTS_PATH
        return pd.read_csv(source)

    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(uploaded_file)
    return pd.read_csv(uploaded_file)


def initialize_parts_database(parts: pd.DataFrame) -> pd.DataFrame:
    """Keep the active engineering master in Streamlit session state."""
    if "parts_database" not in st.session_state:
        st.session_state["parts_database"] = parts.copy()
        st.session_state["drawing_update_log"] = []
    return st.session_state["parts_database"].copy()


def reset_drawing_upload_widget() -> None:
    """Create a fresh uploader whenever the user changes the target part."""
    st.session_state["drawing_upload_generation"] = (
        st.session_state.get("drawing_upload_generation", 0) + 1
    )


def save_active_parts_database(parts: pd.DataFrame) -> None:
    """Persist the reviewed active part master with an atomic file replacement."""
    ACTIVE_PARTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = ACTIVE_PARTS_PATH.with_suffix(".tmp")
    parts.to_csv(temporary_path, index=False)
    temporary_path.replace(ACTIVE_PARTS_PATH)


def missing_drawing_specs(parts: pd.DataFrame) -> pd.Series:
    """Count missing drawing-derived specs for each part."""
    return parts[DRAWING_SPEC_COLUMNS].apply(
        lambda row: sum(pd.isna(value) or str(value).strip() == "" for value in row),
        axis=1,
    )


def validate_drawing_review(reviewed_row: pd.Series) -> list[str]:
    """Validate one reviewed drawing row before it can replace active data."""
    errors = []
    missing = [
        column
        for column in DRAWING_SPEC_COLUMNS
        if pd.isna(reviewed_row.get(column)) or str(reviewed_row.get(column)).strip() == ""
    ]
    if missing:
        errors.append("Missing required drawing fields: " + ", ".join(missing))

    positive_fields = ["thickness_mm", "length_mm", "width_mm", "weight_kg"]
    count_fields = ["bend_count", "hole_count"]
    for column in positive_fields:
        value = pd.to_numeric(pd.Series([reviewed_row.get(column)]), errors="coerce").iloc[0]
        if pd.isna(value) or float(value) <= 0:
            errors.append(f"{column} must be greater than zero.")
    for column in count_fields:
        value = pd.to_numeric(pd.Series([reviewed_row.get(column)]), errors="coerce").iloc[0]
        if pd.isna(value) or float(value) < 0 or not float(value).is_integer():
            errors.append(f"{column} must be a non-negative whole number.")
    return errors


def apply_drawing_specs_to_part(
    parts: pd.DataFrame,
    part_id: str,
    specs: dict[str, object],
    file_name: str,
    confidence: str,
) -> pd.DataFrame:
    """Update one part row with extracted drawing specifications."""
    updated = parts.copy()
    mask = updated["part_id"].astype(str) == str(part_id)
    if not mask.any():
        return updated

    for column in DRAWING_SPEC_COLUMNS:
        if column in specs:
            updated.loc[mask, column] = specs[column]

    updated.loc[mask, "drawing_source_file"] = file_name
    updated.loc[mask, "drawing_extraction_confidence"] = confidence
    updated.loc[mask, "engineering_data_source"] = "Uploaded drawing"
    updated.loc[mask, "engineering_status"] = "Committed"
    updated.loc[mask, "prediction_status"] = "Ready"
    return updated


def read_erp_transactions(uploaded_file) -> pd.DataFrame:
    """Read raw ERP data and immediately pass it through the cleaning pipeline."""
    if uploaded_file is None:
        raw_erp = load_csv("erp_raw_sample.csv")
    else:
        suffix = Path(uploaded_file.name).suffix.lower()
        if suffix in {".xlsx", ".xls"}:
            raw_erp = pd.read_excel(uploaded_file)
        else:
            raw_erp = pd.read_csv(uploaded_file)
    return clean_erp_data(raw_erp).cleaned_data


def extract_uploaded_drawing_text(uploaded_file) -> str:
    """Extract text from uploaded drawing files for specification parsing."""
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(uploaded_file)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            return ""
    if suffix in {".txt", ".dxf"}:
        return uploaded_file.getvalue().decode("utf-8", errors="ignore")
    return ""


@st.cache_data(ttl=60 * 60)
def load_market_adjustment():
    """Cache live market calls for one hour so the dashboard stays responsive."""
    return get_market_adjustment()


def validate_parts(parts: pd.DataFrame) -> list[str]:
    """Validate uploaded part master before running cost and ML calculations."""
    missing = [column for column in REQUIRED_PART_COLUMNS if column not in parts.columns]
    if missing:
        return [f"Missing required columns: {', '.join(missing)}"]

    errors = []
    numeric_columns = [
        "weight_kg",
        "thickness_mm",
        "length_mm",
        "width_mm",
        "bend_count",
        "hole_count",
        "finish_cost_per_part",
        "material_rate_per_kg",
        "cycle_time_min",
        "energy_kwh_per_part",
        "energy_rate_per_kwh",
        "labour_hours",
        "labour_rate_per_hour",
        "overhead_pct",
        "supplier_margin_pct",
        "erp_price",
        "annual_volume",
    ]
    for column in numeric_columns:
        source = parts[column]
        numeric = pd.to_numeric(source, errors="coerce")
        blank = source.isna() | source.astype(str).str.strip().eq("")
        if ((~blank) & numeric.isna()).any():
            errors.append(f"Column '{column}' contains non-numeric values.")
        if column not in DRAWING_SPEC_COLUMNS and numeric.isna().any():
            errors.append(f"Column '{column}' contains missing numeric values.")
    return errors


def explain_price_flags(priced_parts: pd.DataFrame) -> pd.DataFrame:
    """Create simple procurement-language explanations for should-cost gaps."""
    rows = []
    driver_columns = {
        "Material": "material_cost",
        "Energy": "energy_cost",
        "Labour": "labour_cost",
        "Bends and holes": "process_complexity_cost",
        "Surface finish": "surface_finish_cost",
        "Overhead": "overhead",
        "Manual template adjustments": "manual_template_adjustment_cost",
        "Supplier margin": "supplier_margin",
    }
    for _, part in priced_parts.iterrows():
        drivers = {
            label: part[column]
            for label, column in driver_columns.items()
        }
        top_driver = max(drivers, key=drivers.get)
        reasons = [
            f"Top cost driver: {top_driver}",
            f"{int(part['bend_count'])} bends",
            f"{int(part['hole_count'])} holes",
            f"{part['surface_finish']} finish",
        ]
        if part["price_gap_pct"] > PRICE_GAP_THRESHOLD:
            reasons.insert(0, f"ERP price is {percent(part['price_gap_pct'])} above should-cost")
        else:
            reasons.insert(0, "Within review threshold")
        rows.append(
            {
                "part_id": part["part_id"],
                "part_name": part["part_name"],
                "category": part["category"],
                "gap_status": part["gap_status"],
                "price_gap_pct": part["price_gap_pct"],
                "top_cost_driver": top_driver,
                "explanation": "; ".join(reasons),
            }
        )
    return pd.DataFrame(rows)


def get_selected_part_id(priced_parts: pd.DataFrame) -> str:
    """Read selected part_id from the URL query string."""
    part_id = st.query_params.get("part_id")
    if isinstance(part_id, list):
        part_id = part_id[0] if part_id else None
    if part_id in set(priced_parts["part_id"]):
        return str(part_id)
    return str(priced_parts["part_id"].iloc[0])


def get_app_view() -> str:
    """Switch between portfolio page and part-detail page using URL state."""
    view = st.query_params.get("view")
    if isinstance(view, list):
        view = view[0] if view else None
    return "detail" if view == "detail" else "portfolio"


def add_part_links(priced_parts: pd.DataFrame) -> pd.DataFrame:
    """Turn part IDs and gap status into clickable links for the detail page."""
    linked = priced_parts.copy()
    linked["part_id"] = linked["part_id"].map(
        lambda value: f"./?view=detail&part_id={quote(str(value))}"
    )
    linked["gap_status"] = priced_parts.apply(
        lambda row: (
            f"./?view=detail&part_id={quote(str(row['part_id']))}"
            f"&gap_status={quote(str(row['gap_status']))}"
        ),
        axis=1,
    )
    return linked


def cost_breakdown_percent(selected_part: pd.Series) -> pd.DataFrame:
    """Convert cost buckets into percentage share for the stacked chart."""
    rows = pd.DataFrame(
        {
            "cost_bucket": [
                "Supplier Margin",
                "Manual Template Adjustments",
                "Overhead",
                "Surface Finish",
                "Bends and Holes",
                "Energy",
                "Labour",
                "Steel",
            ],
            "amount": [
                selected_part["supplier_margin"],
                selected_part["manual_template_adjustment_cost"],
                selected_part["overhead"],
                selected_part["surface_finish_cost"],
                selected_part["process_complexity_cost"],
                selected_part["energy_cost"],
                selected_part["labour_cost"],
                selected_part["material_cost"],
            ],
        }
    )
    rows["share_pct"] = rows["amount"] / rows["amount"].sum() * 100
    return rows


def monthly_erp_price_history(selected_part: pd.Series, erp_transactions: pd.DataFrame) -> pd.DataFrame:
    """Build monthly ERP price history for the selected part."""
    today = pd.Timestamp.today().normalize()
    if erp_transactions.empty or "part_id" not in erp_transactions.columns:
        months = pd.date_range(today - pd.DateOffset(months=35), today, freq="MS")
        return pd.DataFrame(
            {
                "date": months,
                "erp_monthly_price": [
                    float(selected_part["erp_price"]) * (0.92 + index / max(len(months) - 1, 1) * 0.10)
                    for index in range(len(months))
                ],
                "erp_data_source": "Generated - ERP data unavailable",
            }
        )

    part_erp = erp_transactions[erp_transactions["part_id"] == selected_part["part_id"]].copy()
    if part_erp.empty:
        # Demo fallback: if the real ERP file has no matching part history,
        # generate a labelled illustrative trend so the chart still works.
        months = pd.date_range(today - pd.DateOffset(months=35), today, freq="MS")
        return pd.DataFrame(
            {
                "date": months,
                "erp_monthly_price": [
                    float(selected_part["erp_price"]) * (0.92 + index / max(len(months) - 1, 1) * 0.10)
                    for index in range(len(months))
                ],
                "erp_data_source": "Generated - no ERP history",
            }
        )

    part_erp["date"] = pd.to_datetime(part_erp["po_date"]).dt.to_period("M").dt.to_timestamp()
    part_erp["erp_monthly_price"] = part_erp["unit_price_usd"] * USD_TO_INR
    actual_monthly = (
        part_erp.groupby("date", as_index=False)
        .agg(erp_monthly_price=("erp_monthly_price", "mean"))
        .sort_values("date")
    )
    months = pd.date_range(actual_monthly["date"].min(), today, freq="MS")
    monthly = pd.DataFrame({"date": months}).merge(actual_monthly, on="date", how="left")
    monthly["erp_data_source"] = monthly["erp_monthly_price"].apply(
        lambda value: "Actual ERP" if pd.notna(value) else "Generated - interpolated"
    )
    monthly["erp_monthly_price"] = (
        monthly["erp_monthly_price"]
        .interpolate(method="linear")
        .bfill()
        .ffill()
        .fillna(float(selected_part["erp_price"]))
    )
    return monthly


def daily_ml_fair_price_history(selected_part: pd.Series, start_date: pd.Timestamp) -> pd.DataFrame:
    """Generate a daily ML fair-price trend from the current model prediction."""
    today = pd.Timestamp.today().normalize()
    dates = pd.date_range(start_date, today, freq="D")
    base_prediction = float(
        selected_part.get("ai_predicted_fair_price", selected_part["should_cost"])
    )
    day_index = pd.Series(range(len(dates)), dtype=float)
    progress = day_index / max(len(dates) - 1, 1)
    market_signal = (
        0.95
        + 0.06 * progress
        + 0.012 * (day_index / 29).apply(math.sin)
        + 0.006 * (day_index / 13).apply(math.cos)
    )
    market_signal = market_signal / market_signal.iloc[-1]
    return pd.DataFrame(
        {
            "date": dates,
            "ml_predicted_fair_price": base_prediction * market_signal,
            "linear_regression_fair_price": float(selected_part["linear_regression_fair_price"]) * market_signal,
            "random_forest_fair_price": float(selected_part["random_forest_fair_price"]) * market_signal,
            "xgboost_fair_price": float(selected_part["xgboost_fair_price"]) * market_signal,
        }
    )


def price_development_history(selected_part: pd.Series, erp_transactions: pd.DataFrame) -> pd.DataFrame:
    """Join monthly ERP price and daily ML fair price into one trend table."""
    monthly_erp = monthly_erp_price_history(selected_part, erp_transactions)
    daily_fair = daily_ml_fair_price_history(selected_part, monthly_erp["date"].min())
    history = daily_fair.merge(monthly_erp, on="date", how="left")
    history["erp_monthly_price"] = history["erp_monthly_price"].ffill()
    history["erp_data_source"] = history["erp_data_source"].fillna("Carried from latest monthly ERP")
    history["ml_price_gap"] = history["erp_monthly_price"] - history["ml_predicted_fair_price"]
    history["ml_price_gap_pct"] = history["ml_price_gap"] / history["ml_predicted_fair_price"] * 100
    return history


def render_committed_drawing_preview(selected_part: pd.Series) -> None:
    """Show the committed drawing for a part when a stored file is available."""
    stored_path = selected_part.get("drawing_stored_path")
    if pd.isna(stored_path) or not str(stored_path).strip():
        return

    drawing_path = Path(str(stored_path))
    if not drawing_path.is_absolute():
        drawing_path = BASE_DIR / drawing_path
    drawing_path = drawing_path.resolve()
    project_root = BASE_DIR.resolve()
    if project_root not in drawing_path.parents or not drawing_path.is_file():
        st.warning("The drawing is recorded for this part, but its stored file is unavailable.")
        return

    st.markdown("#### Engineering drawing preview")
    drawing_content = drawing_path.read_bytes()
    drawing_suffix = drawing_path.suffix.lower()
    source_name = selected_part.get("drawing_source_file")
    drawing_name = (
        Path(str(source_name)).name
        if pd.notna(source_name) and str(source_name).strip()
        else drawing_path.name
    )
    part_id = str(selected_part["part_id"])

    try:
        if drawing_suffix == ".pdf":
            page_count = pdf_page_count(drawing_content)
            preview_page = 1
            if page_count > 1:
                preview_page = st.number_input(
                    "Drawing preview page",
                    min_value=1,
                    max_value=page_count,
                    value=1,
                    step=1,
                    key=f"detail_drawing_page_{part_id}",
                )
            preview_image = render_pdf_page(
                drawing_content,
                page_number=int(preview_page),
                scale=1.5,
            )
            components.html(
                build_zoomable_preview_html(
                    preview_image,
                    f"{drawing_name} — page {preview_page} of {page_count}",
                ),
                height=700,
                scrolling=False,
            )
        elif drawing_suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
            components.html(
                build_zoomable_preview_html(
                    load_raster_image(drawing_content),
                    drawing_name,
                ),
                height=700,
                scrolling=False,
            )
        else:
            st.info("An inline preview is unavailable for this drawing format.")
    except Exception as exc:
        st.warning(f"Drawing preview is unavailable: {exc}")

    mime_type = "application/pdf" if drawing_suffix == ".pdf" else "application/octet-stream"
    st.download_button(
        "Download engineering drawing",
        data=drawing_content,
        file_name=drawing_name,
        mime=mime_type,
        key=f"detail_drawing_download_{part_id}",
    )


def render_part_detail(
    selected_part: pd.Series,
    priced_parts: pd.DataFrame,
    erp_transactions: pd.DataFrame,
) -> None:
    """Render the part-level drill-down digital twin page."""
    st.markdown(f"[Back to portfolio]({APP_HOME_URL})")
    st.subheader(f"Illustrative direct spend digital twin analysis: {selected_part['part_id']}")
    st.caption(
        f"{selected_part['part_name']} | {selected_part['material_grade']} | "
        f"{selected_part['current_supplier']} | {selected_part['gap_status']}"
    )

    part_ids = priced_parts["part_id"].tolist()
    selected_part_id = st.selectbox(
        "Switch part",
        part_ids,
        index=part_ids.index(selected_part["part_id"]),
    )
    if selected_part_id != selected_part["part_id"]:
        st.query_params["view"] = "detail"
        st.query_params["part_id"] = selected_part_id
        st.rerun()

    detail_kpis = st.columns(4)
    detail_kpis[0].metric("ERP price", money(selected_part["erp_price"]))
    detail_kpis[1].metric("ML fair price", money(selected_part["ai_predicted_fair_price"]))
    detail_kpis[2].metric("ML price gap", percent(selected_part["ai_price_gap_pct"]))
    detail_kpis[3].metric("ML qualified savings", money(selected_part["ai_savings_opportunity"]))
    st.caption(
        "This page compares month-on-month ERP purchase prices with daily ML-predicted fair prices. "
        "Missing ERP months are generated by interpolation and labelled in the table."
    )

    breakdown_pct = cost_breakdown_percent(selected_part)
    price_history = price_development_history(selected_part, erp_transactions)
    left_col, right_col = st.columns([1, 2.2])

    with left_col:
        fig = go.Figure()
        colors = [
            "#0b73b7",
            "#12a889",
            "#2a64f6",
            "#50d6d3",
            "#65e4e6",
            "#00a7d7",
            "#122a8f",
            "#6b8f23",
        ]
        for index, row in breakdown_pct.iterrows():
            fig.add_trace(
                go.Bar(
                    x=["Cost breakdown, %"],
                    y=[row["share_pct"]],
                    name=row["cost_bucket"],
                    marker_color=colors[index % len(colors)],
                    text=[f"{row['share_pct']:.0f}"],
                    textposition="inside",
                    hovertemplate="%{fullData.name}: %{y:.1f}%<extra></extra>",
                )
            )
        fig.update_layout(
            title="Cost breakdown, %",
            barmode="stack",
            height=430,
            margin={"l": 8, "r": 8, "t": 40, "b": 20},
            yaxis={"range": [0, 100], "ticksuffix": "%", "showgrid": False},
            xaxis={"showticklabels": False},
            legend={"orientation": "h", "y": -0.12},
        )
        st.plotly_chart(fig, use_container_width=True)

    with right_col:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=price_history["date"],
                y=price_history["ml_predicted_fair_price"],
                mode="lines",
                name="Daily ML fair price",
                line={"color": "#12a889", "width": 2},
                hovertemplate="%{x|%Y-%m-%d}<br>ML fair price: ₹%{y:,.0f}<extra></extra>",
            )
        )
        erp_monthly_points = price_history[price_history["date"].dt.is_month_start]
        fig.add_trace(
            go.Scatter(
                x=erp_monthly_points["date"],
                y=erp_monthly_points["erp_monthly_price"],
                mode="lines+markers",
                name="Monthly ERP price",
                line={"shape": "hv", "color": "#3f5ea8", "width": 2},
                marker={"size": 7},
                hovertemplate="%{x|%Y-%m}<br>ERP price: ₹%{y:,.0f}<extra></extra>",
            )
        )
        fig.update_layout(
            title="Monthly ERP price vs daily ML-predicted fair price",
            height=430,
            margin={"l": 10, "r": 10, "t": 55, "b": 20},
            yaxis_title="Price, INR per part",
            xaxis_title=None,
            legend={"orientation": "h", "y": -0.18},
        )
        st.plotly_chart(fig, use_container_width=True)

    st.caption("Daily ML fair-price table with monthly ERP price reference")
    table_view = price_history[
        [
            "date",
            "erp_monthly_price",
            "erp_data_source",
            "ml_predicted_fair_price",
            "linear_regression_fair_price",
            "random_forest_fair_price",
            "xgboost_fair_price",
            "ml_price_gap_pct",
        ]
    ].tail(120)
    st.dataframe(
        table_view.style.format(
            {
                "date": lambda value: value.strftime("%Y-%m-%d"),
                "erp_monthly_price": "₹{:,.0f}",
                "ml_predicted_fair_price": "₹{:,.0f}",
                "linear_regression_fair_price": "₹{:,.0f}",
                "random_forest_fair_price": "₹{:,.0f}",
                "xgboost_fair_price": "₹{:,.0f}",
                "ml_price_gap_pct": "{:,.1f}%",
            }
        ),
        width="stretch",
        hide_index=True,
    )

    st.caption("Drawing-derived cost twin inputs")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "part_id": selected_part["part_id"],
                    "material_grade": selected_part["material_grade"],
                    "thickness_mm": selected_part["thickness_mm"],
                    "blank_area_m2": selected_part["blank_area_m2"],
                    "weight_kg": selected_part["weight_kg"],
                    "material_cost": selected_part["material_cost"],
                    "bend_count": selected_part["bend_count"],
                    "hole_count": selected_part["hole_count"],
                    "surface_finish": selected_part["surface_finish"],
                }
            ]
        ).style.format(
            {
                "thickness_mm": "{:,.1f}",
                "blank_area_m2": "{:,.3f}",
                "weight_kg": "{:,.2f}",
                "material_cost": "₹{:,.0f}",
            }
        ),
        width="stretch",
        hide_index=True,
    )
    render_committed_drawing_preview(selected_part)

    with st.expander("How predicted fair price is calculated"):
        st.write(
            "Predicted fair price is the should-cost estimate built from material, energy, "
            "labour, machine operations, surface finish, overhead, and minimum supplier margin."
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "driver": "Steel material",
                        "logic": "weight kg x live-market-adjusted steel rate x grade factor x thickness factor",
                        "value": money(selected_part["material_cost"]),
                    },
                    {
                        "driver": "Energy",
                        "logic": "part energy kWh x predicted energy tariff for supplier COO",
                        "value": money(selected_part["energy_cost"]),
                    },
                    {
                        "driver": "Labour",
                        "logic": "labour hours x predicted labour rate for supplier COO",
                        "value": money(selected_part["labour_cost"]),
                    },
                    {
                        "driver": "Bends and holes",
                        "logic": "operation minutes x machine hour rate for supplier COO",
                        "value": money(selected_part["process_complexity_cost"]),
                    },
                    {
                        "driver": "Surface finish",
                        "logic": "blank area x finish-specific rate per square meter",
                        "value": money(selected_part["surface_finish_cost"]),
                    },
                    {
                        "driver": "Overhead",
                        "logic": "regional overhead applied to conversion cost",
                        "value": money(selected_part["overhead"]),
                    },
                    {
                        "driver": "Manual template adjustments",
                        "logic": "rejection allowance, tool maintenance, packing/forwarding, and optional tooling amortization",
                        "value": money(selected_part["manual_template_adjustment_cost"]),
                    },
                    {
                        "driver": "Supplier margin",
                        "logic": "minimum industry margin for the part category",
                        "value": money(selected_part["supplier_margin"]),
                    },
                ]
            ),
            width="stretch",
            hide_index=True,
        )
        st.caption(
            f"COO: {selected_part['supplier_region']}; "
            f"energy rate: {money(selected_part['predicted_energy_rate_per_kwh'])}/kWh; "
            f"labour rate: {money(selected_part['predicted_labour_rate_per_hour'])}/hour; "
            f"machine rate: {money(selected_part['machine_rate_per_hour'])}/hour; "
            f"minimum margin: {percent(selected_part['predicted_supplier_margin_pct'])}."
        )


def geo_cost_comparison(selected_part: pd.Series, geo_indices: pd.DataFrame) -> pd.DataFrame:
    """Compare landed should-cost if the same part is sourced from regions."""
    rows = []
    for _, region in geo_indices.iterrows():
        material_cost = (
            selected_part["material_cost"] * region["material_index"]
        )
        energy_cost = selected_part["energy_cost"] * region["energy_index"]
        labour_cost = selected_part["labour_cost"] * region["labour_index"]
        process_complexity_cost = selected_part["process_complexity_cost"]
        surface_finish_cost = selected_part["surface_finish_cost"]
        overhead = (
            (energy_cost + labour_cost + process_complexity_cost + surface_finish_cost)
            * selected_part["predicted_overhead_pct"]
            / 100
            * region["overhead_index"]
        )
        base_cost = (
            material_cost
            + energy_cost
            + labour_cost
            + process_complexity_cost
            + surface_finish_cost
            + overhead
        )
        margin = base_cost * selected_part["predicted_supplier_margin_pct"] / 100
        logistics = (base_cost + margin) * region["logistics_pct"] / 100
        rows.append(
            {
                "region": region["region"],
                "material_cost": material_cost,
                "energy_cost": energy_cost,
                "labour_cost": labour_cost,
                "process_complexity_cost": process_complexity_cost,
                "surface_finish_cost": surface_finish_cost,
                "overhead": overhead,
                "supplier_margin": margin,
                "logistics": logistics,
                "landed_should_cost": base_cost + margin + logistics,
            }
        )
    return pd.DataFrame(rows).sort_values("landed_should_cost")


def money(value: float) -> str:
    """Format INR values for display."""
    return f"₹{value:,.0f}"


def compact_money(value: float) -> str:
    """Format large INR portfolio values using Indian number units."""
    absolute_value = abs(value)
    if absolute_value >= 10_000_000:
        scaled_value, unit = value / 10_000_000, "Crore"
    elif absolute_value >= 100_000:
        scaled_value, unit = value / 100_000, "Lakh"
    elif absolute_value >= 1_000:
        scaled_value, unit = value / 1_000, "Thousand"
    else:
        return money(value)

    formatted_value = f"{scaled_value:,.2f}".rstrip("0").rstrip(".")
    return f"₹{formatted_value} {unit}"


def percent(value: float) -> str:
    """Format percentages for display."""
    return f"{value:,.1f}%"


@st.cache_data(show_spinner=False)
def cached_procurement_report(
    explanation_data: dict[str, object],
    part_data: dict[str, object],
) -> bytes:
    """Cache generated PDF bytes for the selected procurement line item."""
    return build_procurement_report(explanation_data, part_data)


# MAIN APP EXECUTION STARTS HERE.
# Explain this as: load inputs, run backend models, then render tabs.
st.title("Sheet Metal Cost Digital Twin")
st.caption("Explainable procurement intelligence for sheet metal sourcing")

market_adjustment = load_market_adjustment()

with st.sidebar:
    st.header("Live Market Inputs")
    st.metric(
        "Steel index",
        f"{market_adjustment.steel_index:,.1f}",
        help="FRED WPU101 Producer Price Index for Iron and Steel.",
    )
    st.metric(
        "USD/INR FX",
        f"{market_adjustment.usd_inr:,.2f}",
        help="Latest USD to INR exchange rate from Frankfurter.",
    )
    st.metric(
        "Material rate factor",
        f"{market_adjustment.material_rate_factor:,.3f}x",
        help="Steel index factor multiplied by FX factor.",
    )
    st.caption(
        f"Source: {market_adjustment.source_status}; "
        f"steel date: {market_adjustment.steel_index_date}; "
        f"FX date: {market_adjustment.fx_date}."
    )
    if market_adjustment.source_status != "live":
        st.warning("Live API unavailable; baseline market inputs are being used.")

uploaded_file = None
erp_file = None

initial_parts = read_parts(uploaded_file)
initial_errors = validate_parts(initial_parts)
if initial_errors:
    for error in initial_errors:
        st.error(error)
    st.stop()

parts_raw = initialize_parts_database(initial_parts)

WORKSPACE_VIEWS = [
    "Portfolio",
    "Upload Drawing",
    "AI Models",
    "ERP Intelligence",
    "Cost Drivers",
    "Explainability",
    "Supplier Benchmark",
    "Geo Cost",
]
requested_report_part_id = st.query_params.get("report_part_id")
if isinstance(requested_report_part_id, list):
    requested_report_part_id = requested_report_part_id[0] if requested_report_part_id else None
requested_report_part_id = str(requested_report_part_id) if requested_report_part_id else None
default_workspace = "Explainability" if requested_report_part_id else "Portfolio"
active_workspace = st.radio(
    "Workspace view",
    WORKSPACE_VIEWS,
    index=WORKSPACE_VIEWS.index(default_workspace),
    horizontal=True,
    key="active_workspace",
    label_visibility="collapsed",
)

if active_workspace == "Upload Drawing":
    st.subheader("Upload Drawing")
    commit_message = st.session_state.pop("drawing_commit_message", None)
    if commit_message:
        st.success(commit_message)

    missing_counts = missing_drawing_specs(parts_raw)
    part_options = parts_raw["part_id"].astype(str).tolist()
    if "drawing_upload_generation" not in st.session_state:
        st.session_state["drawing_upload_generation"] = 0
    selected_upload_part = st.selectbox(
        "Select part number",
        part_options,
        format_func=lambda part_id: (
            f"{part_id} - {int(missing_counts.loc[parts_raw['part_id'].astype(str) == part_id].iloc[0])} missing drawing fields"
        ),
        help="Choose the ERP/part-master record that should receive the extracted drawing specifications.",
        key="selected_upload_part",
        on_change=reset_drawing_upload_widget,
    )
    selected_upload_row = parts_raw.loc[
        parts_raw["part_id"].astype(str) == selected_upload_part
    ].iloc[0]
    st.caption("Current technical specifications for selected part")
    st.dataframe(
        pd.DataFrame([selected_upload_row[["part_id", "part_name"] + DRAWING_SPEC_COLUMNS]]),
        width="stretch",
        hide_index=True,
    )

    drawing_files = st.file_uploader(
        "Upload technical drawing",
        type=["pdf", "png", "jpg", "jpeg", "tif", "tiff", "dxf", "dwg"],
        accept_multiple_files=False,
        help="Use drawings when engineering specifications are missing from the dataset.",
        key=(
            f"drawing_upload_{selected_upload_part}_"
            f"{st.session_state['drawing_upload_generation']}"
        ),
    )
    if drawing_files:
        text = extract_uploaded_drawing_text(drawing_files)
        extraction_result = extract_specs_from_text(text, file_name=drawing_files.name)

        if not text.strip():
            st.warning(
                "No readable text was extracted. Text-based PDFs and DXF/TXT files can be parsed in this prototype; "
                "scanned images need an OCR layer before technical fields can be fetched automatically."
            )

        st.success("Drawing processed for technical specification review.")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "part_id": selected_upload_part,
                        "file_name": drawing_files.name,
                        "file_type": Path(drawing_files.name).suffix.lower().lstrip("."),
                        "size_kb": drawing_files.size / 1024,
                        "extraction_confidence": extraction_result.confidence,
                    }
                ]
            ).style.format({"size_kb": "{:,.1f}"}),
            width="stretch",
            hide_index=True,
        )
        candidate_row = selected_upload_row.copy()
        for column, value in extraction_result.extracted_specs.items():
            if column in DRAWING_SPEC_COLUMNS:
                candidate_row[column] = value

        preview_column, review_column = st.columns([1.35, 1], vertical_alignment="top")
        with preview_column:
            st.caption("Drawing preview")
            drawing_suffix = Path(drawing_files.name).suffix.lower()
            if drawing_suffix == ".pdf":
                try:
                    pdf_bytes = drawing_files.getvalue()
                    page_count = pdf_page_count(pdf_bytes)
                    preview_page = 1
                    if page_count > 1:
                        preview_page = st.number_input(
                            "Preview page",
                            min_value=1,
                            max_value=page_count,
                            value=1,
                            step=1,
                            key=f"preview_page_{selected_upload_part}_{drawing_files.name}",
                        )
                    preview_image = render_pdf_page(
                        pdf_bytes,
                        page_number=int(preview_page),
                        scale=1.5,
                    )
                    components.html(
                        build_zoomable_preview_html(
                            preview_image,
                            f"{drawing_files.name} — page {preview_page} of {page_count}",
                        ),
                        height=700,
                        scrolling=False,
                    )
                except Exception as exc:
                    st.warning(f"PDF preview is unavailable: {exc}")
                    st.download_button(
                        "Open or download uploaded drawing",
                        data=drawing_files.getvalue(),
                        file_name=drawing_files.name,
                        mime="application/pdf",
                    )
            elif drawing_suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
                components.html(
                    build_zoomable_preview_html(
                        load_raster_image(drawing_files.getvalue()),
                        drawing_files.name,
                    ),
                    height=700,
                    scrolling=False,
                )
            else:
                st.info("Inline preview is available for PDF and image drawings.")

        with review_column:
            st.caption("Review and edit the extracted specifications before committing")
            reviewed_frame = st.data_editor(
                build_vertical_review_table(candidate_row, DRAWING_SPEC_COLUMNS),
                width="stretch",
                hide_index=True,
                num_rows="fixed",
                disabled=["Parameter"],
                height=455,
                column_config={
                    "Parameter": st.column_config.TextColumn("Parameter", width="medium"),
                    "Reviewed value": st.column_config.TextColumn(
                        "Reviewed value",
                        width="medium",
                    ),
                },
                key=f"drawing_review_vertical_{selected_upload_part}_{drawing_files.name}",
            )
        raw_reviewed_specs = reviewed_specs_from_vertical_table(
            reviewed_frame,
            DRAWING_SPEC_COLUMNS,
        )
        reviewed_row = pd.Series(raw_reviewed_specs)
        review_errors = validate_drawing_review(reviewed_row)
        if review_errors:
            st.warning(
                "Review required: " + " ".join(review_errors)
            )

        if st.button(
            "Commit reviewed data and rerun ML pipeline",
            type="primary",
            disabled=bool(review_errors),
        ):
            reviewed_specs = reviewed_specs_from_vertical_table(
                reviewed_frame,
                DRAWING_SPEC_COLUMNS,
                normalize=True,
            )
            candidate_parts = apply_drawing_specs_to_part(
                st.session_state["parts_database"],
                selected_upload_part,
                reviewed_specs,
                drawing_files.name,
                extraction_result.confidence,
            )
            stored_drawing = None
            try:
                candidate_errors = validate_parts(candidate_parts)
                if candidate_errors:
                    raise ValueError(" ".join(candidate_errors))

                candidate_ready = candidate_parts.loc[
                    missing_drawing_specs(candidate_parts).eq(0)
                ].copy()
                candidate_priced = calculate_should_cost(
                    candidate_ready,
                    material_rate_factor=market_adjustment.material_rate_factor,
                )
                run_ai_pricing_models(
                    candidate_priced,
                    commodity_index=market_adjustment.steel_index,
                    fx_rate=market_adjustment.usd_inr,
                    market_source_status=market_adjustment.source_status,
                )
                stored_drawing = store_committed_drawing(
                    content=drawing_files.getvalue(),
                    original_file_name=drawing_files.name,
                    part_id=selected_upload_part,
                    drawings_directory=DRAWINGS_DIR,
                    project_root=BASE_DIR,
                )
                selected_mask = candidate_parts["part_id"].astype(str).eq(selected_upload_part)
                candidate_parts.loc[
                    selected_mask, "drawing_stored_path"
                ] = stored_drawing.relative_path
                candidate_parts.loc[
                    selected_mask, "drawing_sha256"
                ] = stored_drawing.sha256
                candidate_parts.loc[
                    selected_mask, "drawing_committed_at_utc"
                ] = stored_drawing.committed_at_utc
                save_active_parts_database(candidate_parts)
            except Exception as exc:
                if stored_drawing is not None:
                    stored_drawing.absolute_path.unlink(missing_ok=True)
                st.error(f"Commit cancelled; the active database was not changed. {exc}")
            else:
                st.session_state["parts_database"] = candidate_parts
                st.session_state["drawing_update_log"].append(
                    {
                        "part_id": selected_upload_part,
                        "file_name": drawing_files.name,
                        "stored_path": stored_drawing.relative_path,
                        "drawing_sha256": stored_drawing.sha256,
                        "confidence": extraction_result.confidence,
                        "updated_fields": ", ".join(DRAWING_SPEC_COLUMNS),
                        "previous_values": json.dumps(
                            {
                                column: (
                                    None
                                    if pd.isna(selected_upload_row[column])
                                    else selected_upload_row[column]
                                )
                                for column in DRAWING_SPEC_COLUMNS
                            },
                            default=str,
                        ),
                        "committed_values": json.dumps(reviewed_specs, default=str),
                        "committed_at_utc": stored_drawing.committed_at_utc,
                    }
                )
                st.session_state["drawing_commit_message"] = (
                    f"{selected_upload_part} committed. The should-cost, fair-price, "
                    "anomaly, clustering, SHAP, savings, and portfolio pipelines were rerun."
                )
                st.rerun()
    else:
        st.info("Upload a drawing when thickness, material, dimensions, weight, bends, holes, or finish are missing.")

    if st.session_state.get("drawing_update_log"):
        with st.expander("Committed drawing audit log"):
            st.dataframe(
                pd.DataFrame(st.session_state["drawing_update_log"]),
                width="stretch",
                hide_index=True,
            )
    if st.button("Restore baseline part master"):
        baseline_parts = pd.read_csv(BASE_PARTS_PATH)
        baseline_parts["engineering_status"] = "Baseline ready"
        baseline_parts["prediction_status"] = "Ready"
        save_active_parts_database(baseline_parts)
        st.session_state["parts_database"] = baseline_parts
        st.session_state["drawing_update_log"] = []
        parts_raw = st.session_state["parts_database"].copy()
        st.success("Active part database restored from the recoverable baseline part master.")

parts_raw = st.session_state["parts_database"].copy()
errors = validate_parts(parts_raw)
if errors:
    for error in errors:
        st.error(error)
    st.stop()

# Parts with incomplete drawing fields remain available for ingestion but are
# intentionally blocked from cost and ML execution until reviewed data is committed.
ready_mask = missing_drawing_specs(parts_raw).eq(0)
ready_parts_raw = parts_raw.loc[ready_mask].copy()
if ready_parts_raw.empty:
    st.error("No parts have complete engineering data. Commit a reviewed drawing first.")
    st.stop()

# First backend calculation: engineering should-cost from the Cost Digital Twin.
priced_parts = calculate_should_cost(
    ready_parts_raw,
    material_rate_factor=market_adjustment.material_rate_factor,
)
# Second backend calculation: ML fair price, anomaly detection, clusters, XAI.
ai_result = run_ai_pricing_models(
    priced_parts,
    commodity_index=market_adjustment.steel_index,
    fx_rate=market_adjustment.usd_inr,
    market_source_status=market_adjustment.source_status,
)
ai_priced_parts = ai_result.priced_parts
geo_indices = load_csv("geo_cost_indices.csv")
benchmarks = load_csv("supplier_benchmarks.csv")

try:
    erp_transactions = read_erp_transactions(erp_file)
    erp_error = None
except ValueError as exc:
    erp_transactions = pd.DataFrame()
    erp_error = str(exc)

explanations = explain_price_flags(priced_parts)
procurement_explanations = build_procurement_explanations(ai_priced_parts)
query_part_id = get_selected_part_id(priced_parts)
selected_part = ai_priced_parts.loc[ai_priced_parts["part_id"] == query_part_id].iloc[0]

if get_app_view() == "detail":
    render_part_detail(selected_part, ai_priced_parts, erp_transactions)
    st.stop()

total_spend = ai_priced_parts["erp_price"].mul(ai_priced_parts["annual_volume"]).sum()
total_ml_fair_spend = (
    ai_priced_parts["ai_predicted_fair_price"].mul(ai_priced_parts["annual_volume"]).sum()
)
opportunity = ai_priced_parts["ai_savings_opportunity"].sum()
savings_part_count = int((ai_priced_parts["ai_savings_opportunity"] > 0).sum())

if active_workspace == "Portfolio":
    kpi_cols = st.columns(4)
    kpi_cols[0].metric("ERP annual spend", compact_money(total_spend))
    kpi_cols[1].metric("ML fair spend", compact_money(total_ml_fair_spend))
    kpi_cols[2].metric("Qualified savings", compact_money(opportunity))
    kpi_cols[3].metric("Savings-eligible parts", f"{savings_part_count}/{len(ai_priced_parts)}")
    st.caption(
        "Qualified savings excludes parts where ML Predicted Fair Price is higher than ERP/current supplier price. "
        "Should-cost remains visible as the engineering anchor."
    )

    st.subheader("ERP Price vs Predicted Fair Price")
    review_parts = (
        ai_priced_parts.loc[ai_priced_parts["gap_status"].eq("Review")]
        .sort_values("ai_price_gap_pct", ascending=False)
        .copy()
    )
    st.caption("All priced parts. Click a part ID to open its detailed cost digital twin analysis page.")
    display_columns = [
        "part_id",
        "gap_status",
        "part_name",
        "category",
        "material_grade",
        "thickness_mm",
        "bend_count",
        "hole_count",
        "surface_finish",
        "weight_kg",
        "material_cost",
        "current_supplier",
        "supplier_region",
        "erp_price",
        "should_cost",
        "ai_predicted_fair_price",
        "ai_price_gap_pct",
        "ai_savings_opportunity",
        "prediction_confidence",
        "label_quality_status",
        "should_cost_variance_pct",
        "shap_top_feature",
        "shap_procurement_explanation",
    ]
    pricing_table_config = {
        "part_id": st.column_config.LinkColumn(
            "part_id",
            display_text=r"part_id=([^&]+)",
            help="Open detailed part analysis",
        ),
        "gap_status": st.column_config.LinkColumn(
            "gap_status",
            display_text=r"gap_status=([^&]+)",
            help="Open detailed part analysis",
        ),
        "erp_price": st.column_config.NumberColumn("erp_price", format="₹%.0f"),
        "should_cost": st.column_config.NumberColumn("should_cost", format="₹%.0f"),
        "ai_predicted_fair_price": st.column_config.NumberColumn("ML fair price", format="₹%.0f"),
        "ai_price_gap_pct": st.column_config.NumberColumn("ML gap %", format="%.1f%%"),
        "ai_savings_opportunity": st.column_config.NumberColumn(
            "qualified_ml_savings",
            format="₹%.0f",
        ),
        "should_cost_variance_pct": st.column_config.NumberColumn(
            "ML vs should-cost %",
            format="%.1f%%",
        ),
        "shap_top_feature": st.column_config.TextColumn("top ML driver"),
        "shap_procurement_explanation": st.column_config.TextColumn("ML explanation"),
        "thickness_mm": st.column_config.NumberColumn("thickness_mm", format="%.1f"),
        "weight_kg": st.column_config.NumberColumn("weight_kg", format="%.2f"),
        "material_cost": st.column_config.NumberColumn("material_cost", format="₹%.0f"),
    }
    portfolio_view = add_part_links(ai_priced_parts)
    st.dataframe(
        portfolio_view[display_columns],
        width="stretch",
        hide_index=True,
        column_config=pricing_table_config,
    )

    st.subheader("Items Requiring Review")
    st.caption(
        f"Showing {len(review_parts)} parts with Gap Status = Review, sorted by highest ML gap."
    )
    review_view = add_part_links(review_parts)
    st.dataframe(
        review_view[display_columns],
        width="stretch",
        hide_index=True,
        column_config=pricing_table_config,
    )

    fig = px.scatter(
        ai_priced_parts,
        x="ai_predicted_fair_price",
        y="erp_price",
        color="prediction_confidence",
        size="annual_volume",
        hover_name="part_name",
        hover_data=["category", "current_supplier", "ai_price_gap_pct", "should_cost"],
        labels={"ai_predicted_fair_price": "ML Predicted Fair Price", "erp_price": "ERP supplier price"},
    )
    fig.add_shape(
        type="line",
        x0=ai_priced_parts["ai_predicted_fair_price"].min() * 0.9,
        y0=ai_priced_parts["ai_predicted_fair_price"].min() * 0.9,
        x1=ai_priced_parts["ai_predicted_fair_price"].max() * 1.1,
        y1=ai_priced_parts["ai_predicted_fair_price"].max() * 1.1,
        line={"dash": "dash", "color": "#555"},
    )
    st.plotly_chart(fig, use_container_width=True)

if active_workspace == "AI Models":
    st.subheader("AI Pricing, Anomaly Detection, and Segmentation")
    st.caption(
        "Linear Regression, Random Forest, and XGBoost learn the explainable should-cost as "
        "the fair-price target. Isolation Forest flags unusual pricing patterns, and K-Means "
        "segments similar parts."
    )

    ai_columns = [
        "part_id",
        "part_name",
        "category",
        "erp_price",
        "should_cost",
        "linear_regression_fair_price",
        "random_forest_fair_price",
        "xgboost_fair_price",
        "ai_predicted_fair_price",
        "ai_price_gap_pct",
        "ai_savings_opportunity",
        "should_cost_variance_pct",
        "prediction_confidence",
        "label_quality_status",
        "shap_top_feature",
        "shap_explanation_method",
        "isolation_forest_flag",
        "kmeans_cluster",
    ]
    st.dataframe(
        ai_priced_parts[ai_columns].style.format(
            {
                "erp_price": "₹{:,.0f}",
                "should_cost": "₹{:,.0f}",
                "linear_regression_fair_price": "₹{:,.0f}",
                "random_forest_fair_price": "₹{:,.0f}",
                "xgboost_fair_price": "₹{:,.0f}",
                "ai_predicted_fair_price": "₹{:,.0f}",
                "ai_price_gap_pct": "{:,.1f}%",
                "ai_savings_opportunity": "₹{:,.0f}",
                "should_cost_variance_pct": "{:,.1f}%",
            }
        ),
        width="stretch",
        hide_index=True,
    )

    metrics_col, clusters_col = st.columns(2)
    with metrics_col:
        st.caption("Supervised model fit on demo data")
        st.dataframe(
            ai_result.model_metrics.style.format(
                {
                    "training_mae": "₹{:,.2f}",
                    "training_mape": "{:,.1f}%",
                    "training_rmse": "₹{:,.2f}",
                    "training_r2": "{:,.3f}",
                }
            ),
            width="stretch",
            hide_index=True,
        )

    st.caption("Fair-price label and confidence quality")
    st.dataframe(
        ai_result.label_quality.style.format({"avg_sample_weight": "{:,.2f}"}),
        width="stretch",
        hide_index=True,
    )
    with clusters_col:
        st.caption("K-Means part clusters")
        st.dataframe(
            ai_result.cluster_summary.style.format(
                {
                    "avg_erp_price": "₹{:,.0f}",
                    "avg_ai_fair_price": "₹{:,.0f}",
                    "avg_gap_pct": "{:,.1f}%",
                    "qualified_savings": "₹{:,.0f}",
                }
            ),
            width="stretch",
            hide_index=True,
        )

    st.caption("Part-level SHAP / model explanation")
    st.dataframe(
        ai_result.shap_explanations.style.format({"top_feature_impact": "{:,.3f}"}),
        width="stretch",
        hide_index=True,
    )

    top_importance = ai_result.feature_importance.groupby(
        ["algorithm", "feature", "explanation_method"],
        as_index=False,
    ).agg(importance=("importance", "mean"))
    top_importance = (
        top_importance.sort_values(["algorithm", "importance"], ascending=[True, False])
        .groupby("algorithm")
        .head(8)
    )
    fig = px.bar(
        top_importance,
        x="importance",
        y="feature",
        color="algorithm",
        facet_col="algorithm",
        orientation="h",
        labels={"importance": "Feature importance", "feature": "Feature"},
    )
    fig.update_yaxes(matches=None, showticklabels=True)
    st.plotly_chart(fig, use_container_width=True)

    fig = px.scatter(
        ai_priced_parts,
        x="ai_predicted_fair_price",
        y="erp_price",
        color="isolation_forest_flag",
        symbol="kmeans_cluster",
        size="annual_volume",
        hover_name="part_name",
        hover_data=["category", "ai_price_gap_pct", "kmeans_cluster"],
        labels={
            "ai_predicted_fair_price": "AI predicted fair price",
            "erp_price": "ERP supplier price",
        },
    )
    st.plotly_chart(fig, use_container_width=True)

if active_workspace == "ERP Intelligence":
    st.subheader("ERP Procurement Intelligence")
    if erp_error:
        st.error(erp_error)
    else:
        erp_kpis = st.columns(4)
        erp_kpis[0].metric("ERP transactions", f"{len(erp_transactions):,}")
        erp_kpis[1].metric("Parts", f"{erp_transactions['part_id'].nunique():,}")
        erp_kpis[2].metric("Suppliers anonymized", f"{erp_transactions['supplier_id'].nunique():,}")
        erp_kpis[3].metric(
            "Normalized spend",
            f"${erp_transactions['unit_price_usd'].mul(erp_transactions['quantity']).sum():,.0f}",
        )

        erp_view = erp_transactions.copy()
        erp_view["po_month"] = pd.to_datetime(erp_view["po_date"]).dt.to_period("M").astype(str)
        erp_view["spend_usd"] = erp_view["unit_price_usd"] * erp_view["quantity"]

        trend = (
            erp_view.groupby(["po_month", "category"], as_index=False)
            .agg(avg_unit_price_usd=("unit_price_usd", "mean"), spend_usd=("spend_usd", "sum"))
            .sort_values("po_month")
        )
        fig = px.line(
            trend,
            x="po_month",
            y="avg_unit_price_usd",
            color="category",
            markers=True,
            labels={"po_month": "PO month", "avg_unit_price_usd": "Avg unit price USD"},
        )
        st.plotly_chart(fig, use_container_width=True)

        left_col, right_col = st.columns(2)
        supplier_price = (
            erp_view.groupby(["supplier_id", "category"], as_index=False)
            .agg(avg_unit_price_usd=("unit_price_usd", "mean"), spend_usd=("spend_usd", "sum"))
            .sort_values("avg_unit_price_usd", ascending=False)
        )
        country_spend = (
            erp_view.groupby(["country", "category"], as_index=False)
            .agg(spend_usd=("spend_usd", "sum"), avg_unit_price_usd=("unit_price_usd", "mean"))
            .sort_values("spend_usd", ascending=False)
        )

        with left_col:
            st.caption("Supplier benchmark from anonymized ERP transactions")
            st.dataframe(
                supplier_price.style.format(
                    {"avg_unit_price_usd": "${:,.2f}", "spend_usd": "${:,.0f}"}
                ),
                width="stretch",
                hide_index=True,
            )

        with right_col:
            st.caption("Geographic spend comparison")
            st.dataframe(
                country_spend.style.format(
                    {"avg_unit_price_usd": "${:,.2f}", "spend_usd": "${:,.0f}"}
                ),
                width="stretch",
                hide_index=True,
            )

        st.caption("Cleaned ERP dataset")
        st.dataframe(
            erp_transactions.style.format(
                {"unit_price": "{:,.2f}", "unit_price_usd": "${:,.2f}", "quantity": "{:,.0f}"}
            ),
            width="stretch",
            hide_index=True,
        )

if active_workspace == "Cost Drivers":
    selected_part_id = st.selectbox("Select part", priced_parts["part_id"])
    selected_part = priced_parts.loc[priced_parts["part_id"] == selected_part_id].iloc[0]
    cost_breakdown = pd.DataFrame(
        {
            "cost_bucket": [
                "Material Cost",
                "Energy Cost",
                "Labour Cost",
                "Bends and Holes",
                "Surface Finish",
                "Overhead",
                "Manual Template Adjustments",
                "Supplier Margin",
            ],
            "amount": [
                selected_part["material_cost"],
                selected_part["energy_cost"],
                selected_part["labour_cost"],
                selected_part["process_complexity_cost"],
                selected_part["surface_finish_cost"],
                selected_part["overhead"],
                selected_part["manual_template_adjustment_cost"],
                selected_part["supplier_margin"],
            ],
        }
    )
    st.metric(
        f"{selected_part['part_name']} should-cost",
        money(selected_part["should_cost"]),
        delta=f"{percent(selected_part['price_gap_pct'])} vs ERP",
    )
    fig = px.bar(cost_breakdown, x="cost_bucket", y="amount", text_auto=".0f")
    st.plotly_chart(fig, use_container_width=True)

    st.caption("Drawing-derived attributes used by the cost twin")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "material_grade": selected_part["material_grade"],
                    "thickness_mm": selected_part["thickness_mm"],
                    "blank_area_m2": selected_part["blank_area_m2"],
                    "weight_kg": selected_part["weight_kg"],
                    "material_cost": selected_part["material_cost"],
                    "bend_count": selected_part["bend_count"],
                    "hole_count": selected_part["hole_count"],
                    "surface_finish": selected_part["surface_finish"],
                }
            ]
        ).style.format(
            {
                "thickness_mm": "{:,.1f}",
                "blank_area_m2": "{:,.3f}",
                "weight_kg": "{:,.2f}",
                "material_cost": "₹{:,.0f}",
            }
        ),
        width="stretch",
        hide_index=True,
    )

if active_workspace == "Explainability":
    st.subheader("Explainable AI Procurement Answers")
    savings_explanations = (
        procurement_explanations.loc[
            procurement_explanations["savings_opportunity"].gt(0)
        ]
        .sort_values("savings_opportunity", ascending=False)
        .copy()
    )
    st.caption(
        f"Showing {len(savings_explanations)} parts with a qualified savings opportunity. "
        "Select a row to open its detailed PDF below in this tab."
    )
    narrative_columns = [
        "erp_price_explanation",
        "negotiation_recommendation",
        "batna",
        "xai_summary",
    ]
    report_table = savings_explanations.drop(columns=narrative_columns).copy()
    report_selection = st.dataframe(
        report_table,
        width="stretch",
        hide_index=True,
        key="procurement_report_table",
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "erp_price": st.column_config.NumberColumn("ERP price", format="₹%.0f"),
            "fair_price": st.column_config.NumberColumn("ML fair price", format="₹%.0f"),
            "should_cost": st.column_config.NumberColumn("Should-cost", format="₹%.0f"),
            "price_gap_pct": st.column_config.NumberColumn("Price gap", format="%.1f%%"),
            "savings_opportunity": st.column_config.NumberColumn(
                "Qualified savings",
                format="₹%.0f",
            ),
        },
    )

    selected_report_part_id = requested_report_part_id
    selected_report_rows = report_selection.selection.rows
    if selected_report_rows:
        selected_report_part_id = str(
            report_table.iloc[int(selected_report_rows[0])]["part_id"]
        )

    if selected_report_part_id:
        explanation_match = savings_explanations.loc[
            savings_explanations["part_id"].astype(str).eq(selected_report_part_id)
        ]
        part_match = ai_priced_parts.loc[
            ai_priced_parts["part_id"].astype(str).eq(selected_report_part_id)
        ]
        if explanation_match.empty or part_match.empty:
            st.warning("The selected PDF is unavailable because this part has no qualified savings opportunity.")
        else:
            explanation_row = explanation_match.iloc[0]
            report_part = part_match.iloc[0]
            report_bytes = cached_procurement_report(
                explanation_row.to_dict(),
                report_part.to_dict(),
            )
            safe_report_part_id = "".join(
                character if character.isalnum() or character in {"-", "_"} else "_"
                for character in selected_report_part_id
            )
            report_file_name = f"Procurement_Decision_Report_{safe_report_part_id}.pdf"
            st.subheader(f"Detailed Procurement PDF — {selected_report_part_id}")
            st.download_button(
                "Download detailed PDF",
                data=report_bytes,
                file_name=report_file_name,
                mime="application/pdf",
                key=f"download_procurement_report_{safe_report_part_id}",
            )
            report_page_count = pdf_page_count(report_bytes)
            for report_page_number in range(1, report_page_count + 1):
                report_page_image = render_pdf_page(
                    report_bytes,
                    page_number=report_page_number,
                    scale=1.6,
                )
                st.image(
                    report_page_image,
                    caption=(
                        f"{report_file_name} — page {report_page_number} "
                        f"of {report_page_count}"
                    ),
                    width="stretch",
                )

    driver_summary = (
        explanations.groupby(["top_cost_driver", "gap_status"], as_index=False)
        .agg(parts=("part_id", "count"))
        .sort_values("parts", ascending=False)
    )
    st.caption("Flagged parts grouped by their top cost driver")
    fig = px.bar(
        driver_summary,
        x="top_cost_driver",
        y="parts",
        color="gap_status",
        labels={"top_cost_driver": "Top cost driver"},
    )
    st.plotly_chart(fig, use_container_width=True)

if active_workspace == "Supplier Benchmark":
    supplier_summary = (
        ai_priced_parts.groupby(["current_supplier", "category"], as_index=False)
        .agg(
            parts=("part_id", "count"),
            avg_gap_pct=("ai_price_gap_pct", "mean"),
            qualified_savings=("ai_savings_opportunity", "sum"),
            avg_should_cost=("should_cost", "mean"),
            avg_ml_fair_price=("ai_predicted_fair_price", "mean"),
        )
        .merge(
            benchmarks,
            left_on=["current_supplier", "category"],
            right_on=["supplier", "category"],
            how="left",
        )
    )
    st.dataframe(
        supplier_summary[
            [
                "current_supplier",
                "category",
                "region",
                "parts",
                "avg_gap_pct",
                "qualified_savings",
                "quality_ppm",
                "on_time_delivery_pct",
                "lead_time_days",
                "commercial_risk_score",
            ]
        ].style.format(
            {
                "avg_gap_pct": "{:,.1f}%",
                "qualified_savings": "₹{:,.0f}",
                "on_time_delivery_pct": "{:,.0f}%",
            }
        ),
        width="stretch",
        hide_index=True,
    )
    fig = px.scatter(
        supplier_summary,
        x="quality_ppm",
        y="avg_gap_pct",
        size="qualified_savings",
        color="category",
        hover_name="current_supplier",
        labels={"quality_ppm": "Quality defects PPM", "avg_gap_pct": "Average price gap %"},
    )
    st.plotly_chart(fig, use_container_width=True)

if active_workspace == "Geo Cost":
    geo_part_id = st.selectbox("Geo comparison part", priced_parts["part_id"], key="geo_part")
    geo_part = priced_parts.loc[priced_parts["part_id"] == geo_part_id].iloc[0]
    geo_df = geo_cost_comparison(geo_part, geo_indices)
    st.dataframe(
        geo_df.style.format(
            {
                "material_cost": "₹{:,.0f}",
                "energy_cost": "₹{:,.0f}",
                "labour_cost": "₹{:,.0f}",
                "process_complexity_cost": "₹{:,.0f}",
                "surface_finish_cost": "₹{:,.0f}",
                "overhead": "₹{:,.0f}",
                "supplier_margin": "₹{:,.0f}",
                "logistics": "₹{:,.0f}",
                "landed_should_cost": "₹{:,.0f}",
            }
        ),
        width="stretch",
        hide_index=True,
    )
    fig = px.bar(
        geo_df,
        x="region",
        y="landed_should_cost",
        color="region",
        text_auto=".0f",
        labels={"landed_should_cost": "Landed should-cost"},
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()
with st.expander("Cost model"):
    st.write(
        "Should Cost = Material Cost + Energy Cost + Labour Cost + Bend/Hole Complexity + Surface Finish + Overhead + Supplier Margin"
    )
    st.write(
        "The prototype flags parts where ERP/current supplier price is more than 5% above the predicted fair price."
    )
