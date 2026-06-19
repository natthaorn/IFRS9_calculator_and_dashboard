import pandas as pd
import numpy as np

class DataValidator:
    """
    Implements IFRS 9 Data Quality Validation Rules:
    - Completeness (missing critical values like ratings or balances)
    - Logical Consistency (negative interest rates, maturity dates before reporting date)
    - Outlier Detection (extremely high exposure, LTV, or interest rates)
    """
    def __init__(self):
        self.rules = {
            "missing_rating": "Current Credit Rating is null or missing",
            "negative_eir": "Effective Interest Rate (EIR) is negative",
            "remaining_term_error": "Remaining Term is negative or zero",
            "negative_dpd": "Days Past Due (DPD) is negative",
            "balance_over_limit": "Outstanding Balance exceeds Credit Limit",
            "extreme_eir": "Effective Interest Rate (EIR) is abnormally high (> 35%)",
            "extreme_ltv": "Loan-to-Value (LTV) ratio is abnormally high (> 300%)"
        }

    def validate(self, df: pd.DataFrame):
        """
        Runs validation checks on the portfolio dataframe.
        Returns:
            clean_df: DataFrame with clean records
            dirty_df: DataFrame with flagged erroneous records
            report: Dict summarizing the findings of validation
        """
        issues = []
        
        # Make a copy to avoid side-effects
        validated_df = df.copy()
        validated_df["validation_status"] = "PASSED"
        validated_df["flagged_rules"] = ""
        
        # 1. Check missing ratings
        missing_rating_mask = validated_df["current_rating"].isna()
        
        # 2. Check negative EIR
        negative_eir_mask = validated_df["eir"] < 0
        
        # 3. Check remaining term error
        term_error_mask = validated_df["remaining_term_months"] <= 0
        
        # 4. Check negative DPD
        negative_dpd_mask = validated_df["dpd"] < 0
        
        # 5. Check balance over limit
        # For revolving products (where limit > 0 and term is short/revolving, or limit != balance)
        limit_error_mask = (validated_df["credit_limit"] > 0) & (validated_df["outstanding_balance"] > validated_df["credit_limit"] * 1.05)
        
        # 6. Extreme EIR (> 35%)
        extreme_eir_mask = validated_df["eir"] > 0.35
        
        # 7. Extreme LTV (> 300%)
        # LTV = outstanding_balance / collateral_value (if collateral_value > 0)
        ltv = np.where(validated_df["collateral_value"] > 0, validated_df["outstanding_balance"] / validated_df["collateral_value"], 0)
        extreme_ltv_mask = (validated_df["collateral_value"] > 0) & (ltv > 3.0)
        
        # Accumulate issues
        for idx in range(len(validated_df)):
            record_issues = []
            if missing_rating_mask.iloc[idx]:
                record_issues.append("missing_rating")
            if negative_eir_mask.iloc[idx]:
                record_issues.append("negative_eir")
            if term_error_mask.iloc[idx]:
                record_issues.append("remaining_term_error")
            if negative_dpd_mask.iloc[idx]:
                record_issues.append("negative_dpd")
            if limit_error_mask.iloc[idx]:
                record_issues.append("balance_over_limit")
            if extreme_eir_mask.iloc[idx]:
                record_issues.append("extreme_eir")
            if extreme_ltv_mask.iloc[idx]:
                record_issues.append("extreme_ltv")
                
            if record_issues:
                validated_df.loc[idx, "validation_status"] = "FAILED"
                validated_df.loc[idx, "flagged_rules"] = ",".join(record_issues)
                
        # Split clean and dirty
        clean_df = validated_df[validated_df["validation_status"] == "PASSED"].copy()
        dirty_df = validated_df[validated_df["validation_status"] == "FAILED"].copy()
        
        # Build JSON report
        total_records = len(df)
        failed_records = len(dirty_df)
        passed_records = len(clean_df)
        
        report = {
            "summary": {
                "total_records": total_records,
                "passed_records": passed_records,
                "failed_records": failed_records,
                "pass_rate_pct": round((passed_records / total_records) * 100, 2) if total_records > 0 else 0
            },
            "rule_breakdown": {
                "missing_rating": int(missing_rating_mask.sum()),
                "negative_eir": int(negative_eir_mask.sum()),
                "remaining_term_error": int(term_error_mask.sum()),
                "negative_dpd": int(negative_dpd_mask.sum()),
                "balance_over_limit": int(limit_error_mask.sum()),
                "extreme_eir": int(extreme_eir_mask.sum()),
                "extreme_ltv": int(extreme_ltv_mask.sum())
            },
            "dirty_sample": dirty_df.head(20).to_dict(orient="records")
        }
        
        return clean_df, dirty_df, report

if __name__ == "__main__":
    # Test validator
    from data_generator import generate_portfolio_data
    df = generate_portfolio_data()
    validator = DataValidator()
    clean_df, dirty_df, report = validator.validate(df)
    print("Clean records:", len(clean_df))
    print("Dirty records:", len(dirty_df))
    print("Pass Rate:", report["summary"]["pass_rate_pct"], "%")
    print("Breakdown:", report["rule_breakdown"])
