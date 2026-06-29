# Review 2 Speaker Notes

## Opening objective

Today I am asking the panel to validate three things: whether the research gap is acceptable, whether the proposed pipeline and evaluation method are sufficient, and whether the should-cost Excel template fields match industry expectations.

## 30-minute flow

1. Recap problem statement and project aim: 3 minutes.
2. Show what changed since the last review and the requested should-cost template: 5 minutes.
3. Explain the 10 literature reviews by theme and then the base paper: 6 minutes.
4. Present the pipeline and system architecture as the answer to the literature gap: 6 minutes.
5. Show code and deployment/demo path: 4 minutes.
6. Present results and evaluation plan: 4 minutes.
7. Close with limitations, next steps, and panel feedback requested: 2 minutes.

## One-line project framing

ERP price tells what was paid. The Cost Digital Twin and ML fair-price model estimate what should be paid, explain the major cost drivers, and produce review-ready procurement evidence.

## Since last review

- The presentation now starts with a clear review objective.
- The requested should-cost Excel template is shown early, with the filled example before the blank structure.
- The literature review is grouped by themes instead of being presented as ten isolated summaries.
- The base paper is explained using adopted, modified, and extended points.
- The architecture is presented as the method that answers the research gap.
- The results are framed around generated output, validation, limitations, and next steps.

## Should-cost template line

The Excel template is not just an output file. It is the structured cost representation that the proposed pipeline populates from procurement and technical inputs, and it becomes the main artifact for validation.

## Research gap line

Existing work supports cost estimation, document/data extraction, and explainable AI separately. The gap is an end-to-end, domain-specific pipeline that converts procurement and technical inputs into a traceable should-cost template with explainable fair-price intelligence.

## Base paper defense

The base paper was selected because it is closest to the required cost-estimation logic. The other papers support individual components such as extraction, explainability, anomaly detection, and validation. My work adapts and extends the base idea into a complete pipeline with ERP cleaning, cost modeling, ML fair-price prediction, explainability, and deployment output.

## Current demo results

- Demo engineering parts: 30.
- Imported ERP source rows: 97.
- Clean usable ERP rows: 90.
- ERP annual spend: INR 13.63 crore.
- ML fair spend: INR 14.94 crore.
- Qualified ML savings signal: INR 23.05 lakh.
- Savings-eligible parts: 11.
- Should-cost gap flags above 5 percent: 5.
- Isolation Forest anomaly flags: 13.
- K-Means clusters: 3.

## Most important limitation

Real ERP purchase history is available and cleaned, but drawing-level engineering attributes are synthetic in the current prototype because the purchase file does not contain OCR/CAD parameters. This is the next integration gap, not a hidden weakness.

## Review 2 panel feedback received

The panel feedback is to collect more real data and see the updated results. This is now the main next-submission action item.

## Next submission response plan

- Collect more real ERP purchase rows for sheet-metal parts.
- Collect drawing or engineering attributes for the same part IDs.
- Join ERP transactions with drawing-level cost drivers.
- Rerun the Cost Digital Twin, ML fair-price prediction, anomaly detection, clustering, and savings analysis.
- Compare the new real-data results against the current Review 2 prototype baseline.
- Validate selected generated should-cost templates against expert/reference templates.
- Clearly state any remaining limitation if full drawing/OCR data is not available.

## Data collection target

- Minimum target: 100+ ERP rows, 30+ real part IDs, 5+ suppliers, and 10-20 expert/reference should-cost checks.
- Better target: 200-500 ERP rows, 50-100 part IDs, 12-24 months of history, and matching drawing attributes.
- Collection workbook: `submissions/review_2/Review_2_Real_Data_Collection_Template.xlsx`

## Evaluation answer

Correctness will be evaluated by comparing generated should-cost templates against manually prepared expert/reference templates, field by field. I will check extracted values, units, assumptions, completeness, cost-driver mapping, final cost variance, and explanation usefulness.

## If asked why this is research and not only software

The research contribution is not just the app. It is the structured methodology: identify the gap, build a pipeline from noisy procurement and technical inputs to a traceable should-cost template, generate explainable fair-price intelligence, and validate the output against expert/reference templates.

## Demo fallback

If the live deployment fails, continue with screenshots, one generated Excel output file, and the architecture slide. The goal is to prove the pipeline and results, not to spend review time debugging.
