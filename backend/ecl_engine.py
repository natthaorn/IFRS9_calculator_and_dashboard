import numpy as np
import pandas as pd
from scipy.stats import norm
import os

# TTC PD Mapping for Ratings 1-10 (Rating 10 is default)
TTC_PD_MAP = {
    1: 0.0005,  # 0.05%
    2: 0.0015,  # 0.15%
    3: 0.0035,  # 0.35%
    4: 0.0075,  # 0.75%
    5: 0.0150,  # 1.50%
    6: 0.0300,  # 3.00%
    7: 0.0600,  # 6.00%
    8: 0.1200,  # 12.00%
    9: 0.2500,  # 25.00%
    10: 1.0000  # 100.00% (Default)
}

# Asset Correlations (rho) by Segment
RHO_MAP = {
    "Retail": 0.05,
    "SME": 0.12,
    "Corporate": 0.20
}

# Collateral Haircuts and Recovery Rates
COLLATERAL_RULES = {
    "Unsecured": {"haircut": 0.0, "lgd_secured": 0.75, "lgd_unsecured": 0.75},
    "Real Estate": {"haircut": 0.20, "lgd_secured": 0.15, "lgd_unsecured": 0.75},
    "Vehicle": {"haircut": 0.35, "lgd_secured": 0.30, "lgd_unsecured": 0.75},
    "Financial Asset": {"haircut": 0.05, "lgd_secured": 0.05, "lgd_unsecured": 0.75}
}

# CCF for revolving loans
CCF_MAP = {
    "Retail": 0.20,
    "SME": 0.50,
    "Corporate": 0.75
}

class ECLEngine:
    """
    Core IFRS 9 ECL Calculation Engine:
    - Stage allocation with Absolute and Relative PD thresholds
    - Vasicek TTC to PiT PD model (incorporating macroeconomic scenarios)
    - Marginal / Conditional PD curves
    - Collateralized LGD
    - EAD amortization and Credit Conversion Factors (CCF)
    """
    def __init__(self):
        pass

    @staticmethod
    def vasicek_pit_pd(ttc_pd, rho, y):
        """
        Merton-Vasicek Single Factor Model formula to calculate Point-in-Time (PiT) PD:
        PiT_PD = Phi( (Phi^-1(TTC_PD) - sqrt(rho) * Y) / sqrt(1 - rho) )
        
        Args:
            ttc_pd (float): Through-The-Cycle PD
            rho (float): Asset correlation coefficient
            y (float): Systematic macroeconomic index (higher Y means better economy -> lower PD)
        """
        if ttc_pd >= 1.0:
            return 1.0
        if ttc_pd <= 0.0:
            return 0.0
        
        # Phi^-1 (TTC_PD)
        z = norm.ppf(ttc_pd)
        
        # Numerator
        num = z - np.sqrt(rho) * y
        # Denominator
        den = np.sqrt(1 - rho)
        
        # Phi ( num / den )
        pit_pd = norm.cdf(num / den)
        return float(np.clip(pit_pd, 0.0001, 0.9999))

    @staticmethod
    def get_macro_index(gdp_growth, unemployment_rate, inflation_rate):
        """
        Maps normalized macro variables into a single systematic economic index Y.
        In a real bank, this comes from a regression model.
        Y is standard normal (mean 0, std 1). Higher Y is expansion, lower Y is recession.
        """
        # Baseline means and std (for normalization)
        # GDP: mean 2.5%, std 1.5%
        # Unemp: mean 4.0%, std 2.0%
        # Infl: mean 2.0%, std 1.0%
        z_gdp = (gdp_growth - 0.025) / 0.015
        z_unemp = (unemployment_rate - 0.040) / 0.020
        z_infl = (inflation_rate - 0.020) / 0.010
        
        # Y index = 0.5 * Z_gdp - 0.4 * Z_unemp - 0.1 * Z_infl
        # Coefficients represent the weight of each variable
        y = 0.5 * z_gdp - 0.4 * z_unemp - 0.1 * z_infl
        return float(y)

    def calculate_lgd(self, row):
        """
        Computes LGD based on collateral value, type, and outstanding balance.
        """
        col_type = row["collateral_type"]
        balance = row["outstanding_balance"]
        col_val = row["collateral_value"]
        
        rules = COLLATERAL_RULES.get(col_type, COLLATERAL_RULES["Unsecured"])
        haircut = rules["haircut"]
        lgd_sec = rules["lgd_secured"]
        lgd_unsec = rules["lgd_unsecured"]
        
        if col_val <= 0 or col_type == "Unsecured":
            return lgd_unsec
        
        # Adjusted Collateral Value (post-haircut)
        adj_col_val = col_val * (1 - haircut)
        
        # Secured portion vs Unsecured portion
        secured_amount = min(balance, adj_col_val)
        unsecured_amount = max(0.0, balance - secured_amount)
        
        # Weighted LGD
        weighted_lgd = (secured_amount * lgd_sec + unsecured_amount * lgd_unsec) / balance
        return float(np.clip(weighted_lgd, 0.10, 0.85))

    def calculate_lifetime_pd_curve(self, pit_pd_12m, segment, term_years):
        """
        Generates Conditional and Marginal PD curves for each year up to term_years.
        """
        # Segment decay parameter
        decay = 0.02 if segment == "Retail" else 0.04
        
        cond_pds = []
        survival_probs = [1.0] # S_0 = 1.0
        marginal_pds = []
        cumulative_pds = []
        
        for t in range(1, term_years + 1):
            # Conditional PD: h_t (decays slightly over time as survivors are typically lower risk)
            h_t = pit_pd_12m * ((1 - decay) ** (t - 1))
            h_t = np.clip(h_t, 0.0001, 0.9999)
            cond_pds.append(h_t)
            
            # Marginal PD: d_t = S_t-1 * h_t
            s_prev = survival_probs[-1]
            d_t = s_prev * h_t
            marginal_pds.append(d_t)
            
            # Survival Probability: S_t = S_t-1 * (1 - h_t)
            s_t = s_prev * (1 - h_t)
            survival_probs.append(s_t)
            
            # Cumulative PD: P_cum_t = sum(d_k for k=1..t)
            cumulative_pds.append(sum(marginal_pds))
            
        return cond_pds, marginal_pds, cumulative_pds

    def calculate_ecl(self, df_portfolio, gdp, unemp, infl, base_scen_weight=0.5, opt_scen_weight=0.3, pes_scen_weight=0.2):
        """
        Calculates IFRS 9 Expected Credit Loss for the portfolio.
        Returns the portfolio DataFrame with ECL columns and a summary of calculations.
        """
        results_df = df_portfolio.copy()
        
        # 1. Macro Indices for each scenario
        # In this calculation, we calculate the PIT PD for each macro scenario and weight them
        y_base = self.get_macro_index(gdp, unemp, infl)
        # Optimistic scenario: better GDP, lower unemployment
        y_opt = self.get_macro_index(gdp + 0.015, unemp - 0.01, infl + 0.002)
        # Pessimistic scenario: worse GDP, higher unemployment
        y_pes = self.get_macro_index(gdp - 0.035, unemp + 0.03, infl - 0.005)
        
        ecl_list = []
        stage_list = []
        pit_pd_12m_list = []
        lgd_list = []
        
        for idx, row in results_df.iterrows():
            segment = row["segment"]
            curr_rating = row["current_rating"]
            orig_rating = row["origin_rating"]
            dpd = row["dpd"]
            balance = row["outstanding_balance"]
            limit = row["credit_limit"]
            eir = row["eir"]
            rem_months = row["remaining_term_months"]
            term_years = int(np.ceil(rem_months / 12))
            
            # Retrieve TTC PDs
            ttc_pd_curr = TTC_PD_MAP.get(int(curr_rating) if not pd.isna(curr_rating) else 5, 0.015)
            ttc_pd_orig = TTC_PD_MAP.get(int(orig_rating), 0.015)
            rho = RHO_MAP.get(segment, 0.12)
            
            # Calculate Point-in-Time PDs for the 3 scenarios
            pit_pd_base = self.vasicek_pit_pd(ttc_pd_curr, rho, y_base)
            pit_pd_opt = self.vasicek_pit_pd(ttc_pd_curr, rho, y_opt)
            pit_pd_pes = self.vasicek_pit_pd(ttc_pd_curr, rho, y_pes)
            
            # Weighted 12-month PiT PD
            pit_pd_12m = base_scen_weight * pit_pd_base + opt_scen_weight * pit_pd_opt + pes_scen_weight * pit_pd_pes
            pit_pd_12m_list.append(pit_pd_12m)
            
            # Origin PiT PD (for SICR comparison, assuming base macro environment at origination)
            pit_pd_orig = self.vasicek_pit_pd(ttc_pd_orig, rho, 0.0) # Y=0 at origination
            
            # LGD
            lgd = self.calculate_lgd(row)
            lgd_list.append(lgd)
            
            # 2. Stage Allocation (SICR rules)
            # Relative PD Ratio
            pd_ratio = pit_pd_12m / max(0.0001, pit_pd_orig)
            # Absolute PD Difference
            pd_diff = pit_pd_12m - pit_pd_orig
            
            if curr_rating == 10 or dpd >= 90:
                stage = 3
            elif dpd >= 30 or pd_ratio >= 3.0 or pd_diff >= 0.02:
                stage = 2
            else:
                stage = 1
                
            stage_list.append(stage)
            
            # 3. EAD Amortization over lifetime
            is_revolving = (limit > balance) and (limit > 0)
            ccf = CCF_MAP.get(segment, 0.50)
            
            ead_curve = []
            for t in range(1, term_years + 1):
                if is_revolving:
                    # EAD for revolving includes balance + CCF * undrawn commitment
                    ead_t = balance + ccf * max(0.0, limit - balance)
                else:
                    # Amortizing EAD (straight-line)
                    ead_t = balance * (1.0 - (t - 1) / term_years)
                ead_curve.append(max(0.0, ead_t))
                
            # 4. ECL Calculation based on Stage
            # Stage 1: 12-month ECL (year 1 only)
            # Stage 2/3: Lifetime ECL (sum of discounted losses over years)
            ecl_val = 0.0
            
            # Base/Opt/Pes lifetime PD curves
            _, base_marg, _ = self.calculate_lifetime_pd_curve(pit_pd_base, segment, term_years)
            _, opt_marg, _ = self.calculate_lifetime_pd_curve(pit_pd_opt, segment, term_years)
            _, pes_marg, _ = self.calculate_lifetime_pd_curve(pit_pd_pes, segment, term_years)
            
            years_to_calc = 1 if stage == 1 else term_years
            
            for t in range(1, years_to_calc + 1):
                idx_t = t - 1
                ead_t = ead_curve[idx_t]
                
                # Weighted Marginal PD for year t
                marg_pd_t = (base_scen_weight * base_marg[idx_t] + 
                             opt_scen_weight * opt_marg[idx_t] + 
                             pes_scen_weight * pes_marg[idx_t])
                
                # Discount Factor
                df_t = (1 + eir) ** (-t)
                
                # ECL for year t
                ecl_val += ead_t * lgd * marg_pd_t * df_t
                
            ecl_list.append(round(ecl_val, 2))
            
        results_df["stage"] = stage_list
        results_df["pit_pd_12m"] = pit_pd_12m_list
        results_df["lgd"] = lgd_list
        results_df["ecl"] = ecl_list
        
        # Summary Analytics
        summary = {
            "total_portfolio": float(results_df["outstanding_balance"].sum()),
            "total_ecl": float(results_df["ecl"].sum()),
            "overall_ecl_coverage_pct": float(round((results_df["ecl"].sum() / results_df["outstanding_balance"].sum()) * 100, 4)),
            "stage_breakdown": {
                "stage1": {
                    "count": int((results_df["stage"] == 1).sum()),
                    "balance": float(results_df[results_df["stage"] == 1]["outstanding_balance"].sum()),
                    "ecl": float(results_df[results_df["stage"] == 1]["ecl"].sum()),
                    "coverage_pct": float(round((results_df[results_df["stage"] == 1]["ecl"].sum() / max(1, results_df[results_df["stage"] == 1]["outstanding_balance"].sum())) * 100, 4))
                },
                "stage2": {
                    "count": int((results_df["stage"] == 2).sum()),
                    "balance": float(results_df[results_df["stage"] == 2]["outstanding_balance"].sum()),
                    "ecl": float(results_df[results_df["stage"] == 2]["ecl"].sum()),
                    "coverage_pct": float(round((results_df[results_df["stage"] == 2]["ecl"].sum() / max(1, results_df[results_df["stage"] == 2]["outstanding_balance"].sum())) * 100, 4))
                },
                "stage3": {
                    "count": int((results_df["stage"] == 3).sum()),
                    "balance": float(results_df[results_df["stage"] == 3]["outstanding_balance"].sum()),
                    "ecl": float(results_df[results_df["stage"] == 3]["ecl"].sum()),
                    "coverage_pct": float(round((results_df[results_df["stage"] == 3]["ecl"].sum() / max(1, results_df[results_df["stage"] == 3]["outstanding_balance"].sum())) * 100, 4))
                }
            },
            "segment_breakdown": results_df.groupby("segment").agg(
                balance=("outstanding_balance", "sum"),
                ecl=("ecl", "sum")
            ).round(2).to_dict(orient="index")
        }
        
        return results_df, summary

if __name__ == "__main__":
    from data_generator import generate_portfolio_data
    df = generate_portfolio_data()
    # Clean data (simple drop for testing)
    df = df.dropna().copy()
    df = df[df["eir"] > 0].copy()
    df = df[df["remaining_term_months"] > 0].copy()
    df = df[df["dpd"] >= 0].copy()
    df = df.reset_index(drop=True)
    
    engine = ECLEngine()
    res, summary = engine.calculate_ecl(df, 0.025, 0.040, 0.020)
    print("ECL Summary:")
    print(f"Total Portfolio: {summary['total_portfolio']:,.2f}")
    print(f"Total ECL: {summary['total_ecl']:,.2f}")
    print(f"Coverage: {summary['overall_ecl_coverage_pct']}%")
    print("Stage 1 Balance:", summary["stage_breakdown"]["stage1"]["balance"])
    print("Stage 2 Balance:", summary["stage_breakdown"]["stage2"]["balance"])
    print("Stage 3 Balance:", summary["stage_breakdown"]["stage3"]["balance"])
