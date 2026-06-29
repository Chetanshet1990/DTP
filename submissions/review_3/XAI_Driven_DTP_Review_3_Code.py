"""
XAI Driven DTP - Review 3 Code Submission

Project:
    Explainable AI-Based Fair Price Prediction and Cost Anomaly Detection
    for Sheet Metal Procurement

Purpose:
    This file is the Review 3 code-submission entry point. It points to the
    implemented project code in the repository and provides simple commands for
    checking, testing, generating results, and launching the Streamlit app.

Core implementation files:
    app.py
    dtp/cost_model.py
    dtp/erp_pipeline.py
    dtp/drawing_extractor.py
    dtp/market_data.py
    dtp/ml_models.py
    dtp/procurement_explain.py
    scripts/generate_review3_demo_data.py
    scripts/generate_ml_results.py

Usage:
    python3 submissions/review_3/XAI_Driven_DTP_Review_3_Code.py info
    python3 submissions/review_3/XAI_Driven_DTP_Review_3_Code.py check
    python3 submissions/review_3/XAI_Driven_DTP_Review_3_Code.py test
    python3 submissions/review_3/XAI_Driven_DTP_Review_3_Code.py data
    python3 submissions/review_3/XAI_Driven_DTP_Review_3_Code.py results
    python3 submissions/review_3/XAI_Driven_DTP_Review_3_Code.py app
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

SOURCE_FILES = [
    "app.py",
    "dtp/__init__.py",
    "dtp/cost_model.py",
    "dtp/drawing_extractor.py",
    "dtp/erp_pipeline.py",
    "dtp/market_data.py",
    "dtp/ml_models.py",
    "dtp/procurement_explain.py",
    "scripts/clean_erp_data.py",
    "scripts/import_bracket_purchase_data.py",
    "scripts/generate_review3_demo_data.py",
    "scripts/generate_ml_results.py",
    "tests/test_drawing_extractor.py",
    "tests/test_procurement_explain.py",
    "tests/test_cost_model.py",
    "tests/test_erp_pipeline.py",
    "tests/test_ml_models.py",
]


def run(command: list[str]) -> int:
    """Run a command from the project root and return its exit code."""
    print("$ " + " ".join(command))
    process = subprocess.run(command, cwd=PROJECT_ROOT)
    return process.returncode


def info() -> int:
    """Print the code-submission file map."""
    print("XAI Driven DTP - Review 3 Code Submission")
    print(f"Project root: {PROJECT_ROOT}")
    print("\nMain source files:")
    for relative_path in SOURCE_FILES:
        path = PROJECT_ROOT / relative_path
        status = "OK" if path.exists() else "MISSING"
        print(f"  [{status}] {relative_path}")
    print("\nKey data files:")
    for relative_path in [
        "data/sample_parts.csv",
        "data/erp_raw_sample.csv",
        "data/processed/erp_cleaned.csv",
        "data/digital_twin_pricing_demo.xlsx",
        "submissions/review_3/ml_results/ml_priced_parts_results.csv",
        "submissions/review_3/ml_results/ml_procurement_explanations.csv",
        "submissions/review_3/ml_results/prototype_ml_summary.md",
    ]:
        path = PROJECT_ROOT / relative_path
        status = "OK" if path.exists() else "MISSING"
        print(f"  [{status}] {relative_path}")
    return 0


def check() -> int:
    """Compile the project Python files."""
    return run(
        [
            sys.executable,
            "-m",
            "py_compile",
            *SOURCE_FILES,
        ]
    )


def test() -> int:
    """Run automated tests."""
    return run(["pytest", "-q"])


def results() -> int:
    """Regenerate ML result tables and graphs."""
    return run(
        [
            sys.executable,
            "scripts/generate_ml_results.py",
            "--output-dir",
            "submissions/review_3/ml_results",
        ]
    )


def data() -> int:
    """Regenerate the expanded Review 3 demo dataset."""
    return run([sys.executable, "scripts/generate_review3_demo_data.py"])


def app() -> int:
    """Launch the Streamlit dashboard."""
    return run([sys.executable, "-m", "streamlit", "run", "app.py"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Review 3 code-submission helper")
    parser.add_argument(
        "action",
        choices=["info", "check", "test", "data", "results", "app"],
        help="Action to run",
    )
    args = parser.parse_args()

    actions = {
        "info": info,
        "check": check,
        "test": test,
        "data": data,
        "results": results,
        "app": app,
    }
    return actions[args.action]()


if __name__ == "__main__":
    raise SystemExit(main())
