# Skill: Run RCA Analysis

This skill analyzes a dataset to detect anomalies and identify root causes using statistical methods and LLM reasoning.

## When to Use
Use this skill whenever the user wants to:
- Find anomalies or outliers in a metric
- Understand why a KPI dropped or spiked
- Perform root cause analysis on operational or business data
- Detect change points or sudden shifts in a time series

## How to Execute
1. Ensure data has been fetched first (call `fetch_trino_data` if not done yet).
2. Identify the **metric column** to analyze (ask user if not specified).
3. Identify the **time column** if the data is time-series (optional but recommended).
4. Choose the **detection method**:
   - `zscore` — best for normally distributed data, use threshold 2.0–3.0
   - `iqr` — best for skewed data with outliers, use threshold 1.5–2.5
   - `changepoint` — best for detecting sudden regime shifts in time series
5. Call `run_rca_analysis` with the chosen parameters.
6. Summarize findings: anomaly count, rate, and LLM-generated root cause explanation.

## Best Practices
- Start with `zscore` (default) and switch to `iqr` if data is heavily skewed.
- For time-series data, always provide the `time_column` for better anomaly context.
- After analysis, always suggest plotting the results to visualize anomalies.

## Example User Queries That Trigger This Skill
- "วิเคราะห์ RCA ของ error_rate"
- "หาสาเหตุที่ CPU usage พุ่งสูง"
- "Detect anomalies in the response_time column"
- "ทำไม revenue ถึงลดลงกะทันหัน?"
