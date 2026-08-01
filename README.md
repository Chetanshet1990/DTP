# Sheet Metal Cost Digital Twin

Procurement-focused should-cost intelligence prototype for a thesis demo on sheet metal sourcing.

GitHub repository:

```text
https://github.com/Chetanshet1990/DTP
```

## Features

- Calculates should-cost for sheet metal brackets, mounting plates, covers, panels, and fabricated assemblies
- Applies Linear Regression, Random Forest, XGBoost, Isolation Forest, and K-Means to the priced part dataset
- Targets ML Predicted Fair Price using drawing/engineering parameters, part-level ERP price evidence, commodity index, and FX rates
- Applies SHAP TreeExplainer for part-level ML fair-price explanations
- Incorporates manual should-cost template adjustments for scrap recovery, rejection, tool maintenance, packing/forwarding, and tooling amortization
- Compares ERP/current supplier price with ML Predicted Fair Price and should-cost anchor
- Flags price gaps above 5%
- Counts savings opportunity only when ML Predicted Fair Price is lower than ERP/current supplier spend
- Derives predicted fair price from live steel index and USD/INR FX data without exposing live rates in the dashboard
- Shows live steel index, USD/INR FX, source status, and material adjustment factor in the sidebar
- Explains flagged prices using drawing-derived cost drivers such as thickness, bends, holes, and surface finish
- Shows part-level monthly ERP price history against daily ML-predicted fair prices, with generated/interpolated ERP months labelled in the data table
- Benchmarks suppliers by price gap, quality, delivery, lead time, and risk
- Compares landed should-cost across regions
- Includes Excel/CSV reader functions for part and ERP datasets; the current UI defaults to repository CSV files and exposes drawing upload only
- Keeps a persistent working engineering master in `data/processed/active_parts_master.csv` while retaining `data/sample_parts.csv` as the recoverable baseline
- Supports a single-row drawing review and edit step before an atomic commit to the selected part
- Blocks incomplete drawing rows from pricing without blocking the drawing-ingestion screen or the rest of the portfolio
- Dry-runs and then reruns should-cost, fair-price, anomaly, clustering, SHAP, savings, and portfolio outputs after a drawing commit

## ML Fair Price Pipeline

The V1 executable ML pipeline separates three pricing concepts:

```text
ERP Price
= actual paid/current supplier price

Should-Cost
= explainable engineering cost estimate from the Cost Digital Twin

ML Predicted Fair Price
= learned price estimate from the active part-level training table, drawing/engineering
   features, supplier region, commodity index, and FX rates
```

The model does not use the raw active ERP/current supplier price blindly as truth. It creates `ml_fair_price_label` by clipping abnormal ERP-to-should-cost gaps and downweighting those rows. In the current repository, this operates on the synthetic part-level demonstration table. The separate cleaned real ERP extract has not yet been joined to matching drawing attributes. When that join is available, this pipeline is the place to remove returns, one-off tooling/freight/emergency effects, normalize historical market context, and control anomalous supplier pricing.

V1 prediction level:

```text
part drawing parameters + supplier region + market context + volume
-> current ML Predicted Fair Price
```

Mandatory V1 model inputs:

```text
material_grade, thickness_mm, length_mm, width_mm, weight_kg,
bend_count, hole_count, surface_finish, part_category,
annual_volume, supplier_region, commodity_index, fx_rate
```

Recommended model stack:

- Linear Regression: academic baseline.
- Random Forest: non-linear benchmark.
- XGBoost or LightGBM: primary tabular fair-price model.
- Isolation Forest: anomaly detection and training-label cleanup support.
- SHAP: part-level prediction explanation translated into procurement language.

Low-history or new parts should use the Cost Digital Twin as a fallback or anchor. The app should show prediction confidence based on OCR completeness, similar ERP history, market-data freshness, and validation error.

Implemented V1 pipeline fields include:

```text
ml_fair_price_label
training_sample_weight
prediction_readiness
prediction_confidence
label_quality_status
similar_erp_history_count
commodity_index
fx_rate
should_cost_variance
should_cost_variance_pct
shap_top_feature
shap_procurement_explanation
manual_template_adjustment_cost
```

Live market fallback rule:

```text
Live commodity/FX available -> use live values
Live unavailable and cache exists -> use latest cached values
Live unavailable and no cache exists -> use baseline values and mark lower confidence
```

## Cost Formula

```text
Should Cost =
Material Cost +
Energy Cost +
Labour Cost +
Bend/Hole Complexity +
Surface Finish +
Overhead +
Manual Template Adjustments +
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

- Manual template adjustments: optional benchmark-style costing fields for scrap recovery, rejection allowance, tool maintenance, packing/forwarding, and tooling amortization.
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
Qualified ML Savings = max(ERP Price - ML Predicted Fair Price, 0) x Annual Volume
```

If ML Predicted Fair Price is higher than ERP/current supplier price, the part is counted as ₹0 qualified savings. Should-Cost remains visible as an explainable anchor and sanity check.

## AI Algorithms Implemented

The current prototype uses these algorithms in `dtp/ml_models.py` and displays them in the Streamlit `AI Models` tab:

- Linear Regression: supervised fair-price prediction from engineering, supplier, and volume features.
- Random Forest: non-linear supervised fair-price prediction plus feature importance.
- XGBoost: gradient-boosted supervised fair-price prediction plus feature importance and SHAP explanations.
- SHAP TreeExplainer: part-level explanation of the strongest ML fair-price driver translated into procurement language.
- Isolation Forest: unsupervised anomaly detection for unusual price and part-cost patterns.
- K-Means: unsupervised segmentation of similar parts into cost/engineering clusters.

On macOS, native XGBoost may require the OpenMP runtime (`libomp`). If that runtime is unavailable, the app keeps running with a marked gradient-boosting compatibility fallback; deployed Linux environments commonly provide the required runtime.

Planned thesis-grade validation:

- Time-based train/test split: train on older ERP transactions and test on newer transactions.
- Regression metrics: MAE, MAPE, RMSE, and R².
- Procurement validation: review the top flagged savings/anomaly opportunities for commercial reasonableness.

Current metrics are in-sample training metrics and must be treated as prototype execution evidence, not out-of-sample model accuracy.

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
python3 tests/test_ml_models.py
PYTHONPYCACHEPREFIX=.pycache_check python3 -m py_compile app.py dtp/cost_model.py dtp/erp_pipeline.py dtp/market_data.py dtp/ml_models.py scripts/clean_erp_data.py scripts/import_bracket_purchase_data.py tests/test_erp_pipeline.py tests/test_cost_model.py tests/test_ml_models.py
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
python3 scripts/clean_erp_data.py --input /path/to/raw_erp.csv --output-dir /path/to/processed-output
```

Do not target `data/processed/` during experimentation unless you intend to replace the checked-in 90-row real ERP evidence outputs.

Import the real bracket purchase workbook into the same ERP schema:

```bash
python3 scripts/import_bracket_purchase_data.py --input /path/to/bracket_purchase_data.xlsx --output /path/to/imported_erp.csv --processed-output-dir /path/to/processed-output
```

Generated outputs:

- `data/processed/erp_cleaned.csv`
- `data/processed/supplier_anonymization_map.csv`
- `data/processed/erp_data_quality_report.csv`

The backend reader functions support raw ERP CSV or Excel inputs and apply the same cleaning pipeline. The current Streamlit screen does not expose an ERP/part-file uploader; it loads the checked-in CSV defaults and exposes only the drawing-upload workflow.

## Drawing Review and Commit Workflow

The active demonstration master is `data/processed/active_parts_master.csv`. The
recoverable 120-part baseline remains in `data/sample_parts.csv`. `SM-1001` starts
with its drawing-derived fields cleared and is marked as awaiting a drawing.
Incomplete parts remain selectable in the `Upload Drawing` tab but are excluded
from should-cost and ML execution until their reviewed values are committed.

Use this workflow:

1. Select the target part ID in the frontend.
2. Upload a text-searchable PDF drawing.
3. Compare the inline drawing preview with the vertical `Parameter` / `Reviewed value` table, then review or edit each value.
4. Commit the reviewed data.
5. The app validates the candidate master and dry-runs the complete pricing/ML pipeline.
6. On success, the uploaded file is stored under `data/drawings/committed/<part_id>/`, its path and SHA-256 hash are written to the active master, and the active master is replaced atomically.
7. Streamlit reruns all pricing, ML, anomaly, clustering, SHAP, savings, and portfolio outputs.
8. On failure, the active master remains unchanged and any partially stored drawing is removed.

For `SM-1001`, upload `data/drawings/SM-1001_searchable.pdf`. It preserves the
appearance of the supplied image-based A3 drawing and adds an extractable PDF text
layer containing category, material, grade, thickness, dimensions, weight, bend
count, hole count, and surface finish. Regenerate it from the original drawing with:

```bash
python3 scripts/generate_searchable_drawing.py \
  --input /path/to/SM-1001.pdf \
  --output data/drawings/SM-1001_searchable.pdf
```

The selected frontend part ID is authoritative; the drawing Part ID is not used as
a second validation gate.

Prepare one or more parts for a clean drawing-ingestion demonstration with:

```bash
python3 scripts/prepare_drawing_ingestion_demo.py SM-1001 SM-1002
```

The script atomically clears only drawing-derived fields and drawing metadata,
marks the selected parts as `Awaiting drawing` / `Blocked`, preserves commercial
data and stored drawing files, and leaves every unselected part unchanged. Restart
Streamlit after running it to clear existing browser-session widget state.

The horizontal workspace navigation is stored in Streamlit session state. Uploading
a file, editing extracted values, committing, or rerunning the app therefore keeps
the user on `Upload Drawing` instead of returning to `Portfolio`.
Changing the selected part number creates a fresh uploader instance, which clears
the previous part's file, preview, extracted values, and staged review table.

PDF pages are rendered server-side with PDFium and displayed beside the editable
extraction table; this avoids browser PDF-plugin and Streamlit component-version
compatibility problems. Image drawings are displayed directly.
The preview includes cursor-position magnification with selectable `1.5x`, `2x`,
and `3x` zoom levels; moving the cursor away restores the complete drawing view.
The review table is transposed vertically so all engineering fields use the height
beside the drawing instead of extending horizontally beyond the available width.
DXF and DWG uploads continue through extraction/commit without an inline renderer.

## ML Results and Graphs

Generate standalone ML result tables and interactive Plotly graphs from Python:

```bash
python3 scripts/generate_ml_results.py
```

Generated outputs are written to `outputs/ml_results/`:

- `prototype_ml_summary.md`
- `prototype_ml_summary.csv`
- `ml_priced_parts_results.csv`
- `ml_model_metrics.csv`
- `ml_feature_importance.csv`
- `ml_cluster_summary.csv`
- `ml_shap_explanations.csv`
- `model_prediction_fit.html`
- `prediction_residuals.html`
- `ml_fair_price_vs_should_cost.html`
- `model_mae_comparison.html`
- `feature_importance.html`
- `segmentation_anomaly_results.html`

## Dataset

The current repository snapshot contains two distinct data tracks:

- Active Review 3 demonstration data: `data/sample_parts.csv` contains the recoverable 120-part synthetic baseline, `data/processed/active_parts_master.csv` is the working engineering master loaded by the Streamlit app, and `data/erp_raw_sample.csv` contains 480 synthetic ERP transactions covering the same `SM-*` part IDs. The active `SM-1001` engineering fields are intentionally blank until its drawing is reviewed and committed.
- Real ERP evidence: `data/processed/erp_cleaned.csv` contains 90 cleaned and anonymized transactions from 97 source rows, covering 84 real bracket part IDs and 48 anonymized suppliers. These `BR-*` records do not yet have matching drawing attributes and are not currently joined to the active `SM-*` engineering master.

The older workbook `data/digital_twin_pricing_demo.xlsx` is a small demonstration workbook and is not the current default 120-part dataset.

The files already present in `outputs/ml_results/` were generated from the earlier 30-part baseline. Regenerate them with `python3 scripts/generate_ml_results.py` before citing results for the current 120-part dataset.

Review 2 feedback was to collect more real data and rerun the results. Expanding the synthetic demonstration set from 30 to 120 parts improves prototype coverage but does not satisfy that feedback by itself. The next validation step is to use `submissions/review_2/Review_2_Real_Data_Collection_Template.xlsx` to collect matching real ERP transactions and drawing/engineering attributes for the same part IDs before regenerating Cost Digital Twin and ML outputs.

Recommended next-submission data target:

- 100+ real ERP purchase rows, preferably 200-500.
- 30+ real sheet-metal part IDs, preferably 50-100.
- Matching material, thickness, dimensions, weight, bend count, hole count, finish, and process data for those part IDs.
- 5+ suppliers with country, region, and currency.
- 6-12 months of PO history, preferably 12-24 months.
- 10-20 expert/reference should-cost checks for validation.

For the upload flow, use the workbook's `Parts` sheet exported as Excel/CSV, or upload any `.xlsx`, `.xls`, or `.csv` file with these columns:

```text
part_id, part_name, category, material, material_grade, thickness_mm,
length_mm, width_mm, weight_kg, bend_count, hole_count, surface_finish,
finish_cost_per_part, material_rate_per_kg, cycle_time_min,
energy_kwh_per_part, energy_rate_per_kwh, labour_hours,
labour_rate_per_hour, overhead_pct, supplier_margin_pct,
current_supplier, supplier_region, erp_price, annual_volume
```

Optional manual should-cost template columns are also supported:

```text
blank_weight_kg, scrap_weight_kg, scrap_rate_per_kg, scrap_recovery_pct,
rejection_pct, tool_maintenance_pct, packing_forwarding_pct,
tooling_cost, tooling_cost_per_part
```

Raw ERP upload files should include:

```text
Part Number, Part Description, Category, Supplier Name, Supplier Country,
PO Date, Quantity, Unit Price, Currency
```

## Future Scope

- CAD ingestion
- Production OCR/CAD drawing-parameter extraction with field-level confidence and manual correction; the current prototype only parses text available in PDFs/DXF-style inputs using rules
- Cached commodity and FX history for time-aware fair-price trends
- Reinforcement learning optimization
- ERP integration
- LLM assistant for sourcing decisions
