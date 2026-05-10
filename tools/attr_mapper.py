"""
tools/attr_mapper.py
====================
Fuzzy-matches attribute names from `attribute_list.csv` (requirements spec)
to actual column names in `drive_hd.csv` (DB schema).

Matching strategy
-----------------
For every row in attribute_list.csv the matcher tries (in order):
  1. `Source Attribute(ODS)` column
  2. `Attribute_Name` column
  3. `Alias` column
Each candidate is compared against all column_name values in drive_hd.csv
using token-sort-ratio from rapidfuzz (falls back to difflib if unavailable).
The highest-scoring match wins.  If the score < threshold → "unmatched".

Table alias mapping (fixed SQL template)
-----------------------------------------
  drvsoftware_rca_attr_hd     → hd
  drvsoftware_rca_attr_pivot  → ap
  v_drvsoftware_evt_hd_norm_date → e
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Optional

import pandas as pd

# Try rapidfuzz first, fall back to difflib
try:
    from rapidfuzz import fuzz as _fuzz

    def _score(a: str, b: str) -> float:
        return _fuzz.token_sort_ratio(a, b)

except ImportError:
    import difflib

    def _score(a: str, b: str) -> float:  # type: ignore[misc]
        return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() * 100


# ── Constants ──────────────────────────────────────────────────────────────────

TABLE_ALIASES: dict[str, str] = {
    "drvsoftware_rca_attr_hd": "hd",
    "drvsoftware_rca_attr_pivot": "ap",
    "v_drvsoftware_evt_hd_norm_date": "e",
}

ATTR_CANDIDATE_COLS = ["Source Attribute(ODS)", "Attribute_Name", "Alias"]

# ── Main class ─────────────────────────────────────────────────────────────────


class AttributeMapper:
    """
    Parameters
    ----------
    attr_csv : path-like
        attribute_list.csv  — the requirements spec (CSV 1).
    schema_csv : path-like
        drive_hd.csv        — the DB schema (CSV 2).
    threshold : float
        Minimum fuzzy-match score (0–100) to accept a match.
        Rows scoring below this are returned with status='unmatched'.
    """

    def __init__(
        self,
        attr_csv: Path | str,
        schema_csv: Path | str,
        threshold: float = 80.0,
    ):
        self.threshold = threshold
        self.attr_df = self._load_attr(Path(attr_csv))
        self.schema_df = self._load_schema(Path(schema_csv))
        self._mapping: Optional[pd.DataFrame] = None

    # ── Loaders ───────────────────────────────────────────────────────────────

    @staticmethod
    def _load_attr(path: Path) -> pd.DataFrame:
        if not path.exists():
            raise FileNotFoundError(f"attribute_list.csv not found: {path}")
        df = pd.read_csv(path)
        # Normalize column names (strip whitespace)
        df.columns = [c.strip() for c in df.columns]
        return df

    @staticmethod
    def _load_schema(path: Path) -> pd.DataFrame:
        if not path.exists():
            raise FileNotFoundError(f"drive_hd.csv not found: {path}")
        df = pd.read_csv(path)
        df.columns = [c.strip() for c in df.columns]
        required = {"table_name", "column_name"}
        if not required.issubset(df.columns):
            raise ValueError(
                f"drive_hd.csv must have columns {required}. Found: {list(df.columns)}"
            )
        return df

    # ── Matching ──────────────────────────────────────────────────────────────

    def _best_match(self, candidates: list[str], source_attr: str = "") -> dict:
        """
        Find the highest-scoring column across all candidates.

        Priority strategy
        -----------------
        1. Exact match on `source_attr` (Source Attribute(ODS)) — score 100, wins immediately.
        2. Fuzzy match across all candidates — picks highest token-sort-ratio score.
        """
        # ── 1. Exact match on Source Attribute(ODS) first ───────────────────────
        if source_attr and not pd.isna(source_attr):
            src = source_attr.strip().lower()
            exact_rows = self.schema_df[
                self.schema_df["column_name"].str.strip().str.lower() == src
            ]
            if not exact_rows.empty:
                row = exact_rows.iloc[0]  # take first exact hit
                return {
                    "score": 100.0,
                    "column_name": str(row["column_name"]),
                    "table_name": str(row["table_name"]),
                    "data_type": row.get("data_type", ""),
                    "matched_by": source_attr,
                }

        # ── 2. Fuzzy match fallback ──────────────────────────────────────────────
        best = {"score": -1.0, "column_name": None, "table_name": None,
                "data_type": None, "matched_by": None}

        for _, schema_row in self.schema_df.iterrows():
            col = str(schema_row["column_name"])
            for cand in candidates:
                if not cand or pd.isna(cand):
                    continue
                s = _score(str(cand), col)
                if s > best["score"]:
                    best = {
                        "score": round(s, 1),
                        "column_name": col,
                        "table_name": schema_row["table_name"],
                        "data_type": schema_row.get("data_type", ""),
                        "matched_by": cand,
                    }
        return best

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self) -> pd.DataFrame:
        """
        Execute the mapping and return a DataFrame with one row per attribute.

        Columns returned
        ----------------
        orig_index, PROCESS_NAME, COMPONENT_NAME, source_attr, attribute_name,
        alias, description, failure_mode, matched_column, matched_table,
        table_alias, data_type, match_score, matched_by, status
        """
        records = []
        for idx, row in self.attr_df.iterrows():
            candidates = [
                str(row.get(c, "")) for c in ATTR_CANDIDATE_COLS if c in row.index
            ]
            candidates = [c for c in candidates if c and c.lower() not in ("nan", "")]

            if not candidates:
                records.append(
                    self._make_row(idx, row, None, 0.0, "no_candidate")
                )
                continue

            source_attr = str(row.get("Source Attribute(ODS)", ""))
            best = self._best_match(candidates, source_attr=source_attr)
            if best["score"] < self.threshold:
                status = "unmatched"
            else:
                status = "matched"

            records.append(self._make_row(idx, row, best, best["score"], status))

        self._mapping = pd.DataFrame(records)
        return self._mapping

    def _make_row(self, idx, row: pd.Series, best: dict | None, score: float, status: str) -> dict:
        table_name = (best or {}).get("table_name", "")
        return {
            "orig_index": idx,
            "PROCESS_LEVEL": row.get("PROCESS_LEVEL", ""),
            "PROCESS_NAME": row.get("PROCESS_NAME", ""),
            "COMPONENT_NAME": row.get("COMPONENT_NAME", ""),
            "source_attr": row.get("Source Attribute(ODS)", ""),
            "attribute_name": row.get("Attribute_Name", ""),
            "alias": row.get("Alias", ""),
            "description": row.get("Description", ""),
            "failure_mode": row.get("failure mode", ""),
            "matched_column": (best or {}).get("column_name", ""),
            "matched_table": table_name,
            "table_alias": TABLE_ALIASES.get(str(table_name), ""),
            "data_type": (best or {}).get("data_type", ""),
            "match_score": score,
            "matched_by": (best or {}).get("matched_by", ""),
            "status": status,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def matched(self) -> pd.DataFrame:
        """Return only matched rows."""
        self._ensure_run()
        return self._mapping[self._mapping["status"] == "matched"].reset_index(drop=True)

    def unmatched(self) -> pd.DataFrame:
        """Return only unmatched rows."""
        self._ensure_run()
        return self._mapping[self._mapping["status"] == "unmatched"].reset_index(drop=True)

    def summary(self) -> str:
        """Human-readable summary string."""
        self._ensure_run()
        total = len(self._mapping)
        n_match = (self._mapping["status"] == "matched").sum()
        n_un = total - n_match
        return (
            f"📊 Mapping summary | threshold={self.threshold:.0f}\n"
            f"  Total attributes : {total}\n"
            f"  ✅ Matched        : {n_match}\n"
            f"  ❌ Unmatched      : {n_un}\n"
        )

    def _ensure_run(self):
        if self._mapping is None:
            self.run()

    # ── Override individual mappings ──────────────────────────────────────────

    def override(self, orig_index: int, column_name: str, table_name: str):
        """
        Manually override a mapping for a specific attribute index.
        Useful for resolving unmatched attributes interactively.
        """
        self._ensure_run()
        mask = self._mapping["orig_index"] == orig_index
        if not mask.any():
            warnings.warn(f"orig_index {orig_index} not found in mapping.")
            return
        self._mapping.loc[mask, "matched_column"] = column_name
        self._mapping.loc[mask, "matched_table"] = table_name
        self._mapping.loc[mask, "table_alias"] = TABLE_ALIASES.get(table_name, "")
        self._mapping.loc[mask, "match_score"] = 100.0
        self._mapping.loc[mask, "matched_by"] = "manual_override"
        self._mapping.loc[mask, "status"] = "matched"
