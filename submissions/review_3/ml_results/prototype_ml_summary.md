# Prototype ML Results Summary

- Parts evaluated: 120
- Prediction-ready parts: 120/120
- Isolation Forest anomalies: 51/120
- K-Means clusters: 3
- SHAP explanation coverage: 100.0%
- Best training R2: 0.999
- Lowest training MAE: INR 16.20
- Lowest training RMSE: INR 19.61

## Prediction Confidence

| label_quality_status | prediction_confidence | parts | avg_sample_weight |
| --- | --- | --- | --- |
| Clean ERP label | Low | 1 | 1.0 |
| Clean ERP label | Medium | 93 | 1.0 |
| ERP high outlier clipped to should-cost anchor | Low | 3 | 0.45 |
| ERP low outlier lifted toward should-cost anchor | Low | 23 | 0.45 |