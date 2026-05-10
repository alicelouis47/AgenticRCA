# Skill: Fetch Data from Trino

This skill retrieves data from a Trino database by executing a SQL query.

## When to Use
Use this skill whenever the user wants to:
- Query or fetch data from a database or data warehouse
- Retrieve metrics, logs, or operational data for analysis
- Look up specific tables, schemas, or catalogs in Trino

## How to Execute
1. Identify the target table from the user's request. Ask if unclear.
2. Construct a valid SQL query using `catalog.schema.table` format.
3. Apply appropriate filters (WHERE clauses) based on user's time range or conditions.
4. Set a reasonable row limit (default 1000, max 5000 for large tables).
5. Call `fetch_trino_data` with the SQL query.

## Best Practices
- Always include a time filter if the table has a timestamp column (e.g., `WHERE event_time >= NOW() - INTERVAL '7' DAY`).
- Select only the columns needed for analysis — avoid `SELECT *` on wide tables.
- After fetching, summarize the columns and row count for the user.

## Example User Queries That Trigger This Skill
- "ดึงข้อมูล CPU usage 7 วันล่าสุดจาก Trino"
- "Query the orders table from hive.sales schema"
- "Get error logs from the last 24 hours"
