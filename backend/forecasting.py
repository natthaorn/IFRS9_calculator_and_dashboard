import pandas as pd
import numpy as np
from backend.ecl_engine import ECLEngine

class ECLForecaster:
    """
    Forecasting & Stress Testing Engine:
    Projects portfolio ECL over a 5-year budget horizon (2026 - 2030)
    under 3 macroeconomic scenarios: Base, Optimistic, and Pessimistic.
    """
    def __init__(self, ecl_engine: ECLEngine):
        self.engine = ecl_engine

    def run_5year_forecast(self, df_portfolio: pd.DataFrame, df_macro: pd.DataFrame):
        """
        Simulates the 5-year portfolio behavior and ECL charge.
        
        Args:
            df_portfolio (pd.DataFrame): Cleaned portfolio data
            df_macro (pd.DataFrame): Macro forecast scenarios
        Returns:
            forecast_results: List of yearly ECL summaries per scenario
        """
        scenarios = ["Base", "Optimistic", "Pessimistic"]
        years = [2026, 2027, 2028, 2029, 2030]
        
        results = []
        
        for scenario in scenarios:
            # Filter macro forecasts for this scenario
            scen_macro = df_macro[df_macro["scenario"] == scenario]
            
            for i, year in enumerate(years):
                # Retrieve macro factors for this specific year
                macro_row = scen_macro[scen_macro["year"] == year]
                if len(macro_row) > 0:
                    gdp = macro_row["gdp_growth"].values[0]
                    unemp = macro_row["unemployment_rate"].values[0]
                    infl = macro_row["inflation_rate"].values[0]
                else:
                    # Fallback default values
                    gdp, unemp, infl = 0.025, 0.040, 0.020
                
                # Simulating portfolio amortization over the forecast horizon
                # Outstanding balances decay over time (e.g., straight line reduction of 15% per year)
                # This represents loan payouts, and the remaining term shrinks.
                temp_portfolio = df_portfolio.copy()
                decay_factor = max(0.2, 1.0 - 0.15 * i)
                temp_portfolio["outstanding_balance"] = (temp_portfolio["outstanding_balance"] * decay_factor).round(2)
                
                # Adjust remaining terms: subtract months elapsed
                elapsed_months = i * 12
                temp_portfolio["remaining_term_months"] = np.clip(
                    temp_portfolio["remaining_term_months"] - elapsed_months, 1, 360
                )
                
                # Run the ECL calculation for this year and scenario
                # For forecast, we set the scenario weight to 100% for the selected scenario
                if scenario == "Base":
                    w_base, w_opt, w_pes = 1.0, 0.0, 0.0
                elif scenario == "Optimistic":
                    w_base, w_opt, w_pes = 0.0, 1.0, 0.0
                else: # Pessimistic
                    w_base, w_opt, w_pes = 0.0, 0.0, 1.0
                    
                calc_df, summary = self.engine.calculate_ecl(
                    temp_portfolio, gdp, unemp, infl,
                    base_scen_weight=w_base, opt_scen_weight=w_opt, pes_scen_weight=w_pes
                )
                
                results.append({
                    "scenario": scenario,
                    "year": year,
                    "portfolio_balance": round(summary["total_portfolio"], 2),
                    "ecl": round(summary["total_ecl"], 2),
                    "coverage_pct": round(summary["overall_ecl_coverage_pct"], 4),
                    "gdp_growth_pct": round(gdp * 100, 2),
                    "unemployment_pct": round(unemp * 100, 2),
                    "inflation_pct": round(infl * 100, 2),
                    "stage1_balance": round(summary["stage_breakdown"]["stage1"]["balance"], 2),
                    "stage2_balance": round(summary["stage_breakdown"]["stage2"]["balance"], 2),
                    "stage3_balance": round(summary["stage_breakdown"]["stage3"]["balance"], 2),
                })
                
        return results

if __name__ == "__main__":
    from data_generator import generate_portfolio_data, generate_macro_forecast
    df_p = generate_portfolio_data()
    # Clean simple
    df_p = df_p.dropna().copy()
    df_p = df_p[df_p["eir"] > 0].copy()
    df_p = df_p[df_p["remaining_term_months"] > 0].copy()
    df_p = df_p[df_p["dpd"] >= 0].copy()
    df_p = df_p.reset_index(drop=True)
    
    df_m = generate_macro_forecast()
    
    engine = ECLEngine()
    forecaster = ECLForecaster(engine)
    forecast = forecaster.run_5year_forecast(df_p, df_m)
    print("Forecast output length:", len(forecast))
    print("First record:", forecast[0])
