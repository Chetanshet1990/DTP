# Sheet Metal Cost Digital Twin

Procurement-focused should-cost intelligence prototype for a thesis demo on sheet metal sourcing.

## Features

- Calculates should-cost for sheet metal brackets, mounting plates, covers, panels, and fabricated assemblies
- Compares ERP/current supplier price with predicted fair price
- Flags price gaps above 5%
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

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy

Recommended option for external users:

1. Push this repository to GitHub.
2. Open Streamlit Community Cloud: `https://share.streamlit.io`
3. Create a new app from repository `Chetanshet1990/DTP`.
4. Select branch `main`.
5. Set main file path to `app.py`.
6. Deploy.

The deployed app will get a public `*.streamlit.app` URL that can be shared with external users.

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
