# Review 3 Feedback Response

## Review 2 feedback

1. Create more data and see the results.
2. Add functionality to read manufacturing drawings and fetch required specifications.
3. Explainable AI must explain fair price, ERP price, vendor, high ERP-price reason, price-increase feature, negotiation path, savings opportunity, and BATNA.

## Response implemented

### 1. More data and updated results

Implemented `scripts/generate_review3_demo_data.py`, which creates:

- 120 sheet-metal part records.
- 480 ERP purchase transactions.
- Multiple suppliers and regions.
- Varied material grades, thicknesses, dimensions, bends, holes, finishes, prices, and annual volumes.

Updated results are saved in `submissions/review_3/ml_results`.

### 2. Manufacturing drawing specification extraction

Implemented `dtp/drawing_extractor.py`.

The parser extracts:

- `material_grade`
- `thickness_mm`
- `length_mm`
- `width_mm`
- `bend_count`
- `hole_count`
- `surface_finish`

The Streamlit app now includes an Upload Drawing tab that processes uploaded drawing files and shows extracted specifications, confidence, and missing fields.

### 3. Procurement-grade Explainable AI

Implemented `dtp/procurement_explain.py`.

The output file `ml_procurement_explanations.csv` now explains:

- ERP purchased price.
- ML fair price.
- Engineering should-cost.
- Vendor.
- Top feature causing price increase.
- Why ERP price is high or acceptable.
- Savings opportunity.
- Negotiation recommendation.
- BATNA.

## Validation

- `pytest -q`: 10 tests passed.
- `py_compile`: passed with local Python cache.
- ML outputs regenerated successfully into `submissions/review_3/ml_results`.
