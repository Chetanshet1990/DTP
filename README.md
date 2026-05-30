# Sheet Metal Cost Digital Twin

Procurement-focused should-cost intelligence prototype for a thesis demo on sheet metal sourcing.

GitHub repository:

```text
https://github.com/Chetanshet1990/DTP
```

## Features

- Calculates should-cost for sheet metal brackets, mounting plates, covers, panels, and fabricated assemblies
- Compares ERP/current supplier price with predicted fair price
- Flags price gaps above 5%
- Counts savings opportunity only when predicted fair price is lower than ERP/current supplier spend
- Derives predicted fair price from live steel index and USD/INR FX data without exposing live rates in the dashboard
- Explains flagged prices using drawing-derived cost drivers such as thickness, bends, holes, and surface finish
- Benchmarks suppliers by price gap, quality, delivery, lead time, and risk
- Compares landed should-cost across regions
- Accepts Excel or CSV datasets

## Cost Formula

```text
Should Cost =
Material Cost +
Energy Cost +
Labour Cost +
Bend/Hole Complexity +
Surface Finish +
Overhead +
Supplier Margin
```

Material cost rule used inside the model:

```text
Market Adjusted Steel Rate / kg =
Base Steel Rate / kg x
(Latest Steel Index / Base Steel Index) x
(Latest USD/INR / Base USD/INR)

Material Cost =
Weight kg x Market Adjusted Steel Rate / kg
```

Other should-cost drivers:

- Energy: part kWh multiplied by predicted energy tariff for the supplier country of origin.
- Labour: part labour hours multiplied by predicted labour rate for the supplier country of origin.
- Bends and holes: treated as machine operation cost using operation minutes and country-level machine hour rate.
- Surface finish: included because sheet metal finishes such as painting, powder coating, zinc plating, and passivation add real conversion cost; estimated from blank area and finish type.
- Overhead: applied to conversion cost using a country-level overhead assumption.
- Supplier margin: uses a minimum industry margin by part category, not the submitted supplier margin.

Current live-data sources:

- Steel index: FRED `WPU101`, Producer Price Index for Iron and Steel
- FX: Frankfurter USD/INR latest exchange rate API

If live market data is unavailable, the app falls back to baseline steel index and USD/INR values so the demo remains usable. Live steel index and FX values are used as model inputs, not displayed as dashboard KPIs.

Qualified savings opportunity rule:

```text
Qualified Savings Opportunity = max(ERP Price - Predicted Fair Price, 0) x Annual Volume
```

If predicted fair price is higher than ERP/current supplier price, the part is counted as ₹0 qualified savings.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy

Recommended option for external users:

1. Open Streamlit Community Cloud: `https://share.streamlit.io`
2. Create a new app from repository `Chetanshet1990/DTP`.
3. Select branch `main`.
4. Set main file path to `app.py`.
5. Deploy.

The deployed app will get a public `*.streamlit.app` URL that can be shared with external users.

Deployment notes:

- The app uses relative links for part-level drill-down pages, so clickable `part_id` links work on localhost and on the deployed Streamlit domain.
- No API keys or private secrets are required for the current demo dataset.
- `requirements.txt` contains the Python packages needed by Streamlit Cloud.

## Development Workflow

Use this flow when continuing development:

```bash
git status
git add -A
git commit -m "Describe the change"
git push
```

Run local checks before pushing important changes:

```bash
python3 tests/test_erp_pipeline.py
python3 tests/test_cost_model.py
python3 -m py_compile app.py dtp/cost_model.py dtp/erp_pipeline.py scripts/clean_erp_data.py tests/test_erp_pipeline.py tests/test_cost_model.py
```

Run the app locally:

```bash
streamlit run app.py
```

Then open:

```text
http://localhost:8501
```

## ERP Data Pipeline

Clean and anonymize raw ERP procurement data:

```bash
python3 scripts/clean_erp_data.py --input data/erp_raw_sample.csv --output-dir data/processed
```

Generated outputs:

- `data/processed/erp_cleaned.csv`
- `data/processed/supplier_anonymization_map.csv`
- `data/processed/erp_data_quality_report.csv`

The portal also accepts raw ERP CSV or Excel uploads in the sidebar and applies the same cleaning pipeline before showing ERP Intelligence analytics.

## Dataset

The app includes sample CSV datasets in `data/` and an Excel workbook at `data/digital_twin_pricing_demo.xlsx`.

For the upload flow, use the workbook's `Parts` sheet exported as Excel/CSV, or upload any `.xlsx`, `.xls`, or `.csv` file with these columns:

```text
part_id, part_name, category, material, material_grade, thickness_mm,
length_mm, width_mm, weight_kg, bend_count, hole_count, surface_finish,
finish_cost_per_part, material_rate_per_kg, cycle_time_min,
energy_kwh_per_part, energy_rate_per_kwh, labour_hours,
labour_rate_per_hour, overhead_pct, supplier_margin_pct,
current_supplier, supplier_region, erp_price, annual_volume
```

Raw ERP upload files should include:

```text
Part Number, Part Description, Category, Supplier Name, Supplier Country,
PO Date, Quantity, Unit Price, Currency
```

## Future Scope

- CAD ingestion
- Reinforcement learning optimization
- ERP integration
- LLM assistant for sourcing decisions
