# AgentRCA

AI Agent ระบบ Root Cause Analysis แบบ modular รองรับ **skill.md** — ดึงข้อมูลจาก Trino → วิเคราะห์ RCA → Plot ผลลัพธ์

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set API key
copy .env.example .env
# แก้ OPENAI_API_KEY ใน .env

# 3. Configure Trino (optional — or use CSV upload)
# แก้ config/trino_config.csv ให้ตรงกับ server

# 4. Run
streamlit run ui/app.py
```

## Project Structure

```
AgentRCA/
├── agent/
│   ├── orchestrator.py    # OpenAI function-calling agent loop
│   └── skill_loader.py    # Load/save/delete skills/*.md
├── skills/                # Natural language skill instructions
│   ├── fetch_trino.md
│   ├── run_rca.md
│   └── plot_results.md
├── tools/
│   ├── trino_client.py    # Trino connector
│   ├── rca_engine.py      # Anomaly detection + LLM analysis
│   └── plotter.py         # Plotly charts
├── config/
│   └── trino_config.csv   # Trino connection settings
├── prompts/
│   └── system_prompt.md   # Agent base system prompt
├── ui/
│   └── app.py             # Streamlit app (3 pages)
├── config.py
├── .env.example
└── requirements.txt
```

## Adding a New Skill

**Via UI:** Open Skills Manager page → click "Add New Skill" → write natural language instructions → Save.

**Via file:** Create `skills/my_skill.md`:
```markdown
# Skill: My Skill Title

Brief description.

## When to Use
Describe trigger conditions...

## How to Execute
Step-by-step instructions for the agent...

## Example User Queries That Trigger This Skill
- Example query 1
```

The agent auto-discovers and loads all `.md` files in `skills/` on every run.

## Trino Config CSV Format

```csv
parameter,value
host,trino.mycompany.com
port,8080
user,analyst
catalog,hive
schema,analytics
auth_type,basic
password,mypassword
```

## Features

| Feature | Details |
|---------|---------|
| LLM | OpenAI GPT-4o (function calling) |
| Data Source | Trino database or CSV upload |
| RCA Methods | Z-score, IQR, Change Point Detection |
| Plots | Time series, Bar, Histogram, Scatter, Box, Heatmap |
| Skills | Add/Edit/Delete via UI or file |
| UI | Streamlit dark theme |
