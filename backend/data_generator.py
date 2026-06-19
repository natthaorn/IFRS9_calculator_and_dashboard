import pandas as pd
import numpy as np
import os
import json

# Set seed for reproducibility
np.random.seed(42)

def generate_portfolio_data(n_records=1000):
    """
    Generates mock credit portfolio data with some intentional data quality errors
    to test the validation suite.
    """
    loan_ids = [f"LN{str(i).zfill(6)}" for i in range(1, n_records + 1)]
    
    # Segments with weights
    segments = np.random.choice(["Retail", "SME", "Corporate"], size=n_records, p=[0.6, 0.3, 0.1])
    
    # Initialize dictionary
    data = {
        "loan_id": loan_ids,
        "segment": segments,
        "origin_rating": np.random.randint(1, 6, size=n_records), # Initial ratings: 1 (best) to 5 (average)
    }
    
    # Current Rating (allow migration, rating 10 is default)
    # Ratings 1-9 are active, 10 is default
    current_ratings = []
    for r in data["origin_rating"]:
        migration = np.random.choice([-1, 0, 1, 2, 3, 5], p=[0.1, 0.5, 0.25, 0.1, 0.03, 0.02])
        curr = min(10, max(1, r + migration))
        current_ratings.append(curr)
    data["current_rating"] = current_ratings
    
    # Days Past Due (DPD) - correlated with current rating
    dpds = []
    for r in data["current_rating"]:
        if r == 10: # Default rating
            dpds.append(np.random.randint(90, 365))
        elif r >= 8:
            dpds.append(np.random.choice([np.random.randint(30, 89), np.random.randint(0, 29)], p=[0.7, 0.3]))
        elif r >= 5:
            dpds.append(np.random.choice([np.random.randint(0, 29), np.random.randint(30, 59)], p=[0.85, 0.15]))
        else:
            dpds.append(np.random.choice([0, np.random.randint(1, 15)], p=[0.95, 0.05]))
    data["dpd"] = dpds
    
    # Balances and Limits (based on segment)
    balances = []
    limits = []
    for s in segments:
        if s == "Retail":
            lim = np.random.choice([0, 10000, 20000, 50000], p=[0.6, 0.2, 0.1, 0.1]) # 0 means term loan (no limit)
            if lim == 0:
                bal = np.random.uniform(5000, 150000)
                lim = bal # for term loan, limit is balance at origination
            else:
                bal = np.random.uniform(0, lim)
        elif s == "SME":
            lim = np.random.choice([0, 250000, 500000, 1000000], p=[0.4, 0.3, 0.2, 0.1])
            if lim == 0:
                bal = np.random.uniform(50000, 750000)
                lim = bal
            else:
                bal = np.random.uniform(0, lim)
        else: # Corporate
            lim = np.random.choice([0, 5000000, 10000000, 20000000], p=[0.3, 0.4, 0.2, 0.1])
            if lim == 0:
                bal = np.random.uniform(1000000, 15000000)
                lim = bal
            else:
                bal = np.random.uniform(0, lim)
        balances.append(round(bal, 2))
        limits.append(round(lim, 2))
        
    data["outstanding_balance"] = balances
    data["credit_limit"] = limits
    
    # Interest rates (EIR) - inversely correlated with rating
    eirs = []
    for r in data["current_rating"]:
        base_eir = 0.02 + (r * 0.015) # higher risk, higher EIR
        eirs.append(round(np.random.normal(base_eir, 0.01), 4))
    data["eir"] = eirs
    
    # Initial Term and Remaining Term (months)
    initial_terms = []
    remaining_terms = []
    for s in segments:
        if s == "Retail":
            init = np.random.choice([12, 24, 36, 60, 120, 360]) # car, credit card, housing
        elif s == "SME":
            init = np.random.choice([12, 36, 60, 120])
        else: # Corporate
            init = np.random.choice([12, 24, 60, 120])
        
        rem = np.random.randint(1, init)
        initial_terms.append(int(init))
        remaining_terms.append(int(rem))
        
    data["initial_term_months"] = initial_terms
    data["remaining_term_months"] = remaining_terms
    
    # Collateral Type and Value
    collateral_types = []
    collateral_values = []
    for s, bal in zip(segments, balances):
        if s == "Retail":
            col_type = np.random.choice(["Unsecured", "Real Estate", "Vehicle"], p=[0.5, 0.2, 0.3])
        elif s == "SME":
            col_type = np.random.choice(["Unsecured", "Real Estate", "Financial Asset"], p=[0.2, 0.6, 0.2])
        else: # Corporate
            col_type = np.random.choice(["Unsecured", "Real Estate", "Financial Asset"], p=[0.1, 0.5, 0.4])
            
        if col_type == "Unsecured":
            col_val = 0.0
        elif col_type == "Real Estate":
            # Real Estate is typically over-collateralized (LTV 50-80%)
            col_val = bal / np.random.uniform(0.5, 0.8)
        elif col_type == "Vehicle":
            col_val = bal / np.random.uniform(0.7, 0.9)
        else: # Financial Asset (Cash, Deposits)
            col_val = bal / np.random.uniform(0.8, 1.0)
            
        collateral_types.append(col_type)
        collateral_values.append(round(col_val, 2))
        
    data["collateral_type"] = collateral_types
    data["collateral_value"] = collateral_values
    
    df = pd.DataFrame(data)
    
    # Inject SOME dirty data (exactly 2.5% of records have some errors)
    dirty_indices = np.random.choice(range(n_records), size=int(n_records * 0.025), replace=False)
    for idx in dirty_indices:
        err_type = np.random.choice(["missing_rating", "negative_eir", "remaining_term_error", "balance_over_limit", "negative_dpd"])
        if err_type == "missing_rating":
            df.loc[idx, "current_rating"] = np.nan
        elif err_type == "negative_eir":
            df.loc[idx, "eir"] = -0.05
        elif err_type == "remaining_term_error":
            df.loc[idx, "remaining_term_months"] = -5
        elif err_type == "balance_over_limit":
            df.loc[idx, "outstanding_balance"] = df.loc[idx, "credit_limit"] * 1.25
        elif err_type == "negative_dpd":
            df.loc[idx, "dpd"] = -10
            
    return df

def generate_macro_forecast():
    """
    Generates macroeconomic scenario forecasts for GDP Growth, Unemployment, and Inflation
    across 3 scenarios: Base, Optimistic, Pessimistic.
    """
    years = [2026, 2027, 2028, 2029, 2030]
    
    macro_data = {
        "Base": {
            "gdp_growth": [0.025, 0.027, 0.028, 0.030, 0.030],
            "unemployment_rate": [0.040, 0.039, 0.038, 0.037, 0.037],
            "inflation_rate": [0.021, 0.020, 0.019, 0.018, 0.018]
        },
        "Optimistic": {
            "gdp_growth": [0.042, 0.045, 0.045, 0.040, 0.038],
            "unemployment_rate": [0.032, 0.029, 0.028, 0.028, 0.030],
            "inflation_rate": [0.025, 0.023, 0.022, 0.021, 0.020]
        },
        "Pessimistic": {
            "gdp_growth": [-0.015, -0.025, 0.005, 0.015, 0.020],
            "unemployment_rate": [0.065, 0.085, 0.080, 0.070, 0.055],
            "inflation_rate": [0.045, 0.050, 0.035, 0.025, 0.022]
        }
    }
    
    # Format into a clean structure for the frontend/engine
    records = []
    for scenario, metrics in macro_data.items():
        for i, year in enumerate(years):
            records.append({
                "scenario": scenario,
                "year": year,
                "gdp_growth": metrics["gdp_growth"][i],
                "unemployment_rate": metrics["unemployment_rate"][i],
                "inflation_rate": metrics["inflation_rate"][i]
            })
            
    return pd.DataFrame(records)

def save_mock_data(base_path):
    """
    Saves generated csv files to the specified data folder
    """
    data_dir = os.path.join(base_path, "data")
    os.makedirs(data_dir, exist_ok=True)
    
    portfolio_df = generate_portfolio_data()
    macro_df = generate_macro_forecast()
    
    portfolio_df.to_csv(os.path.join(data_dir, "portfolio_raw.csv"), index=False)
    macro_df.to_csv(os.path.join(data_dir, "macro_forecasts.csv"), index=False)
    
    print(f"Generated and saved raw portfolio ({len(portfolio_df)} records) and macro scenarios.")
    return portfolio_df, macro_df

if __name__ == "__main__":
    save_mock_data("/Users/fhyfhy/Desktop/ifrs9-ecl-analytics")
