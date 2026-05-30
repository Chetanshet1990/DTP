from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dtp.cost_model import PRICE_GAP_THRESHOLD, calculate_should_cost
from dtp.erp_pipeline import clean_erp_data
from dtp.market_data import get_market_adjustment
from dtp.ml_models import run_ai_pricing_models


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
APP_HOME_URL = "./"


st.set_page_config(
    page_title="Digital Twin Pricing",
    page_icon="DTP",
    layout="wide",
)


CATEGORY_PRESETS = {
    "Bracket": {
        "default_material_rate": 78.0,
        "default_energy_kwh": 0.55,
        "default_labour_rate": 390.0,
        "default_overhead_pct": 23.0,
        "default_margin_pct": 11.0,
    },
    "Mounting plate": {
        "default_material_rate": 86.0,
        "default_energy_kwh": 0.70,
        "default_labour_rate": 390.0,
        "default_overhead_pct": 24.0,
        "default_margin_pct": 11.0,
    },
    "Cover / panel": {
        "default_material_rate": 92.0,
        "default_energy_kwh": 1.05,
        "default_labour_rate": 410.0,
        "default_overhead_pct": 25.0,
        "default_margin_pct": 12.0,
    },
    "Fabricated assembly": {
        "default_material_rate": 80.0,
        "default_energy_kwh": 1.70,
        "default_labour_rate": 420.0,
        "default_overhead_pct": 27.0,
        "default_margin_pct": 12.0,
    },
}

SURFACE_FINISH_COSTS = {
    "Painted": 45.0,
    "Powder coated": 80.0,
    "Zinc plated": 60.0,
    "Passivated": 50.0,
}


REQUIRED_PART_COLUMNS = [
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


def load_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / name)


def read_parts(uploaded_file) -> pd.DataFrame:
    if uploaded_file is None:
        return load_csv("sample_parts.csv")

    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(uploaded_file)
    return pd.read_csv(uploaded_file)


def read_erp_transactions(uploaded_file) -> pd.DataFrame:
    if uploaded_file is None:
        raw_erp = load_csv("erp_raw_sample.csv")
    else:
        suffix = Path(uploaded_file.name).suffix.lower()
        if suffix in {".xlsx", ".xls"}:
            raw_erp = pd.read_excel(uploaded_file)
        else:
            raw_erp = pd.read_csv(uploaded_file)
    return clean_erp_data(raw_erp).cleaned_data


@st.cache_data(ttl=60 * 60)
def load_market_adjustment():
    return get_market_adjustment()


def validate_parts(parts: pd.DataFrame) -> list[str]:
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
        if pd.to_numeric(parts[column], errors="coerce").isna().any():
            errors.append(f"Column '{column}' contains non-numeric values.")
    return errors


def explain_price_flags(priced_parts: pd.DataFrame) -> pd.DataFrame:
    rows = []
    driver_columns = {
        "Material": "material_cost",
        "Energy": "energy_cost",
        "Labour": "labour_cost",
        "Bends and holes": "process_complexity_cost",
        "Surface finish": "surface_finish_cost",
        "Overhead": "overhead",
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
    part_id = st.query_params.get("part_id")
    if isinstance(part_id, list):
        part_id = part_id[0] if part_id else None
    if part_id in set(priced_parts["part_id"]):
        return str(part_id)
    return str(priced_parts["part_id"].iloc[0])


def get_app_view() -> str:
    view = st.query_params.get("view")
    if isinstance(view, list):
        view = view[0] if view else None
    return "detail" if view == "detail" else "portfolio"


def add_part_links(priced_parts: pd.DataFrame) -> pd.DataFrame:
    linked = priced_parts.copy()
    linked["part_id"] = linked["part_id"].map(
        lambda value: f"./?view=detail&part_id={quote(str(value))}"
    )
    return linked


def cost_breakdown_percent(selected_part: pd.Series) -> pd.DataFrame:
    rows = pd.DataFrame(
        {
            "cost_bucket": [
                "Supplier Margin",
                "Overhead",
                "Surface Finish",
                "Bends and Holes",
                "Energy",
                "Labour",
                "Steel",
            ],
            "amount": [
                selected_part["supplier_margin"],
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


def price_development_index(selected_part: pd.Series, erp_transactions: pd.DataFrame) -> pd.DataFrame:
    erp_price = float(selected_part["erp_price"])
    fair_price = float(selected_part["should_cost"])
    start_date = pd.Timestamp.today().normalize() - pd.DateOffset(years=1)
    end_date = pd.Timestamp.today().normalize()
    return pd.DataFrame(
        [
            {
                "date": start_date,
                "supplier_price_index": 100.0,
                "fair_price_index": 100.0,
            },
            {
                "date": end_date,
                "supplier_price_index": 100.0,
                "fair_price_index": fair_price / erp_price * 100,
            },
        ]
    )


def render_part_detail(
    selected_part: pd.Series,
    priced_parts: pd.DataFrame,
    erp_transactions: pd.DataFrame,
) -> None:
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
    detail_kpis[1].metric("Should-cost", money(selected_part["should_cost"]))
    detail_kpis[2].metric("Price gap", percent(selected_part["price_gap_pct"]))
    detail_kpis[3].metric("Qualified savings", money(selected_part["savings_opportunity"]))
    st.caption(
        "Savings is counted only when ERP/current supplier price is higher than predicted fair price. "
        "If fair price is higher than ERP price, savings is ₹0."
    )
    st.caption(
        "The chart indexes current ERP price to 100. A predicted fair price index below 100 means "
        "the should-cost model is lower than the current ERP price."
    )

    breakdown_pct = cost_breakdown_percent(selected_part)
    indexed_prices = price_development_index(selected_part, erp_transactions)
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
        ]
        for index, row in breakdown_pct.iterrows():
            fig.add_trace(
                go.Bar(
                    x=["Cost breakdown, %"],
                    y=[row["share_pct"]],
                    name=row["cost_bucket"],
                    marker_color=colors[index],
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
                x=indexed_prices["date"],
                y=indexed_prices["supplier_price_index"],
                mode="lines+markers",
                name="ERP supplier price",
                line={"shape": "hv", "color": "#3f5ea8", "width": 2},
            )
        )
        fig.add_trace(
            go.Scatter(
                x=indexed_prices["date"],
                y=indexed_prices["fair_price_index"],
                mode="lines+markers",
                name="Predicted fair price",
                line={"color": "#35aef5", "width": 2},
            )
        )
        fig.update_layout(
            title="Current ERP supplier price vs predicted fair price index",
            height=430,
            margin={"l": 10, "r": 10, "t": 55, "b": 20},
            yaxis_title="Index (100 = current ERP price)",
            xaxis_title=None,
            legend={"orientation": "h", "y": -0.18},
        )
        st.plotly_chart(fig, use_container_width=True)

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
    return f"₹{value:,.0f}"


def percent(value: float) -> str:
    return f"{value:,.1f}%"


st.title("Sheet Metal Cost Digital Twin")
st.caption("Explainable procurement intelligence for sheet metal sourcing")

with st.sidebar:
    st.header("Dataset")
    uploaded_file = st.file_uploader(
        "Upload ERP or should-cost dataset",
        type=["xlsx", "xls", "csv"],
    )
    st.caption("Leave blank to use the thesis demo dataset.")

    erp_file = st.file_uploader(
        "Upload raw ERP procurement data",
        type=["xlsx", "xls", "csv"],
        key="erp_upload",
    )
    st.caption("Raw ERP data is cleaned, normalized, and anonymized before analytics.")

    st.header("Create Scenario")
    category = st.selectbox("Manufacturing category", list(CATEGORY_PRESETS))
    preset = CATEGORY_PRESETS[category]
    weight_kg = st.number_input("Weight per part (kg)", min_value=0.001, value=1.2, step=0.1)
    material_rate = st.number_input(
        "Material rate per kg",
        min_value=0.0,
        value=preset["default_material_rate"],
        step=5.0,
    )
    energy_kwh = st.number_input(
        "Energy kWh per part",
        min_value=0.0,
        value=preset["default_energy_kwh"],
        step=0.05,
    )
    bend_count = st.number_input("Bend count", min_value=0, value=4, step=1)
    hole_count = st.number_input("Hole count", min_value=0, value=8, step=1)
    surface_finish = st.selectbox("Surface finish", list(SURFACE_FINISH_COSTS))
    labour_hours = st.number_input("Labour hours per part", min_value=0.0, value=0.12, step=0.01)
    erp_price = st.number_input("Current supplier price", min_value=0.0, value=500.0, step=10.0)


parts_raw = read_parts(uploaded_file)
errors = validate_parts(parts_raw)
if errors:
    for error in errors:
        st.error(error)
    st.stop()

market_adjustment = load_market_adjustment()

priced_parts = calculate_should_cost(
    parts_raw,
    material_rate_factor=market_adjustment.material_rate_factor,
)
ai_result = run_ai_pricing_models(priced_parts)
ai_priced_parts = ai_result.priced_parts
geo_indices = load_csv("geo_cost_indices.csv")
benchmarks = load_csv("supplier_benchmarks.csv")

try:
    erp_transactions = read_erp_transactions(erp_file)
    erp_error = None
except ValueError as exc:
    erp_transactions = pd.DataFrame()
    erp_error = str(exc)

scenario = pd.DataFrame(
    [
        {
            "part_id": "SCENARIO",
            "part_name": "What-if part",
            "category": category,
            "material": "User input",
            "material_grade": "User input",
            "thickness_mm": 2.5,
            "length_mm": 250,
            "width_mm": 180,
            "weight_kg": weight_kg,
            "bend_count": bend_count,
            "hole_count": hole_count,
            "surface_finish": surface_finish,
            "finish_cost_per_part": SURFACE_FINISH_COSTS[surface_finish],
            "material_rate_per_kg": material_rate,
            "cycle_time_min": 0,
            "energy_kwh_per_part": energy_kwh,
            "energy_rate_per_kwh": 8.5,
            "labour_hours": labour_hours,
            "labour_rate_per_hour": preset["default_labour_rate"],
            "overhead_pct": preset["default_overhead_pct"],
            "supplier_margin_pct": preset["default_margin_pct"],
            "current_supplier": "Scenario supplier",
            "supplier_region": "India",
            "erp_price": erp_price,
            "annual_volume": 1,
        }
    ]
)
scenario_result = calculate_should_cost(
    scenario,
    material_rate_factor=market_adjustment.material_rate_factor,
).iloc[0]
explanations = explain_price_flags(priced_parts)
query_part_id = get_selected_part_id(priced_parts)
selected_part = priced_parts.loc[priced_parts["part_id"] == query_part_id].iloc[0]

if get_app_view() == "detail":
    render_part_detail(selected_part, priced_parts, erp_transactions)
    st.stop()

total_spend = priced_parts["erp_price"].mul(priced_parts["annual_volume"]).sum()
total_should_cost = priced_parts["should_cost"].mul(priced_parts["annual_volume"]).sum()
review_count = int((priced_parts["gap_status"] == "Review").sum())
opportunity = priced_parts["savings_opportunity"].sum()
savings_part_count = int((priced_parts["savings_opportunity"] > 0).sum())

kpi_cols = st.columns(4)
kpi_cols[0].metric("ERP annual spend", money(total_spend))
kpi_cols[1].metric("Predicted fair spend", money(total_should_cost))
kpi_cols[2].metric("Qualified savings", money(opportunity))
kpi_cols[3].metric("Savings-eligible parts", f"{savings_part_count}/{len(priced_parts)}")
st.caption(
    "Qualified savings excludes parts where predicted fair price is higher than ERP/current supplier price."
)

tab_overview, tab_ai, tab_erp, tab_cost, tab_explain, tab_suppliers, tab_geo, tab_scenario = st.tabs(
    [
        "Portfolio",
        "AI Models",
        "ERP Intelligence",
        "Cost Drivers",
        "Explainability",
        "Supplier Benchmark",
        "Geo Cost",
        "What-if",
    ]
)

with tab_overview:
    st.subheader("ERP Price vs Predicted Fair Price")
    st.caption("Click a part ID to open its detailed cost digital twin analysis page.")
    display_columns = [
        "part_id",
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
        "price_gap_pct",
        "savings_opportunity",
        "opportunity_status",
        "gap_status",
    ]
    portfolio_view = add_part_links(priced_parts)
    st.dataframe(
        portfolio_view[display_columns],
        width="stretch",
        hide_index=True,
        column_config={
            "part_id": st.column_config.LinkColumn(
                "part_id",
                display_text=r"part_id=([^&]+)",
                help="Open detailed part analysis",
            ),
            "erp_price": st.column_config.NumberColumn("erp_price", format="₹%.0f"),
            "should_cost": st.column_config.NumberColumn("should_cost", format="₹%.0f"),
            "price_gap_pct": st.column_config.NumberColumn("price_gap_pct", format="%.1f%%"),
            "savings_opportunity": st.column_config.NumberColumn(
                "qualified_savings",
                format="₹%.0f",
            ),
            "thickness_mm": st.column_config.NumberColumn("thickness_mm", format="%.1f"),
            "weight_kg": st.column_config.NumberColumn("weight_kg", format="%.2f"),
            "material_cost": st.column_config.NumberColumn("material_cost", format="₹%.0f"),
        },
    )

    fig = px.scatter(
        priced_parts,
        x="should_cost",
        y="erp_price",
        color="gap_status",
        size="annual_volume",
        hover_name="part_name",
        hover_data=["category", "current_supplier", "price_gap_pct"],
        labels={"should_cost": "Predicted fair price", "erp_price": "ERP supplier price"},
    )
    fig.add_shape(
        type="line",
        x0=priced_parts["should_cost"].min() * 0.9,
        y0=priced_parts["should_cost"].min() * 0.9,
        x1=priced_parts["should_cost"].max() * 1.1,
        y1=priced_parts["should_cost"].max() * 1.1,
        line={"dash": "dash", "color": "#555"},
    )
    st.plotly_chart(fig, use_container_width=True)

with tab_ai:
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
                    "training_r2": "{:,.3f}",
                }
            ),
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

    top_importance = ai_result.feature_importance.groupby(
        ["algorithm", "feature"],
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

with tab_erp:
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

with tab_cost:
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
                "Supplier Margin",
            ],
            "amount": [
                selected_part["material_cost"],
                selected_part["energy_cost"],
                selected_part["labour_cost"],
                selected_part["process_complexity_cost"],
                selected_part["surface_finish_cost"],
                selected_part["overhead"],
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

with tab_explain:
    st.subheader("Why Parts Are Flagged")
    st.dataframe(
        explanations.style.format({"price_gap_pct": "{:,.1f}%"}),
        width="stretch",
        hide_index=True,
    )
    driver_summary = (
        explanations.groupby(["top_cost_driver", "gap_status"], as_index=False)
        .agg(parts=("part_id", "count"))
        .sort_values("parts", ascending=False)
    )
    fig = px.bar(
        driver_summary,
        x="top_cost_driver",
        y="parts",
        color="gap_status",
        labels={"top_cost_driver": "Top cost driver"},
    )
    st.plotly_chart(fig, use_container_width=True)

with tab_suppliers:
    supplier_summary = (
        priced_parts.groupby(["current_supplier", "category"], as_index=False)
        .agg(
            parts=("part_id", "count"),
            avg_gap_pct=("price_gap_pct", "mean"),
            qualified_savings=("savings_opportunity", "sum"),
            avg_should_cost=("should_cost", "mean"),
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

with tab_geo:
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

with tab_scenario:
    scenario_cols = st.columns(3)
    scenario_cols[0].metric("Material Cost", money(scenario_result["material_cost"]))
    scenario_cols[1].metric("Conversion Cost", money(scenario_result["conversion_cost"]))
    scenario_cols[2].metric("Should Cost", money(scenario_result["should_cost"]))

    st.caption(
        f"Scenario assumes {bend_count} bends, {hole_count} holes, and {surface_finish.lower()} finish."
    )

    comparison = pd.DataFrame(
        {
            "metric": ["ERP price", "Predicted fair price", "Price gap"],
            "amount": [
                scenario_result["erp_price"],
                scenario_result["should_cost"],
                scenario_result["price_gap"],
            ],
        }
    )
    st.plotly_chart(
        px.bar(comparison, x="metric", y="amount", color="metric", text_auto=".0f"),
        use_container_width=True,
    )
    if scenario_result["price_gap_pct"] > PRICE_GAP_THRESHOLD:
        st.warning(
            f"Scenario price is {percent(scenario_result['price_gap_pct'])} above predicted fair price."
        )
    else:
        st.success("Scenario price is within the 5% review threshold.")

st.divider()
with st.expander("Cost model"):
    st.write(
        "Should Cost = Material Cost + Energy Cost + Labour Cost + Bend/Hole Complexity + Surface Finish + Overhead + Supplier Margin"
    )
    st.write(
        "The prototype flags parts where ERP/current supplier price is more than 5% above the predicted fair price."
    )
