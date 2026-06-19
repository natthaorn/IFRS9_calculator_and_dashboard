# IFRS 9 Expected Credit Loss (ECL) Calculator & Analytics Dashboard

This portfolio project is designed to showcase the technical execution and domain knowledge required for a **Credit Risk Quantitative / IFRS 9 ECL Analyst** position. It simulates a credit portfolio of 1,000 corporate, SME, and retail loans, applies data validation tests, calculates Point-in-Time Expected Credit Loss (ECL), runs multi-scenario forecasts for budget planning, and evaluates rating model stability using monitoring metrics.

---

## 🚀 How to Run the Project

The project is structured with a **FastAPI Python backend** for quantitative computations and an **interactive HTML/JS/CSS frontend** dashboard.

### Step 1: Run the Backend Server
Run the automated startup script from your terminal:
```bash
chmod +x /Users/fhyfhy/Desktop/ifrs9-ecl-analytics/start.sh
/Users/fhyfhy/Desktop/ifrs9-ecl-analytics/start.sh
```
This script will:
1. Create a Python virtual environment (`venv`).
2. Install dependencies (`fastapi`, `uvicorn`, `pandas`, `numpy`, `scikit-learn`, `scipy`).
3. Generate mock portfolio and macroeconomic data.
4. Launch the REST API server at `http://127.0.0.1:8000`.

### Step 2: Open the Dashboard
Once the server is running, open the single-page dashboard in your web browser:
- Open the file: [index.html](file:///Users/fhyfhy/Desktop/ifrs9-ecl-analytics/frontend/index.html) (double-click the file in Finder or open via browser).

---

## 📊 Methodology & Core Financial Concepts

### 1. Data Quality & Pre-Calculation Controls
IFRS 9 demands rigorous data quality standards. The data validation suite checks for:
- **Completeness:** Verifying that critical inputs like current ratings, outstanding balances, and terms are present.
- **Logical Consistency:** Rejecting records with negative Days Past Due (DPD), negative interest rates, or outstanding balances exceeding limits by more than 1.05x.
- **Outlier Detection:** Flagging abnormally high Effective Interest Rates (EIR > 35%) or high Loan-to-Value (LTV > 300%) reflecting potential data entry errors.
Dirty data is quarantined and logged, matching bank audit requirements.

### 2. Regulatory Stage Allocation (SICR)
Loans are allocated to three stages to determine ECL calculation depth:
- **Stage 1 (Performing):** DPD < 30 days and no Significant Increase in Credit Risk (SICR) since origination. Receives **12-month ECL**.
- **Stage 2 (Underperforming / SICR):** 30 <= DPD < 90 days OR experiencing SICR. Receives **Lifetime ECL**. SICR is triggered when:
  - **Relative PD Ratio:** Current PiT PD / Origination PiT PD $\ge 3.0x$.
  - **Absolute PD Difference:** Current PiT PD - Origination PiT PD $\ge 2.0\%$ (This absolute hurdle avoids triggering Stage 2 for low-risk accounts experiencing small absolute rating fluctuations, which is standard bank practice).
- **Stage 3 (Non-Performing / Default):** DPD $\ge 90$ days OR Current Rating is 10. Receives **Lifetime ECL**.

### 3. Merton-Vasicek Point-in-Time (PiT) PD
Through-The-Cycle (TTC) rating PDs are converted into Point-in-Time (PiT) PDs based on macroeconomic variables (GDP growth, unemployment, inflation) using the Merton-Vasicek single-factor model:

$$PiT\_PD = \Phi \left( \frac{\Phi^{-1}(TTC\_PD) - \sqrt{\rho} \cdot Y}{\sqrt{1 - \rho}} \right)$$

Where:
- $\Phi$ is the cumulative standard normal distribution.
- $\rho$ is the segment asset correlation (Basel-aligned: Retail = 0.05, SME = 0.12, Corporate = 0.20).
- $Y$ is the systematic economic index calculated from normalized macro variables.

### 4. Marginal vs. Conditional PD Curves
For Stage 2 and 3 loans, lifetime losses are calculated annually and discounted. The engine projects:
- **Conditional PD ($h_t$):** The hazard rate; default probability in year $t$ given survival up to year $t-1$.
- **Survival Probability ($S_t$):** Cumulative survival up to year $t$.
- **Marginal PD ($d_t$):** The probability of defaulting specifically in year $t$:
  $$d_t = S_{t-1} \times h_t$$
This marginal probability is used for year-by-year discounting.

### 5. Loss Given Default (LGD) with Haircuts
LGD is computed dynamically based on collateral backing:
- Secured portions receive a low LGD (e.g., 5% for cash, 15% for real estate).
- Unsecured portions receive a high baseline LGD (75%).
- Collaterals are adjusted using haircuts representing liquidation cost and time (Real Estate: 20%, Vehicle: 35%).
- Net LGD is the weighted average of secured and unsecured portions, capped between 10% and 85%.

### 6. Exposure at Default (EAD)
- **Term Loans:** EAD is amortized over the remaining term using straight-line amortization.
- **Revolving Loans (e.g., credit cards):** EAD is outstanding balance plus undrawn commitment multiplied by a Credit Conversion Factor (CCF) (Retail: 20%, SME: 50%, Corporate: 75%):
  $$EAD = Balance + CCF \times (Limit - Balance)$$

---

## 📈 Model Monitoring Suite

The model performance is evaluated through three key credit risk validation tools:
1. **Gini Coefficient / ROC-AUC:** Measures the rating model's ability to rank-order defaults. An AUC of >0.75 represents strong discrimination.
2. **Population Stability Index (PSI):** Measures the shift in rating distribution between credit origination (baseline) and today. It is calculated step-by-step in pure Python:
   $$PSI = \sum_{i=1}^{k} \left( Actual_i - Expected_i \right) \times \ln\left( \frac{Actual_i}{Expected_i} \right)$$
   - Where $Actual_i$ and $Expected_i$ are the actual and expected percentages for rating bin $i$.
   - $PSI < 0.1$: Stable (Green)
   - $0.1 \le PSI < 0.25$: Moderate shift (Amber)
   - $PSI \ge 0.25$: Significant shift requiring recalibration (Red)
3. **Backtesting:** Compares predicted 12-month PDs against actual observed defaults by rating grade to verify model calibration.
