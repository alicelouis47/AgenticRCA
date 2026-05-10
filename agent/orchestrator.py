from __future__ import annotations
import json
import pandas as pd
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL, PROMPTS_DIR, CONFIG_DIR
from agent.skill_loader import load_all_skills
from tools.trino_client import TrinoClient
from tools.rca_engine import RCAEngine
from tools.plotter import Plotter
from tools.attr_mapper import AttributeMapper
from tools.sql_builder import SQLBuilder


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "fetch_trino_data",
            "description": "Execute a SQL query against Trino and return results as a dataset.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql_query": {"type": "string", "description": "SQL query. Use catalog.schema.table format."},
                    "limit": {"type": "integer", "description": "Max rows. Default 1000.", "default": 1000},
                },
                "required": ["sql_query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_rca_analysis",
            "description": "Detect anomalies and find root causes in the fetched dataset.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric_column": {"type": "string", "description": "Column to analyze for anomalies."},
                    "time_column": {"type": "string", "description": "Timestamp column (optional)."},
                    "method": {
                        "type": "string",
                        "enum": ["zscore", "iqr", "changepoint"],
                        "description": "Detection method. Default: zscore",
                        "default": "zscore",
                    },
                    "threshold": {"type": "number", "description": "Anomaly threshold. Default 2.5.", "default": 2.5},
                },
                "required": ["metric_column"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plot_rca_results",
            "description": "Create an interactive Plotly chart from the current dataset and RCA report.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plot_type": {
                        "type": "string",
                        "enum": ["time_series", "bar", "heatmap", "scatter", "histogram", "box"],
                        "description": "Chart type.",
                    },
                    "x_column": {"type": "string", "description": "X-axis column (optional for some charts)."},
                    "y_column": {"type": "string", "description": "Y-axis column."},
                    "title": {"type": "string", "description": "Chart title."},
                    "highlight_anomalies": {
                        "type": "boolean",
                        "description": "Overlay anomaly markers. Default true.",
                        "default": True,
                    },
                },
                "required": ["plot_type", "y_column"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "map_and_fetch_data",
            "description": (
                "Map attribute names from attribute_list.csv to actual DB columns using "
                "fuzzy matching, build a 3-table LEFT JOIN SQL query, and fetch data from Trino. "
                "Use this when the user wants to pull Drive HDD data based on an attribute requirements list."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "threshold": {
                        "type": "number",
                        "description": "Fuzzy match score threshold (0–100). Attributes scoring below this are flagged as unmatched. Default: 80.",
                        "default": 80,
                    },
                    "time_filter": {
                        "type": "string",
                        "description": "Optional SQL WHERE clause for date filtering, e.g. \"e.event_date_key_st >= DATE '2024-01-01'\". Omit for no filter.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max rows to return. Default 1000.",
                        "default": 1000,
                    },
                    "select_all_event": {
                        "type": "boolean",
                        "description": "If true, selects e.* (all event columns) instead of only matched ones. Default false.",
                        "default": False,
                    },
                    "override_mapping": {
                        "type": "array",
                        "description": "List of manual overrides for unmatched attributes.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "orig_index": {"type": "integer", "description": "Row index from attribute_list.csv (0-based)."},
                                "column_name": {"type": "string", "description": "Exact column name in DB."},
                                "table_name": {"type": "string", "description": "Exact table name."},
                            },
                            "required": ["orig_index", "column_name", "table_name"],
                        },
                    },
                },
                "required": [],
            },
        },
    },
]


class AgentOrchestrator:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.trino = TrinoClient()
        self.rca = RCAEngine()
        self.plotter = Plotter()
        self._data: pd.DataFrame | None = None
        self._rca_report: dict | None = None
        self._figure = None
        self._mapping: pd.DataFrame | None = None
        self._attr_csv = CONFIG_DIR / "attribute_list.csv"
        self._schema_csv = CONFIG_DIR / "drive_hd.csv"

    # ── System prompt ──────────────────────────────────────────────────────────

    def build_system_prompt(self) -> str:
        base_path = PROMPTS_DIR / "system_prompt.md"
        base = base_path.read_text(encoding="utf-8") if base_path.exists() else ""
        skills = load_all_skills()
        skill_blocks = "\n\n---\n\n".join(
            f"## Skill: {s['title']}\n\n{s['content']}" for s in skills.values()
        )
        return f"{base}\n\n# Loaded Skills\n\n{skill_blocks}" if skill_blocks else base

    # ── Tool execution ─────────────────────────────────────────────────────────

    def _exec_tool(self, name: str, args: dict):
        """Returns (text_result: str, figure | None)."""
        if name == "fetch_trino_data":
            try:
                df = self.trino.execute_query(args["sql_query"], limit=args.get("limit", 1000))
                self._data = df
                cols = ", ".join(df.columns)
                return (
                    f"✅ Fetched {len(df)} rows × {len(df.columns)} columns.\nColumns: {cols}\n\n"
                    f"Preview:\n{df.head(5).to_string(index=False)}",
                    None,
                )
            except Exception as e:
                return f"❌ Trino error: {e}", None

        if name == "run_rca_analysis":
            if self._data is None:
                return "❌ No data loaded. Call fetch_trino_data first.", None
            try:
                report = self.rca.analyze(
                    df=self._data,
                    metric_col=args["metric_column"],
                    time_col=args.get("time_column"),
                    method=args.get("method", "zscore"),
                    threshold=float(args.get("threshold", 2.5)),
                )
                self._rca_report = report
                txt = (
                    f"✅ RCA complete | metric={args['metric_column']} | method={args.get('method','zscore')}\n"
                    f"Total points: {report['total_points']} | Anomalies: {report['anomaly_count']} "
                    f"({report['anomaly_rate']:.1%})\n\nAnalysis:\n{report.get('llm_analysis','N/A')}"
                )
                return txt, None
            except Exception as e:
                return f"❌ RCA error: {e}", None

        if name == "plot_rca_results":
            if self._data is None:
                return "❌ No data loaded. Call fetch_trino_data first.", None
            try:
                fig = self.plotter.create_plot(
                    df=self._data,
                    plot_type=args["plot_type"],
                    x_col=args.get("x_column"),
                    y_col=args["y_column"],
                    title=args.get("title", f"{args['plot_type']} — {args['y_column']}"),
                    rca_report=self._rca_report if args.get("highlight_anomalies", True) else None,
                )
                self._figure = fig
                return f"✅ Created {args['plot_type']} chart for '{args['y_column']}'", fig
            except Exception as e:
                return f"❌ Plot error: {e}", None

        if name == "map_and_fetch_data":
            return self._exec_map_and_fetch(args)

        return f"❌ Unknown tool: {name}", None

    def _exec_map_and_fetch(self, args: dict) -> tuple[str, None]:
        """Fuzzy-map attributes → columns → build SQL → execute via Trino."""
        threshold = float(args.get("threshold", 80))
        time_filter = args.get("time_filter") or None
        limit = int(args.get("limit", 1000))
        select_all_event = bool(args.get("select_all_event", False))
        overrides = args.get("override_mapping") or []

        # ── Step 1: Fuzzy map ────────────────────────────────────────────────
        try:
            mapper = AttributeMapper(
                attr_csv=self._attr_csv,
                schema_csv=self._schema_csv,
                threshold=threshold,
            )
            mapper.run()
        except FileNotFoundError as e:
            return (
                f"❌ CSV file missing: {e}\n"
                "Please place `attribute_list.csv` and `drive_hd.csv` in the `config/` folder.",
                None,
            )
        except Exception as e:
            return f"❌ Mapping error: {e}", None

        # Apply manual overrides
        for ov in overrides:
            mapper.override(
                orig_index=int(ov["orig_index"]),
                column_name=str(ov["column_name"]),
                table_name=str(ov["table_name"]),
            )

        summary = mapper.summary()
        matched_df = mapper.matched()
        unmatched_df = mapper.unmatched()
        self._mapping = mapper._mapping

        # ── Step 2: Report unmatched ─────────────────────────────────────────
        unmatched_report = ""
        if not unmatched_df.empty:
            items = []
            for _, r in unmatched_df.iterrows():
                items.append(
                    f"  • [{r['orig_index']}] source='{r['source_attr']}' / attr='{r['attribute_name']}' "
                    f"(best score: {r['match_score']:.0f})"
                )
            unmatched_report = (
                "\n⚠️ Unmatched attributes (score < threshold):\n"
                + "\n".join(items)
                + "\nYou can call `map_and_fetch_data` again with `override_mapping` to fix these."
            )

        if matched_df.empty:
            return (
                f"{summary}{unmatched_report}\n"
                "❌ No attributes matched — cannot build SQL. Adjust threshold or fix attribute names.",
                None,
            )

        # ── Step 3: Build SQL ────────────────────────────────────────────────
        try:
            builder = SQLBuilder(
                mapping_df=matched_df,
                time_filter=time_filter,
                limit=limit,
                select_all_event=select_all_event,
            )
            sql, col_map = builder.build()
            col_map_md = SQLBuilder.format_col_map(col_map)
        except Exception as e:
            return f"❌ SQL build error: {e}", None

        # ── Step 4: Execute ──────────────────────────────────────────────────
        try:
            df = self.trino.execute_query(sql, limit=limit)
            self._data = df
            fetch_result = (
                f"✅ Fetched {len(df)} rows × {len(df.columns)} columns.\n"
                f"Columns: {', '.join(df.columns)}\n\nPreview:\n{df.head(5).to_string(index=False)}"
            )
        except Exception as e:
            fetch_result = (
                f"⚠️ Trino query failed: {e}\n"
                f"Generated SQL (for manual execution):\n```sql\n{sql}\n```"
            )

        result_text = (
            f"{summary}{unmatched_report}\n"
            f"\n📋 Column Mapping:\n{col_map_md}\n"
            f"\n🔍 Generated SQL:\n```sql\n{sql}\n```\n"
            f"\n{fetch_result}"
        )
        return result_text, None

    # ── Main run ───────────────────────────────────────────────────────────────

    def run(self, messages: list[dict]) -> dict:
        """
        Run the agentic loop.
        Returns: {content, figure, tool_calls, current_data}
        """
        system_prompt = self.build_system_prompt()
        full_msgs = [{"role": "system", "content": system_prompt}] + messages
        final_content = ""
        result_figure = None
        tool_calls_log = []

        for _ in range(6):  # max tool-call iterations
            resp = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=full_msgs,
                tools=TOOLS,
                tool_choice="auto",
            )
            msg = resp.choices[0].message
            full_msgs.append(msg)

            if resp.choices[0].finish_reason == "stop" or not msg.tool_calls:
                final_content = msg.content or ""
                break

            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments)
                tool_calls_log.append({"tool": tc.function.name, "args": args})
                text, fig = self._exec_tool(tc.function.name, args)
                if fig is not None:
                    result_figure = fig
                full_msgs.append({"role": "tool", "tool_call_id": tc.id, "content": text})

        return {
            "content": final_content,
            "figure": result_figure,
            "tool_calls": tool_calls_log,
            "current_data": self._data,
        }

    def reset(self):
        self._data = None
        self._rca_report = None
        self._figure = None
        self._mapping = None
