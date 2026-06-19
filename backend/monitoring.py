import numpy as np
import pandas as pd
from sklearn.metrics import roc_curve, auc
import os

class ModelMonitor:
    """
    Implements IFRS 9 Model Validation and Monitoring metrics:
    1. Population Stability Index (PSI) - Hardcoded step-by-step logic
    2. Model Discrimination (ROC-AUC & Gini Coefficient)
    3. Backtesting (Actual vs. Expected Defaults by Rating)
    """
    def __init__(self):
        pass

    def calculate_psi(self, baseline_ratings: pd.Series, current_ratings: pd.Series):
        """
        Step-by-step hardcoded calculation of Population Stability Index (PSI).
        No external advanced ML packages used for this arithmetic to maintain transparency.
        
        Formula: PSI = sum( (Actual% - Expected%) * ln(Actual% / Expected%) )
        """
        # Align ratings into bins (1 to 10)
        bins = list(range(1, 11))
        
        # Calculate counts
        base_counts = baseline_ratings.value_counts().reindex(bins, fill_value=0)
        curr_counts = current_ratings.value_counts().reindex(bins, fill_value=0)
        
        total_base = sum(base_counts)
        total_curr = sum(curr_counts)
        
        # Avoid empty series division errors
        if total_base == 0: total_base = 1
        if total_curr == 0: total_curr = 1
        
        psi_details = []
        total_psi = 0.0
        
        for rating in bins:
            b_count = int(base_counts[rating])
            c_count = int(curr_counts[rating])
            
            # Expected (baseline) percentage
            b_pct = b_count / total_base
            # Actual (current) percentage
            c_pct = c_count / total_curr
            
            # Small smoothing offset (1e-5) to handle bins with 0 counts safely
            b_pct_smooth = max(b_pct, 1e-5)
            c_pct_smooth = max(c_pct, 1e-5)
            
            # PSI contribution
            psi_contribution = (c_pct_smooth - b_pct_smooth) * np.log(c_pct_smooth / b_pct_smooth)
            total_psi += psi_contribution
            
            psi_details.append({
                "rating": rating,
                "baseline_count": b_count,
                "baseline_pct": round(b_pct * 100, 2),
                "current_count": c_count,
                "current_pct": round(c_pct * 100, 2),
                "contribution": float(round(psi_contribution, 5))
            })
            
        # Determine status
        if total_psi < 0.10:
            status = "Green (Stable)"
            action = "No action required. The population distribution remains stable."
        elif total_psi < 0.25:
            status = "Amber (Moderate Shift)"
            action = "Monitor closely. Rating distribution is migrating. Investigate underwriting changes."
        else:
            status = "Red (Significant Shift)"
            action = "Model recalibration required. Ratings distribution has shifted significantly."
            
        return {
            "total_psi": float(round(total_psi, 5)),
            "status": status,
            "action_plan": action,
            "details": psi_details
        }

    def calculate_discrimination(self, current_ratings: pd.Series, actual_defaults: pd.Series):
        """
        Calculates ROC curve, Area Under Curve (AUC), and Gini Coefficient.
        Ratings are ranked 1 to 10 (higher means higher default risk).
        """
        # Drop missing values
        valid_mask = ~current_ratings.isna() & ~actual_defaults.isna()
        if valid_mask.sum() < 10:
            # Fallback for empty/low data testing
            return {"auc": 0.5, "gini": 0.0, "roc_curve": []}
            
        y_true = actual_defaults[valid_mask].astype(int).values
        # Rating is our score (higher rating -> higher default risk)
        y_scores = current_ratings[valid_mask].values
        
        # Calculate ROC
        fpr, tpr, thresholds = roc_curve(y_true, y_scores)
        auc_val = auc(fpr, tpr)
        gini_val = 2.0 * auc_val - 1.0
        
        # Format ROC coordinates for charting
        roc_data = []
        for f, t in zip(fpr, tpr):
            roc_data.append({"fpr": float(round(f, 4)), "tpr": float(round(t, 4))})
            
        return {
            "auc": float(round(auc_val, 4)),
            "gini": float(round(gini_val, 4)),
            "roc_curve": roc_data
        }

    def calculate_backtesting(self, df_results):
        """
        Compares Average predicted PD vs. Actual Observed Default Rates by rating grade.
        Expected defaults = Average 12-month PiT PD.
        Actual defaults = Defaults observed in current period (rating == 10).
        """
        # Exclude loans that started in default (if we want to backtest transitions)
        # For simplicity, default rate is the percentage of loans currently rated 10
        bins = list(range(1, 10)) # Ratings 1 to 9 (since 10 is default)
        
        backtest_results = []
        
        for rating in bins:
            # Subset of loans that were initially at this rating, or current loans minus defaults
            sub_df = df_results[df_results["origin_rating"] == rating]
            if len(sub_df) == 0:
                continue
                
            avg_pred_pd = sub_df["pit_pd_12m"].mean()
            actual_defaults = (sub_df["current_rating"] == 10).sum()
            actual_default_rate = actual_defaults / len(sub_df)
            
            backtest_results.append({
                "rating": rating,
                "loan_count": len(sub_df),
                "predicted_pd_pct": float(round(avg_pred_pd * 100, 3)),
                "actual_default_rate_pct": float(round(actual_default_rate * 100, 3)),
                "actual_default_count": int(actual_defaults)
            })
            
        return backtest_results

if __name__ == "__main__":
    # Test monitoring
    np.random.seed(42)
    base = pd.Series(np.random.choice(range(1, 11), size=500, p=[0.1, 0.2, 0.2, 0.2, 0.1, 0.1, 0.05, 0.03, 0.01, 0.01]))
    # Shift population to right (higher risk) for current
    curr = pd.Series(np.random.choice(range(1, 11), size=500, p=[0.05, 0.1, 0.15, 0.2, 0.2, 0.15, 0.08, 0.04, 0.02, 0.01]))
    
    monitor = ModelMonitor()
    psi_res = monitor.calculate_psi(base, curr)
    print("PSI:", psi_res["total_psi"])
    print("PSI Status:", psi_res["status"])
