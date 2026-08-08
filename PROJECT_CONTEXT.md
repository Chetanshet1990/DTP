# PROJECT_CONTEXT.md

# Project Title

Explainable AI-Driven Cost Digital Twin for Procurement Intelligence and Price Anomaly Detection

---

# Project Overview

This project proposes an Explainable AI-driven procurement intelligence framework that combines cost modeling, machine learning, and anomaly detection to identify pricing inefficiencies in sheet metal sourcing.

The system aims to compare actual ERP purchase prices against ML Predicted Fair Prices and should-cost estimates, helping procurement teams identify negotiation opportunities and potential savings.

Qualified savings opportunity is counted only when ML Predicted Fair Price is lower than ERP/current supplier spend. If ML Predicted Fair Price is higher than ERP spend, the result is counted as ₹0 qualified savings.

The research focuses on reducing procurement cycle time from weeks of manual analysis to near real-time decision support.

---

# Problem Statement

ERP systems show historical purchase prices but do not indicate whether the paid price is fair, inflated, or market-aligned.

Global uncertainty arising from tariff wars, geopolitical tensions, repeated war escalations, commodity volatility, and inflation is creating significant pricing instability across global supply chains.

An AI-based procurement intelligence system is needed to predict fair prices, detect pricing anomalies, and explain cost gaps to support fact-based sourcing and negotiation decisions.


# Revised Scope

The project scope is intentionally limited to:

## Sheet Metal Components

Examples:
- Brackets
- Mounting plates
- Covers
- Panels
- Fabricated assemblies

Reason:
Accurate should-cost estimation requires engineering parameters that are readily available from manufacturing drawings.

---

# Research Objective

To develop an Explainable AI-based procurement intelligence system that:

1. Predicts fair market price.
2. Detects pricing anomalies.
3. Explains pricing deviations.
4. Supports procurement negotiations.
5. Estimates savings opportunities.

---

# Data Sources

## Primary Data

### ERP Procurement Data (Target)
Current repository snapshot has two separate ERP data tracks:

1. Active Review 3 demonstration data:
   - `data/erp_raw_sample.csv`
   - 480 synthetic ERP transactions covering 120 synthetic `SM-*` part IDs
   - Loaded by default in the Streamlit application and aligned with `data/sample_parts.csv`
2. Real bracket ERP evidence:
   - Original locally imported workbook: `bracket_purchase_data.xlsx`
   - Cleaned output: `data/processed/erp_cleaned.csv`
   - 97 source rows and 90 cleaned usable rows
   - 84 real `BR-*` bracket part IDs and 48 anonymized suppliers
   - Not yet joined to matching engineering/drawing attributes

Excluded real ERP rows follow normal data-quality rules: duplicates, missing price, and negative-quantity return/credit rows.

Fields:
- Part Number
- Description
- Supplier
- Country
- PO Date
- Quantity
- Unit Price
- Currency

Additional source fields retained in the raw converted file:
- Bracket type
- Material / process tag
- Tooling flag
- Original country code
- Total purchasing price in local currency

Supplier names are anonymized in processed ERP outputs.

---

## Market Intelligence Data

Planned:
- Live Steel Index
- Live FX Rates
- Labor Rates
- Energy Rates

Sources:
Publicly available market datasets and no-key APIs.

Current prototype sources:
- Steel index: FRED `WPU101`, Producer Price Index for Iron and Steel
- FX: Frankfurter USD/INR latest exchange rate API
- Live market input panel: sidebar shows steel index, USD/INR FX, source status, dates, and material adjustment factor
- Fallback behavior: baseline steel index and FX values are used if live APIs are unavailable

Target market-data fallback behavior for ML:

- Live commodity/FX available: use live values.
- Live unavailable and cache exists: use latest cached values.
- Live unavailable and no cache exists: use baseline values and mark prediction confidence lower.

---

## Engineering Drawing Data

The active prototype uses a synthetic 120-item sheet-metal engineering dataset because the real bracket purchase file contains procurement history but not matching drawing attributes. The 120-part expansion improves demonstration coverage, but it is not a replacement for real engineering evidence. Manufacturing drawings or engineering master data are still required for the real `BR-*` part IDs.

The implemented drawing-ingestion layer extracts fields from searchable PDFs or text-like files using regular-expression rules. The user selects the authoritative part ID, uploads a drawing, reviews and edits one staged row, and explicitly commits the reviewed values. The commit is accepted only after field validation and a dry-run of the complete pricing/ML pipeline. A successful commit stores the physical drawing under `data/drawings/committed/<part_id>/`, records its relative path, SHA-256 hash, and UTC commit timestamp in the active master and audit entry, then replaces the active master atomically. Streamlit reruns should-cost, supervised fair-price models, anomaly detection, clustering, SHAP, savings, and portfolio outputs. Image-only drawings still require OCR or a regenerated searchable text layer.

Engineering attributes required for the Cost Digital Twin:

- Material
- Thickness (Gauge)
- Weight
- Surface Finish
- Manufacturing Process
- Bend Count
- Hole Count
- Dimensions

This data will be used to construct the Cost Digital Twin.

---

# AI Tasks

## 1. Predictive Pricing

Goal:
Target state: predict ML Predicted Fair Price using validated drawing/OCR parameters, cleaned historical ERP data, supplier-region context, commodity index, and FX rates. Current state: train on the active synthetic part-level table while the real ERP-to-drawing join remains pending.

Pricing terms:

- ERP Price: actual paid/current supplier price.
- Should-Cost: explainable engineering cost estimate from the Cost Digital Twin.
- ML Predicted Fair Price: learned market-aligned price from cleaned ERP history, drawing/OCR features, supplier region, commodity index, and FX rates.

Target label strategy:

Raw ERP price should not be treated as direct truth because it may contain supplier inefficiency, poor negotiations, emergency buys, one-off tooling/freight, returns, and anomalous pricing. The ML target is a cleaned or adjusted fair-price label derived from ERP history after data cleaning, market normalization, and anomaly filtering/downweighting.

Implemented V1:

- `prepare_ml_fair_price_pipeline()` creates `ml_fair_price_label`.
- Abnormal ERP-to-should-cost gaps are clipped toward the should-cost anchor.
- Clean labels keep full training weight.
- High/low outlier labels are downweighted.
- Missing or blocked labels use the should-cost anchor with lower training weight.
- The model receives live/baseline `commodity_index` and `fx_rate` as features.
- The app displays prediction confidence, label quality, ML savings, ML-vs-should-cost variance, and SHAP-based procurement explanations.

Training-label preparation:

Raw ERP price
-> remove bad rows, returns, duplicates, and missing values
-> normalize currency and transaction date
-> remove or mark tooling, freight, emergency, and one-off purchase effects where identifiable
-> adjust historical prices to current commodity and FX basis
-> detect and downweight/remove anomalous transactions
-> train the ML model on cleaned fair-price labels

Prediction level:

Part-supplier-region level.

Reason:
Pure part-level prediction ignores sourcing-region cost differences. Pure transaction-level prediction can overfit PO noise. Part-supplier-region prediction lets the model estimate a fair price for the same drawing under different regional cost and market conditions.

V1 prediction output:

One current ML Predicted Fair Price. Time-aware fair-price trends can be generated later by replaying the model under historical commodity and FX inputs.

Mandatory V1 model inputs:

- material_grade
- thickness_mm
- length_mm
- width_mm
- weight_kg
- bend_count
- hole_count
- surface_finish
- part_category
- annual_volume
- supplier_region
- commodity_index
- fx_rate

OCR confidence handling:

- High OCR confidence and complete fields: allow ML prediction.
- Some missing or low-confidence non-critical fields: impute and show medium/low prediction confidence.
- Critical fields missing: block ML prediction and require manual correction.

Critical fields:

- material_grade
- weight_kg
- thickness_mm
- part_category
- supplier_region
- commodity_index
- fx_rate

Low-history or new-part handling:

Use a hybrid approach. ML is the primary fair-price predictor when similar historical ERP data exists. The Cost Digital Twin should act as a fallback or anchor when ERP history is sparse, so the prediction remains explainable and commercially defensible.

Algorithms:
- Linear Regression as the academic baseline
- Random Forest as the non-linear benchmark
- XGBoost as the primary tabular fair-price model with Gradient Boosting fallback for local compatibility
- SHAP TreeExplainer for part-level model explanations

Outputs:
- ML Predicted Fair Price
- Prediction confidence: High, Medium, or Low
- SHAP-based part-level explanation translated into procurement language
- Daily ML-predicted fair price
- Monthly ERP price versus daily ML fair-price trend
- Model fit metrics shown in the `AI Models` tab

---

## 2. Anomaly Detection

Goal:
Identify abnormal supplier pricing.

Algorithms:
- Isolation Forest
- Statistical Threshold Models

Outputs:
- Anomaly Score
- Flagged Parts
- Price gap percentage
- Savings opportunity

Important business rule:
- Qualified ML Savings = max(ERP Price - ML Predicted Fair Price, 0) x Annual Volume
- If ML Predicted Fair Price > ERP Price, Qualified Savings Opportunity = 0
- Should-Cost remains visible beside ML Predicted Fair Price as an explainable anchor and sanity check.

---

## 3. Supplier / Part Segmentation

Goal:
Benchmark suppliers and parts.

Algorithms:
- K-Means Clustering

Outputs:
- Supplier Clusters
- Part Clusters
- Cluster summary by ERP price, AI fair price, gap percentage, and qualified savings

---

# Cost Twin Model

Should Cost Components:

Should Cost =
Material Cost +
Energy Cost +
Labor Cost +
Bend/Hole Complexity Cost +
Surface Finish Cost +
Overhead +
Manual Template Adjustment Cost +
Supplier Margin

Where:

Material Cost:
Derived from steel grade, thickness, weight, live steel index, and live FX rate.

Formula:
Market Adjusted Steel Rate / kg =
Base Steel Rate / kg x
(Latest Steel Index / Base Steel Index) x
(Latest USD/INR / Base USD/INR)

Material Cost =
Weight kg x Market Adjusted Steel Rate / kg

Manual Template Adjustment Cost:
Derived from optional industry costing-template fields: scrap recovery, rejection allowance, tool maintenance, packing and forwarding, and tooling amortization. When these fields are missing, default demo assumptions keep the calculation executable.

Energy Cost:
Predicted using part-level energy consumption and energy tariff for supplier country of origin.

Labor Cost:
Predicted using part-level labor hours and labor rate for supplier country of origin.

Bends and Holes:
Predicted as machine operation cost using bend count, hole count, operation time assumptions, thickness factor, and country-level machine hour rate.

Surface Finish:
Included because sheet metal finishing is a real conversion cost. Estimated using blank area and finish type.

Overhead:
Applied to conversion cost using country-level overhead assumptions.

Supplier Margin:
Predicted using minimum industry margin by part category.

Qualified Savings Opportunity:
Calculated only when ERP/current supplier price exceeds ML Predicted Fair Price.

Formula:
Qualified ML Savings = max(ERP Price - ML Predicted Fair Price, 0) x Annual Volume

---

# Explainable AI Component

Unlike black-box pricing models, the system explains:

- Why a part is expensive.
- Which cost drivers contribute most.
- Why a supplier price is flagged.
- How supplier price movement compares with fair-market price movement.

This improves procurement trust and decision-making.

Implemented ML explanation approach:

- Use SHAP TreeExplainer for part-level prediction explanations.
- Translate SHAP drivers into procurement language.
- Example explanation: fair price is high mainly because of stainless material, higher thickness, high bend count, powder coating, and USA supplier region.
- Show the top driver and impact for each part in the AI Models tab. If SHAP is unavailable, the code falls back to tree feature importance with a marked method label.

Prediction confidence should consider:

- OCR completeness and field-level confidence.
- Similarity to historical ERP records.
- Market-data freshness.
- Model validation error.

Implemented V1 confidence rule:

- Start at three confidence points for a prediction with complete critical inputs.
- Deduct one point when fewer than two similar ERP-history records exist.
- Deduct one point when the ERP label is clipped, lifted, missing, or otherwise not a clean ERP label.
- Deduct one point when commodity/FX inputs are not live.
- Deduct one point when optional engineering fields are missing.
- Map three or more points to `High`, two points to `Medium`, and fewer than two points to `Low`; missing critical fields remain `Blocked`.

The strongest part-level SHAP feature and prediction confidence must not be interpreted as the same measure. SHAP identifies which feature most strongly moved one prediction relative to the model baseline and whether it increased or decreased the result. Confidence describes evidence sufficiency and freshness. For example, `Supplier_Region_USA` may strongly increase one predicted fair price while confidence remains Low because the ERP label required outlier adjustment and live commodity/FX inputs were unavailable.

---

# Expected Outputs

1. Fair Price Prediction
2. Price Gap Analysis
3. Supplier Benchmarking
4. Savings Opportunity Estimation
5. Procurement Dashboard
6. Clickable Part-Level Digital Twin Drill-Down
7. Cost Breakdown Percentage Chart
8. Monthly ERP Price vs Daily ML-Predicted Fair Price Chart
9. Live Market Inputs Panel
10. Review-Only Procurement Action Table
11. Same-Page Detailed Procurement Decision PDF
12. Committed Drawing Preview on the Part Detail Page

---

# Prototype Implementation

The current working prototype is a Streamlit application:

- GitHub repository: `https://github.com/Chetanshet1990/DTP`
- Main file: `app.py`
- ERP cleaning pipeline: `dtp/erp_pipeline.py`
- ERP cleaning script: `scripts/clean_erp_data.py`
- Bracket purchase importer: `scripts/import_bracket_purchase_data.py`
- ML models: `dtp/ml_models.py`
- Test files: `tests/test_erp_pipeline.py`, `tests/test_cost_model.py`, `tests/test_ml_models.py`

The application currently supports:

- Sheet metal-only should-cost analysis.
- Clickable `part_id` links in the portfolio table.
- Dedicated part detail page using URL format:
  `http://localhost:8501/?view=detail&part_id=SM-1003`
- Back navigation from part detail page to portfolio page.
- ERP raw data upload and cleaning.
- Supplier anonymization.
- Currency normalization to USD for ERP intelligence.
- Live steel index and USD/INR FX adjustment for material cost.
- Live steel index, USD/INR FX, source status, input dates, and material adjustment factor are visible in the sidebar.
- Portfolio-level ERP price versus predicted fair price comparison.
- Part-level cost breakdown.
- Part-level direct spend digital twin analysis.
- Manual should-cost template adjustments for scrap recovery, rejection, tool maintenance, packing/forwarding, and tooling amortization.
- AI model outputs using Linear Regression, Random Forest, XGBoost, Isolation Forest, and K-Means.
- SHAP TreeExplainer part-level ML explanations translated into procurement language.
- Supplier benchmarking.
- Geographic landed should-cost comparison.
- External deployment readiness through Streamlit Community Cloud.
- Persistent active engineering master with a recoverable baseline part master.
- Incomplete drawing rows remain available for ingestion but are blocked from cost and ML execution.
- Single-row drawing extraction review with manual correction before commit.
- Atomic drawing commit with full pricing/ML dry-run and automatic pipeline rerun.
- Session-backed workspace navigation that keeps `Upload Drawing` selected throughout upload, review, commit, and rerun events.
- Part-scoped upload state that clears the previous drawing preview and staged extraction whenever the selected part changes.
- Side-by-side PDF/image drawing preview and editable extracted-value table before commit.
- Cursor-following drawing magnification with 1.5x, 2x, and 3x selectable zoom levels.
- Vertical two-column engineering review table with one parameter per row beside the drawing preview.
- Complete portfolio table plus a separate `Review`-only action table sorted by highest ML gap.
- Explainability table restricted to positive qualified-savings opportunities.
- Single-row report selection that displays the chosen report below the table without opening a new browser tab.
- Detailed procurement PDF generation covering ERP-price diagnosis, cost evidence, negotiation steps, BATNA, XAI interpretation, confidence context, and a decision checklist.
- Server-side rendering of generated PDF pages to avoid blank browser-blocked iframe previews.
- Conditional committed-drawing preview below the drawing-derived cost-twin inputs on the part detail page.

The dedicated part detail page shows:

- ERP price.
- ML fair price.
- ML price gap percentage.
- ML qualified savings opportunity.
- Savings opportunity status.
- Cost breakdown by percentage.
- Manual template adjustment bucket.
- Monthly ERP price versus daily ML-predicted fair price.
- Auditable fair-price table with ERP data source labels.
- Committed drawing preview and drawing download when a stored file is available.
- Drawing-derived cost twin inputs.
- Market-adjusted steel rate per kg and material cost.
- Cost breakdown derived from live market-adjusted material cost.

Deployment route:

- Platform: Streamlit Community Cloud
- Repository: `Chetanshet1990/DTP`
- Branch: `main`
- Main file path: `app.py`
- Current deployment URL: `https://6zpfp22otgctvsk4laghpj.streamlit.app`
- Current deployment access note: URL is reachable but redirects to Streamlit authentication unless app visibility/access settings are opened.

Important deployment note:

The application uses relative links for part-level drill-down pages so that clickable `part_id` navigation works on both localhost and external Streamlit deployment URLs.

---

# Current Data Assets

The repository currently includes these data assets:

- `data/sample_parts.csv`
- `data/supplier_benchmarks.csv`
- `data/geo_cost_indices.csv`
- `data/erp_raw_sample.csv`
- `data/digital_twin_pricing_demo.xlsx`
- `data/processed/erp_cleaned.csv`
- `data/processed/supplier_anonymization_map.csv`
- `data/processed/erp_data_quality_report.csv`
- `data/processed/active_parts_master.csv`
- `data/drawings/SM-1001_searchable.pdf`

Current data split:
- `data/erp_raw_sample.csv`: 480 synthetic Review 3 ERP transactions aligned to the active `SM-*` demo parts.
- `data/sample_parts.csv`: synthetic 120-item engineering part master used for the current should-cost and ML demonstration.
- `data/processed/active_parts_master.csv`: persistent working copy loaded by the app; `SM-1001` drawing-derived fields are initially cleared and blocked until drawing review and commit.
- `data/processed/erp_cleaned.csv`: 90 cleaned and anonymized real ERP rows across 84 `BR-*` bracket IDs; currently separate from the synthetic engineering master.
- `data/digital_twin_pricing_demo.xlsx`: older small demonstration workbook retained as a reference/upload example.

Generated-output status:

- `outputs/ml_results/` currently reflects the earlier 30-part baseline and is stale relative to the active 120-part CSV files.
- Current model metrics are calculated on the training data. They demonstrate that the pipeline executes, but they are not held-out or time-based validation results.

The sample parts dataset uses sheet metal engineering fields:

- Part ID
- Part name
- Category
- Material
- Material grade
- Thickness
- Length
- Width
- Weight
- Bend count
- Hole count
- Surface finish
- Finish cost
- Material rate
- Energy use
- Labor hours
- Overhead percentage
- Supplier margin percentage
- Supplier
- Supplier region
- ERP price
- Annual volume

---

# Evaluation Metrics

## Regression

- MAE
- MAPE
- RMSE
- R² Score

Purpose:
Evaluate pricing prediction accuracy.

Validation split:
Planned but not yet implemented: use a time-based train/test split, training on older joined ERP transactions and testing on newer transactions to avoid future price leakage from commodity, FX, and supplier-price movement. Until this is implemented, reported regression metrics must be labelled as in-sample training metrics.

---

## Anomaly Detection

- Precision
- Recall
- F1 Score

Purpose:
Evaluate anomaly identification performance.

---

## Procurement Metrics

- Price Gap %
- Savings Potential
- Supplier Benchmark Score
- Top opportunity commercial reasonableness review

Purpose:
Measure business impact.

---

# Review 2 Feedback and Next Submission Plan

Panel feedback from the Phase I Second Review:

> Collect more real data and see the results.

Interpretation:
The review panel accepted the current prototype direction but expects stronger
evidence from real-world records. Review 3 expands the executable synthetic demo
from 30 to 120 parts and adds drawing-upload/procurement-explanation workflow,
but this does not replace the requested real-data validation. The next evidence
milestone must join real ERP records with real drawing/engineering attributes and
rerun the Cost Digital Twin, ML fair-price prediction, anomaly detection,
clustering, and savings analysis.

Decision for current context:
Keep the earlier Review 2 outputs as the 30-part prototype baseline and label the
120-part Review 3 data as an expanded synthetic demonstration. Do not describe
the expansion as completion of the panel's real-data request.

Required real-data collection target for next submission:

- 100+ real ERP purchase rows, ideally 200-500 rows.
- 30+ real sheet-metal part IDs, ideally 50-100 parts.
- Matching drawing or engineering attributes for the same part IDs.
- 5+ suppliers if available, with country/region/currency information.
- 6-12 months of PO history, ideally 12-24 months for time-based validation.
- 10-20 expert/manual should-cost validations for selected parts.

Data collection workbook:

- `submissions/review_2/Review_2_Real_Data_Collection_Template.xlsx`

Required next-submission output:

- Cleaned real ERP dataset summary.
- Joined ERP + engineering/drawing dataset summary.
- Updated Cost Digital Twin should-cost results.
- Updated ML fair-price results.
- Updated anomaly and cluster results.
- Comparison against the Review 2 prototype baseline.
- Expert/reference should-cost validation for selected parts.
- Clear statement of remaining limitations if complete drawing data is still
  not available.

---

# Expected Deliverables

Phase I:

- Literature Review
- Dataset Preparation
- Baseline Models
- Initial Dashboard

Phase II:

- Improved AI Models
- Cost Twin Framework
- Enhanced Explainability
- Final Research Paper

---

# Technology Stack

IDE:
- Visual Studio Code

Programming:
- Python

Libraries:
- pandas
- plotly
- streamlit
- openpyxl
- numpy
- scikit-learn
- xgboost
- shap

Version Control:
- Git
- GitHub

Repository:
- `https://github.com/Chetanshet1990/DTP`

Deployment:
- Streamlit Community Cloud
- Public URL: `https://6zpfp22otgctvsk4laghpj.streamlit.app`

---

# Development Continuity

This project will continue to be built incrementally based on user directions.

Working process:

1. Implement requested changes in the local repository.
2. Run focused validation checks.
3. Update relevant documentation.
4. Commit changes with a clear message.
5. Push to GitHub so external deployment can rebuild from `main`.

Current baseline validation commands:

```bash
python3 tests/test_erp_pipeline.py
python3 tests/test_cost_model.py
python3 tests/test_ml_models.py
PYTHONPYCACHEPREFIX=.pycache_check python3 -m py_compile app.py dtp/cost_model.py dtp/erp_pipeline.py dtp/market_data.py dtp/ml_models.py scripts/clean_erp_data.py scripts/import_bracket_purchase_data.py tests/test_erp_pipeline.py tests/test_cost_model.py tests/test_ml_models.py
```

Current run command:

```bash
streamlit run app.py
```

---

# Future Scope

Not included in current implementation:

- ERP Live Integration
- CAD Auto-Parsing
- Production OCR for image-only drawings and field-level OCR confidence scoring
- Cached commodity/FX history for time-aware fair-price trend modeling
- LLM Assistant
- Reinforcement Learning

These remain future enhancements.

---

# Research Positioning

This work is positioned as:

"An Explainable AI-based Cost Digital Twin framework for procurement pricing intelligence, combining engineering cost drivers, ERP data, predictive pricing, and anomaly detection to support strategic sourcing decisions."

---

# Current Status

Completed:
- Problem Definition
- Scope Refinement
- Feasibility Analysis
- Initial Literature Survey
- AI Task Identification
- Sheet Metal Dataset Schema
- ERP Data Cleaning Pipeline
- Real Bracket Purchase Data Import Pipeline
- Supplier Anonymization
- Currency Normalization
- Live Market Inputs Sidebar
- Streamlit Procurement Dashboard
- Part-Level Digital Twin Drill-Down
- Explainable Cost Breakdown
- Monthly ERP vs Daily ML Fair Price Timeline
- Linear Regression Pricing Model
- Random Forest Pricing Model
- XGBoost Pricing Model
- Executable ML Predicted Fair Price label pipeline
- Training sample weighting for noisy ERP-derived labels
- Commodity index and FX features passed into ML model
- Prediction readiness and confidence fields
- ML-vs-should-cost variance fields
- Manual should-cost template adjustment fields
- SHAP TreeExplainer part-level ML explanations
- Fair-price label quality summary in dashboard
- Isolation Forest Anomaly Detection
- K-Means Part Segmentation
- Supplier Benchmark View
- Geographic Cost Comparison
- Basic ERP Pipeline Test
- ML Model Test
- GitHub Repository Push
- Deployment-Ready Relative Navigation
- Savings Opportunity Business Rule Test

In Progress:
- Review 2 feedback response: join real ERP records to matching real drawing/engineering data and rerun results
- Replacement of synthetic engineering drawing attributes with real CAD/drawing-derived data
- ML Predicted Fair Price expansion from demo part-level data to joined OCR + transaction-level ERP data
- Dashboard Polish
- Literature Review Expansion
- External Streamlit Deployment

Next:
- Collect real ERP + drawing/engineering data using `submissions/review_2/Review_2_Real_Data_Collection_Template.xlsx`
- Rerun Cost Digital Twin and ML results after real-data collection
- Regenerate `outputs/ml_results/` for the active 120-part synthetic dataset and label those outputs clearly
- Compare joined real-data results against the Review 2 baseline and expanded Review 3 synthetic demo
- Add OCR feature validation and critical-field blocking rules
- Add time-based train/test validation with MAE, MAPE, RMSE, and R²
- Add LightGBM option alongside current XGBoost primary model with Linear Regression and Random Forest benchmarks
- Add cached live market data fallback before baseline fallback
- Final Thesis Evaluation Metrics
- Add public deployment URL after Streamlit Cloud deployment
