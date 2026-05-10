"""
AgentRCA — Streamlit UI
Run with: streamlit run ui/app.py --server.runOnSave true
"""
from __future__ import annotations
import sys
import os
import pandas as pd
import streamlit as st

# Allow imports from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.orchestrator import AgentOrchestrator
from agent.skill_loader import load_all_skills, save_skill, delete_skill
from tools.trino_client import TrinoClient
from tools.attr_mapper import AttributeMapper
from tools.sql_builder import SQLBuilder
from config import CONFIG_DIR

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AgentRCA",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ─────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    border-right: 1px solid #334155;
}
section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }

/* Nav buttons */
.nav-btn {
    width: 100%;
    padding: 12px 16px;
    margin: 4px 0;
    border-radius: 10px;
    border: none;
    background: transparent;
    color: #94a3b8;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    text-align: left;
    transition: all 0.2s;
    display: flex; align-items: center; gap: 10px;
}
.nav-btn:hover { background: rgba(99,102,241,0.15); color: #e2e8f0; }
.nav-btn.active { background: rgba(99,102,241,0.3); color: #818cf8; border-left: 3px solid #6366f1; }

/* Chat bubbles */
.msg-user {
    background: linear-gradient(135deg, #6366f1, #818cf8);
    color: white; padding: 14px 18px;
    border-radius: 18px 18px 4px 18px;
    margin: 8px 0; max-width: 75%; margin-left: auto;
    box-shadow: 0 4px 15px rgba(99,102,241,0.3);
    font-size: 14px; line-height: 1.6;
}
.msg-agent {
    background: #1e293b; color: #e2e8f0;
    border: 1px solid #334155; padding: 14px 18px;
    border-radius: 18px 18px 18px 4px;
    margin: 8px 0; max-width: 80%;
    font-size: 14px; line-height: 1.6;
}
.tool-badge {
    display: inline-block; padding: 3px 10px;
    border-radius: 20px; font-size: 11px; font-weight: 600;
    margin: 3px 2px;
    background: rgba(99,102,241,0.2); color: #818cf8; border: 1px solid #6366f1;
}

/* Skill card */
.skill-card {
    background: #1e293b; border: 1px solid #334155;
    border-radius: 14px; padding: 18px 20px; margin-bottom: 12px;
    transition: border-color 0.2s;
}
.skill-card:hover { border-color: #6366f1; }
.skill-title { font-size: 16px; font-weight: 600; color: #818cf8; margin-bottom: 6px; }
.skill-desc { font-size: 13px; color: #94a3b8; }

/* Metric cards */
.metric-card {
    background: linear-gradient(135deg, #1e293b, #0f172a);
    border: 1px solid #334155; border-radius: 12px;
    padding: 20px; text-align: center;
}
.metric-val { font-size: 32px; font-weight: 700; color: #6366f1; }
.metric-label { font-size: 12px; color: #64748b; margin-top: 4px; }

/* Section header */
.section-hdr {
    font-size: 22px; font-weight: 700; color: #e2e8f0;
    margin-bottom: 20px; padding-bottom: 10px;
    border-bottom: 2px solid #334155;
}
</style>
""",
    unsafe_allow_html=True,
)

# ── Session state init ─────────────────────────────────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = "💬 Chat"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent" not in st.session_state:
    st.session_state.agent = AgentOrchestrator()
if "figures" not in st.session_state:
    st.session_state.figures = []
if "skill_edit" not in st.session_state:
    st.session_state.skill_edit = None
if "mapping_df" not in st.session_state:
    st.session_state.mapping_df = None
if "generated_sql" not in st.session_state:
    st.session_state.generated_sql = None

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        """
        <div style='text-align:center; padding: 20px 0 10px;'>
            <span style='font-size:40px;'>🔍</span>
            <div style='font-size:22px; font-weight:700; color:#818cf8; margin-top:6px;'>AgentRCA</div>
            <div style='font-size:12px; color:#475569; margin-top:4px;'>AI Root Cause Analysis</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    pages = ["💬 Chat", "🗂️ Attribute Mapper", "🧩 Skills Manager", "🔌 Trino Config"]
    for pg in pages:
        active = "active" if st.session_state.page == pg else ""
        if st.button(pg, key=f"nav_{pg}", use_container_width=True):
            st.session_state.page = pg
            st.rerun()

    st.divider()
    skills_count = len(load_all_skills())
    st.markdown(
        f"""
        <div style='padding: 10px; background: #0f172a; border-radius: 10px; text-align:center;'>
            <div style='font-size:12px; color:#64748b;'>Active Skills</div>
            <div style='font-size:24px; font-weight:700; color:#6366f1;'>{skills_count}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — CHAT
# ══════════════════════════════════════════════════════════════════════════════
def page_chat():
    st.markdown('<div class="section-hdr">💬 Chat with AgentRCA</div>', unsafe_allow_html=True)

    col_chat, col_info = st.columns([3, 1])

    with col_chat:
        # Render message history
        chat_container = st.container()
        with chat_container:
            for entry in st.session_state.messages:
                if entry["role"] == "user":
                    st.markdown(f'<div class="msg-user">{entry["content"]}</div>', unsafe_allow_html=True)
                elif entry["role"] == "assistant":
                    st.markdown(f'<div class="msg-agent">{entry["content"]}</div>', unsafe_allow_html=True)
                    # Show tool badges
                    if entry.get("tool_calls"):
                        badges = " ".join(
                            f'<span class="tool-badge">🔧 {tc["tool"]}</span>'
                            for tc in entry["tool_calls"]
                        )
                        st.markdown(badges, unsafe_allow_html=True)
                    # Show plot if attached
                    if entry.get("figure"):
                        st.plotly_chart(entry["figure"], use_container_width=True, key=f"fig_{id(entry)}")

        # Upload CSV as data source
        with st.expander("📂 Upload CSV (fallback if Trino unavailable)", expanded=False):
            uploaded = st.file_uploader("Upload a CSV file", type="csv", key="csv_upload")
            if uploaded:
                df = pd.read_csv(uploaded)
                st.session_state.agent._data = df
                st.success(f"✅ Loaded {len(df)} rows × {len(df.columns)} cols from {uploaded.name}")
                st.dataframe(df.head(), use_container_width=True)

        # Input area
        st.markdown("---")
        with st.form("chat_form", clear_on_submit=True):
            col1, col2 = st.columns([5, 1])
            with col1:
                user_input = st.text_input(
                    "Message",
                    placeholder="ถามเกี่ยวกับข้อมูล, RCA, หรือขอ plot ผลลัพธ์...",
                    label_visibility="collapsed",
                )
            with col2:
                submitted = st.form_submit_button("Send ➤", use_container_width=True)

        if submitted and user_input.strip():
            st.session_state.messages.append({"role": "user", "content": user_input})

            with st.spinner("🤖 Agent thinking..."):
                # Build messages list for API (exclude figures from API payload)
                api_msgs = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages
                    if m["role"] in ("user", "assistant") and m.get("content")
                ]
                result = st.session_state.agent.run(api_msgs)

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": result["content"],
                    "tool_calls": result["tool_calls"],
                    "figure": result["figure"],
                }
            )
            st.rerun()

        # Clear chat button
        if st.session_state.messages:
            if st.button("🗑️ Clear conversation", type="secondary"):
                st.session_state.messages = []
                st.session_state.agent.reset()
                st.rerun()

    with col_info:
        st.markdown("**📊 Session Info**")
        agent = st.session_state.agent
        if agent._data is not None:
            st.metric("Rows loaded", f"{len(agent._data):,}")
            st.metric("Columns", len(agent._data.columns))
            if agent._rca_report:
                st.metric("Anomalies", agent._rca_report.get("anomaly_count", 0))
                rate = agent._rca_report.get("anomaly_rate", 0)
                st.metric("Anomaly rate", f"{rate:.1%}")
        else:
            st.info("No data loaded yet")

        st.markdown("**🧩 Active Skills**")
        for name, skill in load_all_skills().items():
            st.markdown(f"- `{skill['title']}`")

        st.markdown("**💡 Example queries**")
        examples = [
            "ดึงข้อมูล 7 วันล่าสุดจาก hive.prod.metrics",
            "วิเคราะห์ RCA ของ cpu_usage",
            "Plot time series ของ error_rate",
        ]
        for ex in examples:
            if st.button(ex, key=f"ex_{ex}", use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": ex})
                with st.spinner("🤖 Thinking..."):
                    api_msgs = [
                        {"role": m["role"], "content": m["content"]}
                        for m in st.session_state.messages
                        if m["role"] in ("user", "assistant") and m.get("content")
                    ]
                    result = st.session_state.agent.run(api_msgs)
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": result["content"],
                        "tool_calls": result["tool_calls"],
                        "figure": result["figure"],
                    }
                )
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — ATTRIBUTE MAPPER
# ══════════════════════════════════════════════════════════════════════════════
def page_attr_mapper():
    st.markdown('<div class="section-hdr">🗂️ Attribute Mapper</div>', unsafe_allow_html=True)
    st.caption(
        "Fuzzy-match attribute names from `attribute_list.csv` to actual DB columns in `drive_hd.csv`, "
        "then generate the 3-table LEFT JOIN SQL query."
    )

    col_cfg, col_result = st.columns([1, 2])

    # ── Left panel: configuration ─────────────────────────────────────────────
    with col_cfg:
        st.subheader("⚙️ Configuration")

        threshold = st.slider(
            "Fuzzy Match Threshold",
            min_value=0, max_value=100, value=80, step=5,
            help="Attributes with score < threshold will be flagged as Unmatched.",
            key="mapper_threshold",
        )

        time_filter = st.text_input(
            "Time Filter (SQL WHERE expression, optional)",
            placeholder="e.g. e.event_date_key_st >= DATE '2024-01-01'",
            key="mapper_time_filter",
        )

        limit = st.number_input(
            "Row Limit", min_value=1, max_value=100000, value=1000, step=100,
            key="mapper_limit",
        )

        select_all_event = st.toggle(
            "SELECT e.* (all event columns)",
            value=False,
            key="mapper_select_all",
            help="When ON: selects all columns from event view. When OFF: only matched columns.",
        )

        st.divider()

        # Upload CSVs
        st.subheader("📂 CSV Files")
        col_a, col_b = st.columns(2)

        with col_a:
            attr_path = CONFIG_DIR / "attribute_list.csv"
            st.caption("**attribute_list.csv** (requirements)")
            if attr_path.exists():
                st.success(f"✅ Found ({attr_path.stat().st_size:,} B)")
            else:
                st.error("❌ Not found")
            up_attr = st.file_uploader("Upload attribute_list.csv", type="csv", key="up_attr")
            if up_attr:
                with open(attr_path, "wb") as f:
                    f.write(up_attr.read())
                st.success("Saved!")
                st.rerun()

        with col_b:
            schema_path = CONFIG_DIR / "drive_hd.csv"
            st.caption("**drive_hd.csv** (DB schema)")
            if schema_path.exists():
                st.success(f"✅ Found ({schema_path.stat().st_size:,} B)")
            else:
                st.error("❌ Not found")
            up_schema = st.file_uploader("Upload drive_hd.csv", type="csv", key="up_schema")
            if up_schema:
                with open(schema_path, "wb") as f:
                    f.write(up_schema.read())
                st.success("Saved!")
                st.rerun()

        st.divider()
        run_map = st.button("🔍 Run Mapping", type="primary", use_container_width=True, key="run_mapping")

    # ── Right panel: results ──────────────────────────────────────────────────
    with col_result:
        if run_map:
            attr_path = CONFIG_DIR / "attribute_list.csv"
            schema_path = CONFIG_DIR / "drive_hd.csv"

            if not attr_path.exists() or not schema_path.exists():
                st.error("❌ Please upload both CSV files first.")
            else:
                with st.spinner("Running fuzzy match..."):
                    try:
                        mapper = AttributeMapper(
                            attr_csv=attr_path,
                            schema_csv=schema_path,
                            threshold=threshold,
                        )
                        mapper.run()
                        st.session_state.mapping_df = mapper._mapping.copy()

                        # Build SQL preview
                        matched_df = mapper.matched()
                        if not matched_df.empty:
                            builder = SQLBuilder(
                                mapping_df=matched_df,
                                time_filter=time_filter.strip() if time_filter.strip() else None,
                                limit=int(limit),
                                select_all_event=select_all_event,
                            )
                            sql, col_map = builder.build()
                            st.session_state.generated_sql = sql
                            st.session_state.col_map = col_map
                        else:
                            st.session_state.generated_sql = None
                            st.session_state.col_map = None
                    except Exception as e:
                        st.error(f"❌ Error: {e}")

        if st.session_state.mapping_df is not None:
            mapping_df = st.session_state.mapping_df
            n_total = len(mapping_df)
            n_match = (mapping_df["status"] == "matched").sum()
            n_un = n_total - n_match

            # Summary metrics
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Attributes", n_total)
            m2.metric("✅ Matched", n_match)
            m3.metric("❌ Unmatched", n_un)

            st.subheader("📋 Mapping Table")

            def _color_row(row):
                color = "background-color: #14532d22" if row["status"] == "matched" else "background-color: #7f1d1d22"
                return [color] * len(row)

            display_cols = [
                "orig_index", "PROCESS_NAME", "COMPONENT_NAME",
                "source_attr", "attribute_name",
                "matched_column", "matched_table", "table_alias",
                "match_score", "status",
            ]
            styled = mapping_df[display_cols].style.apply(_color_row, axis=1)
            st.dataframe(styled, use_container_width=True, hide_index=True)

            # Download mapping
            csv_data = mapping_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download Mapping CSV",
                data=csv_data,
                file_name="attribute_mapping_result.csv",
                mime="text/csv",
            )

            st.divider()

            # Manual override section
            with st.expander("🔧 Manual Override for Unmatched Attributes", expanded=n_un > 0):
                unmatched = mapping_df[mapping_df["status"] == "unmatched"]
                if unmatched.empty:
                    st.success("All attributes matched! No overrides needed.")
                else:
                    st.warning(f"{n_un} attribute(s) need manual mapping.")
                    schema_df = pd.read_csv(CONFIG_DIR / "drive_hd.csv")
                    all_cols = schema_df["column_name"].tolist()
                    all_tables = schema_df["table_name"].unique().tolist()

                    for _, row in unmatched.iterrows():
                        st.markdown(
                            f"**[{row['orig_index']}]** `{row['source_attr']}` / `{row['attribute_name']}`  "
                            f"(best score: {row['match_score']:.0f})"
                        )
                        oc1, oc2, oc3 = st.columns([2, 2, 1])
                        with oc1:
                            sel_col = st.selectbox(
                                "Column", ["— skip —"] + all_cols,
                                key=f"ov_col_{row['orig_index']}"
                            )
                        with oc2:
                            sel_tbl = st.selectbox(
                                "Table", all_tables,
                                key=f"ov_tbl_{row['orig_index']}"
                            )
                        with oc3:
                            if st.button("Apply", key=f"ov_btn_{row['orig_index']}"):
                                if sel_col != "— skip —":
                                    from tools.attr_mapper import TABLE_ALIASES
                                    idx = row['orig_index']
                                    st.session_state.mapping_df.loc[
                                        st.session_state.mapping_df["orig_index"] == idx,
                                        ["matched_column", "matched_table", "table_alias",
                                         "match_score", "matched_by", "status"]
                                    ] = [sel_col, sel_tbl, TABLE_ALIASES.get(sel_tbl, ""),
                                         100.0, "manual_override", "matched"]
                                    st.success(f"Override applied for [{idx}]")
                                    # Rebuild SQL
                                    matched_df2 = st.session_state.mapping_df[
                                        st.session_state.mapping_df["status"] == "matched"
                                    ]
                                    b2 = SQLBuilder(
                                        mapping_df=matched_df2,
                                        time_filter=time_filter.strip() if time_filter.strip() else None,
                                        limit=int(limit),
                                        select_all_event=select_all_event,
                                    )
                                    sql2, cm2 = b2.build()
                                    st.session_state.generated_sql = sql2
                                    st.session_state.col_map = cm2
                                    st.rerun()

            # SQL Preview
            if st.session_state.generated_sql:
                st.subheader("🔍 Generated SQL")
                st.code(st.session_state.generated_sql, language="sql")

                # Column mapping table
                if st.session_state.get("col_map") is not None:
                    with st.expander("📊 Column Mapping Detail", expanded=False):
                        st.dataframe(st.session_state.col_map, use_container_width=True, hide_index=True)

                # Execute button
                st.divider()
                if st.button("▶️ Execute Query via Trino", type="primary", use_container_width=True, key="exec_sql"):
                    with st.spinner("Executing..."):
                        try:
                            client = TrinoClient()
                            df = client.execute_query(st.session_state.generated_sql, limit=int(limit))
                            st.session_state.agent._data = df
                            st.success(f"✅ Fetched {len(df):,} rows × {len(df.columns)} columns")
                            st.dataframe(df.head(20), use_container_width=True)
                        except Exception as e:
                            st.error(f"❌ Trino error: {e}")
        else:
            st.info("👈 Configure options on the left and click **Run Mapping** to start.")

            # Show current CSV previews if available
            attr_path = CONFIG_DIR / "attribute_list.csv"
            schema_path = CONFIG_DIR / "drive_hd.csv"
            if attr_path.exists():
                with st.expander("👁️ Preview attribute_list.csv", expanded=True):
                    st.dataframe(pd.read_csv(attr_path), use_container_width=True)
            if schema_path.exists():
                with st.expander("👁️ Preview drive_hd.csv (schema)", expanded=False):
                    st.dataframe(pd.read_csv(schema_path), use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — SKILLS MANAGER
# ══════════════════════════════════════════════════════════════════════════════
def page_skills():
    st.markdown('<div class="section-hdr">🧩 Skills Manager</div>', unsafe_allow_html=True)
    st.caption("Skills are natural language instructions that tell the agent how and when to use each tool.")

    col_list, col_editor = st.columns([2, 3])

    with col_list:
        skills = load_all_skills()
        if not skills:
            st.info("No skills yet. Create one →")
        else:
            for name, skill in skills.items():
                with st.container():
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        st.markdown(
                            f"""
                            <div class="skill-card">
                                <div class="skill-title">📄 {skill['title']}</div>
                                <div class="skill-desc">{skill['description'][:120]}...</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    with c2:
                        if st.button("✏️", key=f"edit_{name}", help="Edit"):
                            st.session_state.skill_edit = name
                            st.rerun()
                        if st.button("🗑️", key=f"del_{name}", help="Delete"):
                            delete_skill(name)
                            if st.session_state.skill_edit == name:
                                st.session_state.skill_edit = None
                            st.success(f"Deleted skill: {name}")
                            st.rerun()

    with col_editor:
        editing = st.session_state.skill_edit
        skills = load_all_skills()

        if editing and editing in skills:
            st.subheader(f"✏️ Editing: {editing}")
            current = skills[editing]["content"]
        else:
            st.subheader("➕ Add New Skill")
            current = (
                "# Skill: My New Skill\n\n"
                "Brief description of what this skill does.\n\n"
                "## When to Use\n\nDescribe trigger conditions...\n\n"
                "## How to Execute\n\n1. Step one\n2. Step two\n\n"
                "## Example User Queries That Trigger This Skill\n\n- Example query"
            )

        skill_name = st.text_input(
            "Skill filename (no spaces, no .md)",
            value=editing if editing else "my_new_skill",
            key="skill_name_input",
        )
        skill_content = st.text_area(
            "Skill content (Markdown / natural language instructions)",
            value=current,
            height=420,
            key="skill_content_input",
        )

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if st.button("💾 Save Skill", type="primary", use_container_width=True):
                if skill_name.strip() and skill_content.strip():
                    save_skill(skill_name.strip(), skill_content.strip())
                    st.session_state.skill_edit = None
                    st.success(f"✅ Saved skill: {skill_name}")
                    st.rerun()
                else:
                    st.error("Name and content cannot be empty.")
        with col_s2:
            if st.button("🔄 New Skill", use_container_width=True):
                st.session_state.skill_edit = None
                st.rerun()

        # Preview
        with st.expander("👁️ Preview skill content", expanded=False):
            st.markdown(skill_content)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — TRINO CONFIG
# ══════════════════════════════════════════════════════════════════════════════
def page_trino():
    st.markdown('<div class="section-hdr">🔌 Trino Connection Config</div>', unsafe_allow_html=True)

    from config import TRINO_CONFIG_CSV, CONFIG_DIR

    col_form, col_status = st.columns([2, 1])

    with col_form:
        st.subheader("📝 Edit Connection Settings")

        # Load current config
        client = TrinoClient()
        cfg = client.get_config()

        with st.form("trino_form"):
            host = st.text_input("Host", value=str(cfg.get("host", "localhost")))
            port = st.number_input("Port", value=int(cfg.get("port", 8080)), min_value=1, max_value=65535)
            user = st.text_input("User", value=str(cfg.get("user", "analyst")))
            catalog = st.text_input("Catalog", value=str(cfg.get("catalog", "hive")))
            schema = st.text_input("Schema", value=str(cfg.get("schema", "default")))
            auth_type = st.selectbox("Auth Type", ["none", "basic"], index=0 if cfg.get("auth_type", "none") == "none" else 1)
            password = st.text_input("Password (if basic auth)", type="password", value=str(cfg.get("password", "")))

            if st.form_submit_button("💾 Save Config", type="primary"):
                import csv
                CONFIG_DIR.mkdir(exist_ok=True)
                with open(TRINO_CONFIG_CSV, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["parameter", "value"])
                    for k, v in [
                        ("host", host), ("port", port), ("user", user),
                        ("catalog", catalog), ("schema", schema),
                        ("auth_type", auth_type), ("password", password),
                    ]:
                        writer.writerow([k, v])
                # Reload agent's Trino client
                st.session_state.agent.trino.reload_config()
                st.success("✅ Config saved and reloaded!")

        # Upload CSV directly
        st.subheader("📂 Upload Config CSV")
        st.caption("CSV must have columns: `parameter`, `value`")
        uploaded_cfg = st.file_uploader("Upload trino_config.csv", type="csv", key="cfg_upload")
        if uploaded_cfg:
            CONFIG_DIR.mkdir(exist_ok=True)
            with open(TRINO_CONFIG_CSV, "wb") as f:
                f.write(uploaded_cfg.read())
            st.session_state.agent.trino.reload_config()
            st.success("✅ Config uploaded and applied!")

    with col_status:
        st.subheader("🔍 Connection Status")
        if st.button("🧪 Test Connection", type="primary", use_container_width=True):
            client = TrinoClient()
            ok, msg = client.test_connection()
            if ok:
                st.success(msg)
            else:
                st.error(msg)

        st.subheader("📋 Current Config")
        client = TrinoClient()
        cfg = client.get_config()
        safe_cfg = {k: ("***" if k == "password" and v else v) for k, v in cfg.items()}
        for k, v in safe_cfg.items():
            st.markdown(f"**{k}:** `{v}`")

        # CSV template download
        st.subheader("📥 CSV Template")
        template = "parameter,value\nhost,localhost\nport,8080\nuser,analyst\ncatalog,hive\nschema,default\nauth_type,none\npassword,\n"
        st.download_button(
            "Download template CSV",
            data=template,
            file_name="trino_config_template.csv",
            mime="text/csv",
            use_container_width=True,
        )


# ── Router ─────────────────────────────────────────────────────────────────────
page = st.session_state.page
if page == "💬 Chat":
    page_chat()
elif page == "🗂️ Attribute Mapper":
    page_attr_mapper()
elif page == "🧩 Skills Manager":
    page_skills()
elif page == "🔌 Trino Config":
    page_trino()
