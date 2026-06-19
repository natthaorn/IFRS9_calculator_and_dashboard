// Backend API Base URL
const API_BASE = "http://127.0.0.1:8000/api";

// Global state for charts to allow updating/destroying
let charts = {};

// Loader helpers
const showLoader = () => document.getElementById("loading-overlay").classList.add("active");
const hideLoader = () => document.getElementById("loading-overlay").classList.remove("active");

// Formatter helper functions
const formatCurrency = (val) => {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(val);
};

const formatPercent = (val) => {
    return new Intl.NumberFormat('en-US', {
        style: 'percent',
        minimumFractionDigits: 2,
        maximumFractionDigits: 4
    }).format(val / 100);
};

// Initialize App
document.addEventListener("DOMContentLoaded", () => {
    // 1. Sidebar Tab Switching
    const navItems = document.querySelectorAll(".nav-item");
    const tabContents = document.querySelectorAll(".tab-content");
    
    navItems.forEach(item => {
        item.addEventListener("click", (e) => {
            e.preventDefault();
            const targetTab = item.getAttribute("data-tab");
            
            navItems.forEach(nav => nav.classList.remove("active"));
            item.classList.add("active");
            
            tabContents.forEach(content => {
                content.classList.remove("active");
                if(content.getAttribute("id") === targetTab) {
                    content.classList.add("active");
                }
            });
            
            // Trigger chart updates or refetches specific to tab if needed
            if (targetTab === "calculator") {
                triggerEclCalculation();
            } else if (targetTab === "forecast") {
                fetchForecast();
            } else if (targetTab === "monitoring") {
                fetchMonitoring();
            } else if (targetTab === "validation") {
                fetchValidation();
            } else if (targetTab === "overview") {
                fetchOverviewData();
            }
        });
    });

    // 2. Initialize Slider Inputs & Output Values
    const setupSlider = (sliderId, valId, isPercent = true) => {
        const slider = document.getElementById(sliderId);
        const valueBox = document.getElementById(valId);
        if (slider && valueBox) {
            slider.addEventListener("input", (e) => {
                const val = parseFloat(e.target.value);
                if (isPercent) {
                    if (sliderId.includes("unemp")) {
                        valueBox.textContent = (val / 10).toFixed(1) + "%";
                    } else if (sliderId.includes("gdp") || sliderId.includes("infl")) {
                        valueBox.textContent = (val / 10).toFixed(1) + "%";
                    } else {
                        valueBox.textContent = val + "%";
                    }
                } else {
                    valueBox.textContent = val;
                }
            });
            slider.addEventListener("change", triggerEclCalculation);
        }
    };

    setupSlider("slider-gdp", "val-gdp");
    setupSlider("slider-unemp", "val-unemp");
    setupSlider("slider-infl", "val-infl");
    
    // Staging scenario weights
    setupSlider("slider-w-base", "val-w-base");
    setupSlider("slider-w-opt", "val-w-opt");
    setupSlider("slider-w-pes", "val-w-pes");

    // 3. Regnerate Portfolio Button
    const btnRegen = document.getElementById("btn-regenerate-data");
    if(btnRegen) {
        btnRegen.addEventListener("click", async () => {
            showLoader();
            try {
                const res = await fetch(`${API_BASE}/portfolio/generate`, { method: "POST" });
                const data = await res.json();
                alert(data.message);
                // Refresh overview
                fetchOverviewData();
            } catch (err) {
                console.error("Error regenerating data:", err);
                alert("Failed to regenerate portfolio data.");
            } finally {
                hideLoader();
            }
        });
    }

    // Load initial overview data
    fetchOverviewData();
    fetchValidation(); // Load validation errors sample initially
});

// Destroy chart if already exists to prevent canvas reuse error
const safeDestroyChart = (chartId) => {
    if (charts[chartId]) {
        charts[chartId].destroy();
    }
};

// ================= Tab: Overview =================
async function fetchOverviewData() {
    showLoader();
    try {
        const res = await fetch(`${API_BASE}/ecl/calculate`);
        const data = await res.json();
        
        const summary = data.summary;
        
        // Update KPIs
        document.getElementById("kpi-total-exposure").textContent = formatCurrency(summary.total_portfolio);
        document.getElementById("kpi-stage1-ecl").textContent = formatCurrency(summary.stage_breakdown.stage1.ecl);
        document.getElementById("kpi-stage2-ecl").textContent = formatCurrency(summary.stage_breakdown.stage2.ecl);
        document.getElementById("kpi-stage3-ecl").textContent = formatCurrency(summary.stage_breakdown.stage3.ecl);
        
        document.getElementById("sub-stage1-coverage").textContent = `Coverage: ${summary.stage_breakdown.stage1.coverage_pct.toFixed(3)}%`;
        document.getElementById("sub-stage2-coverage").textContent = `Coverage: ${summary.stage_breakdown.stage2.coverage_pct.toFixed(3)}%`;
        document.getElementById("sub-stage3-coverage").textContent = `Coverage: ${summary.stage_breakdown.stage3.coverage_pct.toFixed(3)}%`;

        // 1. Chart: ECL Stage Allocation (Doughnut)
        safeDestroyChart("chart-ecl-stages");
        const ctxStages = document.getElementById("chart-ecl-stages").getContext("2d");
        charts["chart-ecl-stages"] = new Chart(ctxStages, {
            type: "doughnut",
            data: {
                labels: ["Stage 1 (Performing)", "Stage 2 (Underperforming)", "Stage 3 (Impaired)"],
                datasets: [{
                    data: [
                        summary.stage_breakdown.stage1.balance,
                        summary.stage_breakdown.stage2.balance,
                        summary.stage_breakdown.stage3.balance
                    ],
                    backgroundColor: ["#10b981", "#f59e0b", "#ef4444"],
                    borderColor: "#161c2d",
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: { color: "#f3f4f6", font: { family: "Outfit" } }
                    }
                }
            }
        });

        // 2. Chart: ECL Segment (Grouped Bar)
        safeDestroyChart("chart-ecl-segments");
        const segments = Object.keys(summary.segment_breakdown);
        const balances = segments.map(seg => summary.segment_breakdown[seg].balance);
        const ecls = segments.map(seg => summary.segment_breakdown[seg].ecl);
        
        const ctxSegments = document.getElementById("chart-ecl-segments").getContext("2d");
        charts["chart-ecl-segments"] = new Chart(ctxSegments, {
            type: "bar",
            data: {
                labels: segments,
                datasets: [
                    {
                        label: "Total Exposure ($)",
                        data: balances,
                        backgroundColor: "#3b82f6",
                        yAxisID: "y"
                    },
                    {
                        label: "ECL Charge ($)",
                        data: ecls,
                        backgroundColor: "#8b5cf6",
                        yAxisID: "y1"
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { ticks: { color: "#9ca3af" }, grid: { color: "rgba(255,255,255,0.05)" } },
                    y: {
                        type: "linear",
                        display: true,
                        position: "left",
                        ticks: { color: "#9ca3af" },
                        grid: { color: "rgba(255,255,255,0.05)" }
                    },
                    y1: {
                        type: "linear",
                        display: true,
                        position: "right",
                        ticks: { color: "#9ca3af" },
                        grid: { drawOnChartArea: false } // only want the grid lines for one axis
                    }
                },
                plugins: {
                    legend: {
                        labels: { color: "#f3f4f6", font: { family: "Outfit" } }
                    }
                }
            }
        });

    } catch (err) {
        console.error("Error loading overview data:", err);
    } finally {
        hideLoader();
    }
}

// ================= Tab: Data Quality =================
async function fetchValidation() {
    try {
        const res = await fetch(`${API_BASE}/data/validate`);
        const report = await res.json();
        
        // Update KPIs
        document.getElementById("kpi-pass-rate").textContent = report.summary.pass_rate_pct.toFixed(2) + "%";
        document.getElementById("kpi-validation-status").textContent = `Passed: ${report.summary.passed_records} / Total: ${report.summary.total_records}`;
        document.getElementById("kpi-failed-count").textContent = report.summary.failed_records;
        document.getElementById("kpi-missing-ratings").textContent = report.rule_breakdown.missing_rating;
        document.getElementById("kpi-logical-errors").textContent = 
            report.rule_breakdown.negative_eir + 
            report.rule_breakdown.remaining_term_error + 
            report.rule_breakdown.negative_dpd +
            report.rule_breakdown.balance_over_limit;

        // Chart: Failed Rules Breakdown (Horizontal Bar)
        safeDestroyChart("chart-validation-rules");
        const rules = Object.keys(report.rule_breakdown);
        const ruleCounts = Object.values(report.rule_breakdown);
        
        const ctxRules = document.getElementById("chart-validation-rules").getContext("2d");
        charts["chart-validation-rules"] = new Chart(ctxRules, {
            type: "bar",
            data: {
                labels: [
                    "Missing Rating",
                    "Negative EIR",
                    "Term <= 0",
                    "Negative DPD",
                    "Over Limit",
                    "EIR > 35%",
                    "LTV > 300%"
                ],
                datasets: [{
                    label: "Failed Records Count",
                    data: ruleCounts,
                    backgroundColor: "rgba(239, 68, 68, 0.75)",
                    borderColor: "#ef4444",
                    borderWidth: 1
                }]
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { ticks: { color: "#9ca3af", stepSize: 1 }, grid: { color: "rgba(255,255,255,0.05)" } },
                    y: { ticks: { color: "#9ca3af" }, grid: { color: "rgba(255,255,255,0.05)" } }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });

        // Populate dirty table
        const tbody = document.getElementById("validation-dirty-tbody");
        tbody.innerHTML = "";
        
        if (report.dirty_sample.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;">No dirty records found in portfolio.</td></tr>`;
        } else {
            report.dirty_sample.forEach(row => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td>${row.loan_id}</td>
                    <td>${row.segment}</td>
                    <td>${formatCurrency(row.outstanding_balance)}</td>
                    <td>${isNaN(row.current_rating) || row.current_rating === null ? `<span style="color:#ef4444;">Null</span>` : row.current_rating}</td>
                    <td class="${row.dpd < 0 ? 'red' : ''}">${row.dpd}</td>
                    <td>${(row.eir * 100).toFixed(2)}%</td>
                    <td>${row.remaining_term_months}</td>
                    <td><span class="badge failed">${row.flagged_rules}</span></td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (err) {
        console.error("Error loading validation report:", err);
    }
}

// ================= Tab: ECL Engine / Interactive Calculator =================
async function triggerEclCalculation() {
    const gdpVal = parseFloat(document.getElementById("slider-gdp").value) / 1000;
    const unempVal = parseFloat(document.getElementById("slider-unemp").value) / 1000;
    const inflVal = parseFloat(document.getElementById("slider-infl").value) / 1000;
    
    const wBase = parseFloat(document.getElementById("slider-w-base").value);
    const wOpt = parseFloat(document.getElementById("slider-w-opt").value);
    const wPes = parseFloat(document.getElementById("slider-w-pes").value);
    
    try {
        const query = `gdp=${gdpVal}&unemp=${unempVal}&infl=${inflVal}&w_base=${wBase}&w_opt=${wOpt}&w_pes=${wPes}`;
        const res = await fetch(`${API_BASE}/ecl/calculate?${query}`);
        const data = await res.json();
        
        const summary = data.summary;
        
        // Update Live KPIs
        document.getElementById("calc-kpi-total-ecl").textContent = formatCurrency(summary.total_ecl);
        document.getElementById("calc-kpi-coverage").textContent = `Coverage: ${summary.overall_ecl_coverage_pct.toFixed(3)}%`;
        
        document.getElementById("calc-kpi-s1-bal").textContent = formatCurrency(summary.stage_breakdown.stage1.balance);
        document.getElementById("calc-kpi-s1-count").textContent = `Count: ${summary.stage_breakdown.stage1.count}`;
        
        document.getElementById("calc-kpi-s2-bal").textContent = formatCurrency(summary.stage_breakdown.stage2.balance);
        document.getElementById("calc-kpi-s2-count").textContent = `Count: ${summary.stage_breakdown.stage2.count}`;
        
        document.getElementById("calc-kpi-s3-bal").textContent = formatCurrency(summary.stage_breakdown.stage3.balance);
        document.getElementById("calc-kpi-s3-count").textContent = `Count: ${summary.stage_breakdown.stage3.count}`;
        
        // Populate Calculator Table sample
        const tbody = document.getElementById("calc-results-tbody");
        tbody.innerHTML = "";
        
        data.sample.forEach(row => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><strong>${row.loan_id}</strong></td>
                <td>${row.segment}</td>
                <td>${formatCurrency(row.outstanding_balance)}</td>
                <td>${row.current_rating}</td>
                <td>${row.dpd}</td>
                <td>${(row.pit_pd_12m * 100).toFixed(3)}%</td>
                <td>${(row.lgd * 100).toFixed(1)}%</td>
                <td><span class="badge stage${row.stage}">Stage ${row.stage}</span></td>
                <td><strong>${formatCurrency(row.ecl)}</strong></td>
            `;
            tbody.appendChild(tr);
        });
        
    } catch (err) {
        console.error("Error calculating ECL live:", err);
    }
}

// ================= Tab: Forecasting =================
async function fetchForecast() {
    showLoader();
    try {
        const res = await fetch(`${API_BASE}/forecast`);
        const forecastList = await res.json();
        
        // Group forecasts by scenario
        const baseData = forecastList.filter(f => f.scenario === "Base");
        const optData = forecastList.filter(f => f.scenario === "Optimistic");
        const pesData = forecastList.filter(f => f.scenario === "Pessimistic");
        
        const years = baseData.map(f => f.year);
        
        // Update Chart: Forecast Line
        safeDestroyChart("chart-forecast");
        const ctxForecast = document.getElementById("chart-forecast").getContext("2d");
        charts["chart-forecast"] = new Chart(ctxForecast, {
            type: "line",
            data: {
                labels: years,
                datasets: [
                    {
                        label: "Base Case",
                        data: baseData.map(f => f.ecl),
                        borderColor: "#3b82f6",
                        backgroundColor: "rgba(59, 130, 246, 0.1)",
                        fill: false,
                        tension: 0.1
                    },
                    {
                        label: "Optimistic Case",
                        data: optData.map(f => f.ecl),
                        borderColor: "#10b981",
                        backgroundColor: "rgba(16, 185, 129, 0.1)",
                        fill: false,
                        tension: 0.1
                    },
                    {
                        label: "Pessimistic (Stress Case)",
                        data: pesData.map(f => f.ecl),
                        borderColor: "#ef4444",
                        backgroundColor: "rgba(239, 68, 68, 0.1)",
                        fill: false,
                        tension: 0.1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { ticks: { color: "#9ca3af" }, grid: { color: "rgba(255,255,255,0.05)" } },
                    y: { ticks: { color: "#9ca3af" }, grid: { color: "rgba(255,255,255,0.05)" } }
                },
                plugins: {
                    legend: { labels: { color: "#f3f4f6", font: { family: "Outfit" } } }
                }
            }
        });

        // Populate Table
        const tbody = document.getElementById("forecast-tbody");
        tbody.innerHTML = "";
        
        forecastList.forEach(row => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><strong>${row.scenario}</strong></td>
                <td>${row.year}</td>
                <td>${row.gdp_growth_pct.toFixed(1)}%</td>
                <td>${row.unemployment_pct.toFixed(1)}%</td>
                <td>${formatCurrency(row.portfolio_balance)}</td>
                <td><strong>${formatCurrency(row.ecl)}</strong></td>
                <td>${row.coverage_pct.toFixed(3)}%</td>
                <td>${formatCurrency(row.stage1_balance)}</td>
                <td>${formatCurrency(row.stage2_balance)}</td>
                <td>${formatCurrency(row.stage3_balance)}</td>
            `;
            tbody.appendChild(tr);
        });
        
    } catch (err) {
        console.error("Error loading forecast data:", err);
    } finally {
        hideLoader();
    }
}

// ================= Tab: Model Monitoring =================
async function fetchMonitoring() {
    showLoader();
    try {
        const res = await fetch(`${API_BASE}/monitoring`);
        const monitorData = await res.json();
        
        const psi = monitorData.psi;
        const disc = monitorData.discrimination;
        const backtest = monitorData.backtesting;
        
        // Update KPIs & Text
        document.getElementById("monitor-psi-val").textContent = psi.total_psi.toFixed(5);
        
        const psiStatusBox = document.getElementById("monitor-psi-status");
        psiStatusBox.textContent = psi.status;
        psiStatusBox.className = "metric-value";
        if (psi.status.includes("Green")) psiStatusBox.classList.add("green");
        else if (psi.status.includes("Amber")) psiStatusBox.classList.add("amber");
        else psiStatusBox.classList.add("red");
        
        document.getElementById("monitor-auc-val").textContent = disc.auc.toFixed(4);
        document.getElementById("monitor-gini-val").textContent = disc.gini.toFixed(4);
        
        document.getElementById("monitor-action-text").textContent = psi.action_plan;
        
        // 1. Render ROC Curve
        safeDestroyChart("chart-roc");
        const rocCoords = disc.roc_curve;
        const ctxRoc = document.getElementById("chart-roc").getContext("2d");
        
        charts["chart-roc"] = new Chart(ctxRoc, {
            type: "line",
            data: {
                datasets: [
                    {
                        label: "Rating Model ROC",
                        data: rocCoords.map(c => ({ x: c.fpr, y: c.tpr })),
                        borderColor: "#eab308",
                        backgroundColor: "rgba(234, 179, 8, 0.1)",
                        fill: true,
                        tension: 0.1,
                        showLine: true
                    },
                    {
                        label: "Random Guess (0.50)",
                        data: [{ x: 0, y: 0 }, { x: 1, y: 1 }],
                        borderColor: "rgba(255,255,255,0.2)",
                        borderDash: [5, 5],
                        fill: false,
                        showLine: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { type: "linear", min: 0, max: 1, ticks: { color: "#9ca3af" }, grid: { color: "rgba(255,255,255,0.05)" } },
                    y: { type: "linear", min: 0, max: 1, ticks: { color: "#9ca3af" }, grid: { color: "rgba(255,255,255,0.05)" } }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });

        // 2. Render Step-by-Step PSI Table
        const psiTbody = document.getElementById("monitor-psi-tbody");
        psiTbody.innerHTML = "";
        
        psi.details.forEach(row => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>Rating Bin ${row.rating}</td>
                <td>${row.baseline_pct.toFixed(2)}%</td>
                <td>${row.current_pct.toFixed(2)}%</td>
                <td><strong>${row.contribution.toFixed(5)}</strong></td>
            `;
            psiTbody.appendChild(tr);
        });

        // 3. Render Backtesting Bar Chart
        safeDestroyChart("chart-backtest");
        const ratings = backtest.map(b => `Rating ${b.rating}`);
        const predPDs = backtest.map(b => b.predicted_pd_pct);
        const actualDRs = backtest.map(b => b.actual_default_rate_pct);
        
        const ctxBacktest = document.getElementById("chart-backtest").getContext("2d");
        charts["chart-backtest"] = new Chart(ctxBacktest, {
            type: "bar",
            data: {
                labels: ratings,
                datasets: [
                    {
                        label: "Expected Avg PD (%)",
                        data: predPDs,
                        backgroundColor: "rgba(59, 130, 246, 0.75)"
                    },
                    {
                        label: "Actual Observed Default Rate (%)",
                        data: actualDRs,
                        backgroundColor: "rgba(236, 72, 153, 0.75)"
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { ticks: { color: "#9ca3af" }, grid: { color: "rgba(255,255,255,0.05)" } },
                    y: { ticks: { color: "#9ca3af" }, grid: { color: "rgba(255,255,255,0.05)" } }
                },
                plugins: {
                    legend: { labels: { color: "#f3f4f6", font: { family: "Outfit" } } }
                }
            }
        });
        
    } catch (err) {
        console.error("Error loading model monitoring report:", err);
    } finally {
        hideLoader();
    }
}
