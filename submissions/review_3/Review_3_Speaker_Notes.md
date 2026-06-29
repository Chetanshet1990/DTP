# Review 3 Speaker Notes

## Opening objective

Today I am showing the Review 2 feedback response: expanded data, drawing-specification extraction, and richer Explainable AI procurement answers.

## What changed from Review 2

- Expanded the demo dataset from 30 parts to 120 sheet-metal parts.
- Expanded ERP history from 97 raw rows to 480 ERP purchase rows.
- Added drawing extraction logic to read manufacturing drawing text/PDF content and fetch material grade, thickness, dimensions, bend count, hole count, and finish.
- Added procurement explanation output covering fair price, ERP purchased price, vendor, high-price reason, top price-increase feature, negotiation recommendation, savings opportunity, and BATNA.
- Regenerated ML result tables and charts inside `submissions/review_3/ml_results`.

## Review 3 result numbers

- Parts evaluated: 120.
- ERP transactions generated/processed: 480.
- Prediction-ready parts: 120/120.
- ERP annual spend: INR 120.94 crore.
- ML fair spend: INR 130.74 crore.
- Qualified savings opportunity: INR 29.57 lakh.
- Savings-eligible parts: 49.
- Should-cost review flags above 5 percent: 8.
- Isolation Forest anomaly flags: 51.
- K-Means clusters: 3.
- XAI explanation coverage: 100 percent.

## Drawing extraction defense

The current implementation handles text-based manufacturing drawing content. It extracts required costing specifications and reports confidence plus missing fields. For scanned image drawings, OCR can be added before the same parser. For CAD-native DWG/DXF, the same mapping logic remains valid once text/entities are exported.

## Explainable AI answer line

For each part, the system now answers: the ERP purchased price, the ML fair price, the vendor, why the ERP price is high, which feature is causing price increase, how procurement should negotiate, the savings opportunity, and the BATNA.

## Negotiation example line

The XAI output converts model features into procurement language. For example, if material is the top cost driver and ERP price is above fair price, the recommendation asks the vendor to bridge the price toward the ML fair price using material-cost evidence, while BATNA suggests re-quoting the cluster or alternate supplier around the fair/should-cost anchor.

## Limitation to state honestly

The expanded dataset is deterministic demo data generated to test the pipeline at a larger scale. The next real-world step is replacing demo-generated drawing fields with actual drawing/OCR extraction for matched real ERP part IDs.

## Files to show

- `submissions/review_3/ml_results/prototype_ml_summary.md`
- `submissions/review_3/ml_results/ml_priced_parts_results.csv`
- `submissions/review_3/ml_results/ml_procurement_explanations.csv`
- `dtp/drawing_extractor.py`
- `dtp/procurement_explain.py`
- `scripts/generate_review3_demo_data.py`

## If asked what is research here

The research contribution is the complete explainable pipeline: ERP purchase evidence plus drawing-derived engineering attributes are converted into should-cost, ML fair price, anomaly signals, supplier/geo comparison, and negotiation-ready explanations.
