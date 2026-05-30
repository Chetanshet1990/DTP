# PROJECT_CONTEXT.md

# Project Title

Explainable AI-Driven Cost Digital Twin for Procurement Intelligence and Price Anomaly Detection

---

# Project Overview

This project proposes an Explainable AI-driven procurement intelligence framework that combines cost modeling, machine learning, and anomaly detection to identify pricing inefficiencies in sheet metal sourcing.

The system aims to compare actual ERP purchase prices against AI-predicted fair prices and should-cost estimates, helping procurement teams identify negotiation opportunities and potential savings.

Qualified savings opportunity is counted only when predicted fair price is lower than ERP/current supplier spend. If predicted fair price is higher than ERP spend, the result is counted as ₹0 qualified savings.

The research focuses on reducing procurement cycle time from weeks of manual analysis to near real-time decision support.

---

# Problem Statement

ERP systems show historical purchase prices but do not indicate whether the paid price is fair, inflated, or market-aligned.

Global uncertainty arising from tariff wars, geopolitical tensions, repeated war escalations, commodity volatility, and inflation is creating significant pricing instability across global supply chains.

An AI-based procurement intelligence system is needed to predict fair prices, detect pricing anomalies, and explain cost gaps to support fact-based sourcing and negotiation decisions.

---

# Faculty Feedback Incorporated

## Digital Twin Clarification

Traditional digital twins represent physical or operational entities.

This project uses a Cost Digital Twin concept.

Definition:

"A Cost Digital Twin is a data-driven cost replica of a procured component constructed using engineering attributes, ERP pricing history, commodity indices, labor rates, energy costs, and supplier cost drivers."

---

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
Expected:
- 3 years procurement history

Fields:
- Part Number
- Description
- Supplier
- Country
- PO Date
- Quantity
- Unit Price
- Currency

Data will be anonymized.

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

---

## Engineering Drawing Data

Manufacturing drawings will be used to extract:

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
Predict fair market price.

Algorithms:
- Linear Regression
- Random Forest
- XGBoost

Outputs:
- Predicted Price
- Feature Importance
- Current ERP supplier price versus predicted fair price index, using the same selected-part prices that drive qualified savings

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
- Qualified Savings Opportunity = max(ERP Price - Predicted Fair Price, 0) x Annual Volume
- If Predicted Fair Price > ERP Price, Qualified Savings Opportunity = 0

---

## 3. Supplier / Part Segmentation

Goal:
Benchmark suppliers and parts.

Algorithms:
- K-Means Clustering

Outputs:
- Supplier Clusters
- Part Clusters

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

Energy Cost:
Manufacturing energy consumption.

Labor Cost:
Region-based labor rates.

Bend/Hole Complexity Cost:
Derived from bend count and hole count extracted from sheet metal drawings.

Surface Finish Cost:
Derived from finish type such as painted, powder coated, zinc plated, or passivated.

Overhead:
Factory and operational costs.

Supplier Margin:
Expected supplier profit margin.

Qualified Savings Opportunity:
Calculated only when ERP/current supplier price exceeds predicted fair price.

Formula:
Qualified Savings Opportunity = max(ERP Price - Predicted Fair Price, 0) x Annual Volume

---

# Explainable AI Component

Unlike black-box pricing models, the system explains:

- Why a part is expensive.
- Which cost drivers contribute most.
- Why a supplier price is flagged.
- How supplier price movement compares with fair-market price movement.

This improves procurement trust and decision-making.

---

# Expected Outputs

1. Fair Price Prediction
2. Price Gap Analysis
3. Supplier Benchmarking
4. Savings Opportunity Estimation
5. Procurement Dashboard
6. Clickable Part-Level Digital Twin Drill-Down
7. Cost Breakdown Percentage Chart
8. Supplier Price Development vs Fair Market Price Index Chart

---

# Prototype Implementation

The current working prototype is a Streamlit application:

- GitHub repository: `https://github.com/Chetanshet1990/DTP`
- Main file: `app.py`
- ERP cleaning pipeline: `dtp/erp_pipeline.py`
- ERP cleaning script: `scripts/clean_erp_data.py`
- Test file: `tests/test_erp_pipeline.py`

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
- Live steel index and FX are hidden model inputs rather than visible dashboard KPIs.
- Portfolio-level ERP price versus predicted fair price comparison.
- Part-level cost breakdown.
- Part-level direct spend digital twin analysis.
- Supplier benchmarking.
- Geographic landed should-cost comparison.
- What-if scenario modeling.
- External deployment readiness through Streamlit Community Cloud.

The dedicated part detail page shows:

- ERP price.
- Should-cost.
- Price gap percentage.
- Qualified savings opportunity.
- Savings opportunity status.
- Cost breakdown by percentage.
- Current ERP supplier price versus predicted fair price index.
- Drawing-derived cost twin inputs.
- Market-adjusted steel rate per kg and material cost.
- Cost breakdown derived from live market-adjusted material cost.

Deployment route:

- Platform: Streamlit Community Cloud
- Repository: `Chetanshet1990/DTP`
- Branch: `main`
- Main file path: `app.py`
- Current public deployment URL: to be added after Streamlit Cloud deployment is completed.

Important deployment note:

The application uses relative links for part-level drill-down pages so that clickable `part_id` navigation works on both localhost and external Streamlit deployment URLs.

---

# Current Data Assets

The repository currently includes demo datasets:

- `data/sample_parts.csv`
- `data/supplier_benchmarks.csv`
- `data/geo_cost_indices.csv`
- `data/erp_raw_sample.csv`
- `data/digital_twin_pricing_demo.xlsx`
- `data/processed/erp_cleaned.csv`
- `data/processed/supplier_anonymization_map.csv`
- `data/processed/erp_data_quality_report.csv`

The sample parts dataset uses sheet metal fields:

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
- RMSE
- R² Score

Purpose:
Evaluate pricing prediction accuracy.

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

Purpose:
Measure business impact.

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

Planned for later ML phases:
- numpy
- scikit-learn
- xgboost

Version Control:
- Git
- GitHub

Repository:
- `https://github.com/Chetanshet1990/DTP`

Deployment:
- Streamlit Community Cloud
- Public URL pending deployment

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
python3 -m py_compile app.py dtp/cost_model.py dtp/erp_pipeline.py scripts/clean_erp_data.py tests/test_erp_pipeline.py tests/test_cost_model.py
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
- OCR Extraction
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
- Supplier Anonymization
- Currency Normalization
- Streamlit Procurement Dashboard
- Part-Level Digital Twin Drill-Down
- Explainable Cost Breakdown
- Supplier Benchmark View
- Geographic Cost Comparison
- What-if Cost Scenario
- Basic ERP Pipeline Test
- GitHub Repository Push
- Deployment-Ready Relative Navigation
- Savings Opportunity Business Rule Test

In Progress:
- Dataset Refinement
- Dashboard Polish
- Literature Review Expansion
- External Streamlit Deployment

Next:
- Baseline Regression Model
- Isolation Forest Implementation
- Feature Importance / Explainability Model
- More Realistic Market Index Integration
- Final Thesis Evaluation Metrics
- Add public deployment URL after Streamlit Cloud deployment
