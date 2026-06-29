# Review 2 Feedback Action Plan

## Panel feedback

Collect more real data and see the updated results.

## Decision

This will be addressed in the next submission. The current Review 2 prototype
results remain the baseline result set. The next submission will replace or
reduce synthetic engineering attributes by collecting real drawing/engineering
attributes for the same part IDs found in ERP purchase history.

## Data to collect before next submission

- 100+ real ERP purchase rows, preferably 200-500.
- 30+ real sheet-metal part IDs, preferably 50-100.
- Matching drawing/engineering attributes for the same part IDs.
- 5+ suppliers with country, region, and currency details.
- 6-12 months of purchase history, preferably 12-24 months.
- 10-20 expert/reference should-cost validations.

## Collection workbook

Use:

`submissions/review_2/Review_2_Real_Data_Collection_Template.xlsx`

## Next result rerun

After collecting the data:

1. Clean and anonymize the expanded ERP dataset.
2. Join ERP records with drawing/engineering attributes.
3. Rerun Cost Digital Twin should-cost calculation.
4. Rerun ML fair-price prediction.
5. Rerun Isolation Forest anomaly detection.
6. Rerun K-Means segmentation.
7. Compare new results with the Review 2 prototype baseline.
8. Validate selected generated should-cost templates against expert/reference templates.

## Statement for next review

Based on Review 2 feedback, the next phase focuses on increasing real-world
evidence by collecting more ERP purchase history and matching drawing-level cost
drivers, then rerunning the Cost Digital Twin and ML pipeline to compare updated
results against the current prototype baseline.
