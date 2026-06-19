from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
import os
import json
from typing import Optional

# Import local backend modules
from backend.data_generator import save_mock_data
from backend.data_validator import DataValidator
from backend.ecl_engine import ECLEngine
from backend.forecasting import ECLForecaster
from backend.monitoring import ModelMonitor

app = FastAPI(title="IFRS 9 ECL Analytics API", version="1.0.0")

# Enable CORS for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_PATH = "/Users/fhyfhy/Desktop/ifrs9-ecl-analytics"
DATA_DIR = os.path.join(BASE_PATH, "data")
PORTFOLIO_PATH = os.path.join(DATA_DIR, "portfolio_raw.csv")
MACRO_PATH = os.path.join(DATA_DIR, "macro_forecasts.csv")

# Core instances
validator = DataValidator()
engine = ECLEngine()
forecaster = ECLForecaster(engine)
monitor = ModelMonitor()

def load_data():
    """
    Helper function to load raw data. Generates data if it doesn't exist.
    """
    if not os.path.exists(PORTFOLIO_PATH) or not os.path.exists(MACRO_PATH):
        save_mock_data(BASE_PATH)
        
    try:
        portfolio_df = pd.read_csv(PORTFOLIO_PATH)
        macro_df = pd.read_csv(MACRO_PATH)
        return portfolio_df, macro_df
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading datasets: {str(e)}")

def load_clean_data():
    """
    Helper function to return validated, clean portfolio data.
    """
    df, _ = load_data()
    clean_df, _, _ = validator.validate(df)
    return clean_df

@app.on_event("startup")
def startup_event():
    # Pre-generate mock data on startup if missing
    load_data()

@app.post("/api/portfolio/generate")
def generate_portfolio():
    """
    Regenerates raw portfolio and macroeconomic data.
    """
    portfolio_df, macro_df = save_mock_data(BASE_PATH)
    return {
        "status": "success",
        "message": "Mock portfolio and macroeconomic forecasts regenerated successfully.",
        "records_count": len(portfolio_df)
    }

@app.get("/api/data/validate")
def get_validation_report():
    """
    Validates raw data and returns completeness, logical, and outlier reports.
    """
    df, _ = load_data()
    _, _, report = validator.validate(df)
    return report

@app.get("/api/ecl/calculate")
def calculate_ecl_endpoint(
    gdp: float = Query(0.025, description="GDP Growth Rate (e.g. 0.025 for 2.5%)"),
    unemp: float = Query(0.040, description="Unemployment Rate (e.g. 0.040 for 4.0%)"),
    infl: float = Query(0.020, description="Inflation Rate (e.g. 0.020 for 2.0%)"),
    w_base: float = Query(0.50, description="Base scenario weight"),
    w_opt: float = Query(0.30, description="Optimistic scenario weight"),
    w_pes: float = Query(0.20, description="Pessimistic scenario weight")
):
    """
    Calculates portfolio IFRS 9 ECL under given macroeconomic inputs and weights.
    """
    # Normalize weights to sum to 1
    total_w = w_base + w_opt + w_pes
    if total_w == 0:
        w_base, w_opt, w_pes = 0.50, 0.30, 0.20
    else:
        w_base /= total_w
        w_opt /= total_w
        w_pes /= total_w

    clean_df = load_clean_data()
    
    # Calculate ECL
    calc_df, summary = engine.calculate_ecl(
        clean_df, gdp, unemp, infl,
        base_scen_weight=w_base, opt_scen_weight=w_opt, pes_scen_weight=w_pes
    )
    
    # Expose a subset of raw results for displaying in frontend table (first 100 rows)
    results_sample = calc_df.head(100).to_dict(orient="records")
    
    return {
        "summary": summary,
        "parameters": {
            "gdp_pct": round(gdp * 100, 2),
            "unemployment_pct": round(unemp * 100, 2),
            "inflation_pct": round(infl * 100, 2),
            "weights": {"base": w_base, "optimistic": w_opt, "pessimistic": w_pes}
        },
        "sample": results_sample
    }

@app.get("/api/forecast")
def get_ecl_forecast():
    """
    Runs the 5-year macro-adjusted ECL forecast for budgeting and scenario planning.
    """
    clean_df = load_clean_data()
    _, macro_df = load_data()
    
    forecast = forecaster.run_5year_forecast(clean_df, macro_df)
    return forecast

@app.get("/api/monitoring")
def get_model_monitoring():
    """
    Calculates model validation metrics: PSI (hard-coded), ROC/AUC Gini, and Backtesting.
    """
    raw_df, _ = load_data()
    
    # For PSI: Compare origin rating (baseline) against current rating
    # Drop NaNs to clean up inputs
    valid_ratings = raw_df.dropna(subset=["origin_rating", "current_rating"])
    psi_report = monitor.calculate_psi(
        valid_ratings["origin_rating"],
        valid_ratings["current_rating"]
    )
    
    # For Discrimination & Backtesting, we need ECL outputs
    clean_df = load_clean_data()
    # Run calculation with baseline macro variables (0.025, 0.040, 0.020)
    calc_df, _ = engine.calculate_ecl(clean_df, 0.025, 0.040, 0.020)
    
    # Defaults in backtest: actual transition to Default rating (10)
    # Binary target for ROC-AUC is current_rating == 10
    actual_defaults = (calc_df["current_rating"] == 10).astype(int)
    discrimination_report = monitor.calculate_discrimination(
        calc_df["current_rating"],
        actual_defaults
    )
    
    backtest_report = monitor.calculate_backtesting(calc_df)
    
    return {
        "psi": psi_report,
        "discrimination": discrimination_report,
        "backtesting": backtest_report
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
