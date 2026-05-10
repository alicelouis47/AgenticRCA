# Skill: Plot RCA Results

This skill creates interactive Plotly visualizations of data and RCA findings.

## When to Use
Use this skill whenever the user wants to:
- Visualize data trends, distributions, or patterns
- See anomalies highlighted on a chart
- Create a dashboard or chart from fetched data
- Compare metrics visually

## How to Execute
1. Ensure data has been fetched (call `fetch_trino_data` if needed).
2. Choose the appropriate **chart type** based on the user's request:
   - `time_series` — for time-ordered metrics with a timestamp column
   - `bar` — for categorical comparisons
   - `histogram` — for value distribution analysis
   - `scatter` — for correlation between two numeric columns
   - `box` — for distribution and outlier visualization
   - `heatmap` — for correlation matrix of all numeric columns
3. Identify `x_column` (time or category) and `y_column` (the metric to plot).
4. Set `highlight_anomalies=true` if RCA has been run and the user wants to see anomalies on the chart.
5. Call `plot_rca_results` with the chosen parameters.

## Best Practices
- For time-series anomaly data, use `time_series` with `highlight_anomalies=true`.
- Use `heatmap` when user asks about correlations between multiple metrics.
- Always provide a meaningful chart `title`.
- After plotting, offer to export or explain the visible patterns.

## Example User Queries That Trigger This Skill
- "Plot the CPU usage over time"
- "แสดงกราฟ error_rate พร้อม anomaly"
- "สร้าง heatmap correlation ของ metrics ทั้งหมด"
- "Show me a histogram of response_time"
