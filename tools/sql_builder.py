"""
tools/sql_builder.py
====================
Builds a Trino SQL query from the attribute mapping produced by AttributeMapper.

Fixed SQL template (3-table LEFT JOIN)
--------------------------------------
  catalog : iceberg
  schema  : edputils

  SELECT
      e.<event_cols>,
      ap.<pivot_cols>,
      hd.<hd_cols>
  FROM iceberg.edputils.v_drvsoftware_evt_hd_norm_date e
  LEFT JOIN iceberg.edputils.drvsoftware_rca_attr_pivot ap ON (
      e.drive_serial_num = ap.drive_serial_num
      AND e.event_date_key_st = ap.event_date_key
  )
  LEFT JOIN iceberg.edputils.drvsoftware_rca_attr_hd hd ON (
      e.drive_serial_num = hd.drive_serial_num
      AND e.event_date_key_st = hd.event_date_key
      AND e.head_no = hd.head_no
  )
  [WHERE <time_filter>]
  [LIMIT <limit>]
"""

from __future__ import annotations

import textwrap
from typing import Optional

import pandas as pd

# ── Constants ──────────────────────────────────────────────────────────────────

CATALOG = "iceberg"
SCHEMA = "edputils"

TABLE_FULL = {
    "v_drvsoftware_evt_hd_norm_date": f"{CATALOG}.{SCHEMA}.v_drvsoftware_evt_hd_norm_date",
    "drvsoftware_rca_attr_pivot": f"{CATALOG}.{SCHEMA}.drvsoftware_rca_attr_pivot",
    "drvsoftware_rca_attr_hd": f"{CATALOG}.{SCHEMA}.drvsoftware_rca_attr_hd",
}

TABLE_ALIAS = {
    "v_drvsoftware_evt_hd_norm_date": "e",
    "drvsoftware_rca_attr_pivot": "ap",
    "drvsoftware_rca_attr_hd": "hd",
}

# Always-selected from event view (join keys + head_no)
ALWAYS_SELECT_E = [
    "drive_serial_num",
    "event_date_key_st",
    "head_no",
]


# ── Builder ────────────────────────────────────────────────────────────────────


class SQLBuilder:
    """
    Parameters
    ----------
    mapping_df : pd.DataFrame
        Output of AttributeMapper.matched() — only matched rows should be passed.
    time_filter : str, optional
        Raw SQL WHERE expression, e.g. "e.event_date_key_st >= DATE '2024-01-01'".
        Pass None to omit the WHERE clause.
    limit : int, optional
        LIMIT value.  Pass 0 or None for no LIMIT.
    select_all_event : bool
        If True → SELECT e.* (all columns from event view) instead of only
        the matched event columns.  Defaults to False (select only matched cols).
    """

    def __init__(
        self,
        mapping_df: pd.DataFrame,
        time_filter: Optional[str] = None,
        limit: int = 1000,
        select_all_event: bool = False,
    ):
        self.mapping_df = mapping_df
        self.time_filter = time_filter
        self.limit = limit
        self.select_all_event = select_all_event

    # ── Public ────────────────────────────────────────────────────────────────

    def build(self) -> tuple[str, pd.DataFrame]:
        """
        Returns
        -------
        sql : str
            The complete SQL query.
        col_map : pd.DataFrame
            Mapping table showing which attribute maps to which SQL expression.
        """
        col_map = self._build_col_map()
        sql = self._assemble(col_map)
        return sql, col_map

    # ── Internal ──────────────────────────────────────────────────────────────

    def _build_col_map(self) -> pd.DataFrame:
        """Deduplicate matched columns and assign SQL expressions."""
        seen: dict[str, str] = {}  # (table, col) → sql_expr
        rows = []

        df = self.mapping_df.copy()
        if df.empty:
            return pd.DataFrame(
                columns=["source_attr", "matched_table", "matched_column",
                         "table_alias", "sql_expr", "alias_col"]
            )

        for _, row in df.iterrows():
            tbl = str(row["matched_table"])
            col = str(row["matched_column"])
            alias_tbl = TABLE_ALIAS.get(tbl, "")
            sql_expr = f"{alias_tbl}.{col}" if alias_tbl else col
            alias_col = str(row["alias"]) if str(row["alias"]) not in ("", "nan") else col

            key = f"{tbl}.{col}"
            if key not in seen:
                seen[key] = sql_expr
                rows.append(
                    {
                        "source_attr": row["source_attr"],
                        "matched_table": tbl,
                        "matched_column": col,
                        "table_alias": alias_tbl,
                        "sql_expr": sql_expr,
                        "alias_col": alias_col,
                    }
                )

        return pd.DataFrame(rows)

    def _assemble(self, col_map: pd.DataFrame) -> str:
        # ── SELECT clause ────────────────────────────────────────────────────
        select_parts: list[str] = []

        # Event view columns
        if self.select_all_event:
            select_parts.append("e.*")
        else:
            # Always include join keys
            always = [f"e.{c}" for c in ALWAYS_SELECT_E]
            # Plus matched event columns
            e_matched = col_map[col_map["matched_table"] == "v_drvsoftware_evt_hd_norm_date"]
            e_cols = [
                r["sql_expr"]
                for _, r in e_matched.iterrows()
                if r["matched_column"] not in ALWAYS_SELECT_E
            ]
            combined_e = always + e_cols
            # Deduplicate while preserving order
            seen: set = set()
            for c in combined_e:
                if c not in seen:
                    select_parts.append(c)
                    seen.add(c)

        # Pivot table columns
        ap_matched = col_map[col_map["matched_table"] == "drvsoftware_rca_attr_pivot"]
        for _, r in ap_matched.iterrows():
            expr = f"{r['sql_expr']} AS {r['alias_col']}" if r["alias_col"] != r["matched_column"] else r["sql_expr"]
            select_parts.append(expr)

        # HD table columns
        hd_matched = col_map[col_map["matched_table"] == "drvsoftware_rca_attr_hd"]
        for _, r in hd_matched.iterrows():
            expr = f"{r['sql_expr']} AS {r['alias_col']}" if r["alias_col"] != r["matched_column"] else r["sql_expr"]
            select_parts.append(expr)

        if not select_parts:
            select_parts = ["e.*"]

        select_clause = ",\n    ".join(select_parts)

        # ── WHERE clause ─────────────────────────────────────────────────────
        where_clause = f"\nWHERE {self.time_filter}" if self.time_filter else ""

        # ── LIMIT clause ─────────────────────────────────────────────────────
        limit_clause = f"\nLIMIT {self.limit}" if self.limit else ""

        # ── Assemble ─────────────────────────────────────────────────────────
        sql = textwrap.dedent(f"""\
            SELECT
                {select_clause}
            FROM {TABLE_FULL['v_drvsoftware_evt_hd_norm_date']} e
            LEFT JOIN {TABLE_FULL['drvsoftware_rca_attr_pivot']} ap ON (
                e.drive_serial_num = ap.drive_serial_num
                AND e.event_date_key_st = ap.event_date_key
            )
            LEFT JOIN {TABLE_FULL['drvsoftware_rca_attr_hd']} hd ON (
                e.drive_serial_num = hd.drive_serial_num
                AND e.event_date_key_st = hd.event_date_key
                AND e.head_no = hd.head_no
            ){where_clause}{limit_clause}""")

        return sql

    # ── Convenience ───────────────────────────────────────────────────────────

    @staticmethod
    def format_col_map(col_map: pd.DataFrame) -> str:
        """Return a markdown table of the column mapping."""
        if col_map.empty:
            return "_No columns mapped._"
        lines = ["| Source Attribute | Table | Column | SQL Expression |",
                 "|-----------------|-------|--------|----------------|"]
        for _, r in col_map.iterrows():
            lines.append(
                f"| {r['source_attr']} | {r['matched_table']} | {r['matched_column']} | `{r['sql_expr']}` |"
            )
        return "\n".join(lines)
