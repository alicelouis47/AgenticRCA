from __future__ import annotations
import pandas as pd
import trino
from config import TRINO_CONFIG_CSV


class TrinoClient:
    def __init__(self):
        self._cfg = self._load_config()
        self._conn = None

    # ── Config ─────────────────────────────────────────────────────────────────

    def _load_config(self) -> dict:
        defaults = {
            "host": "localhost",
            "port": 8080,
            "user": "analyst",
            "catalog": "hive",
            "schema": "default",
            "auth_type": "none",
            "password": "",
        }
        if not TRINO_CONFIG_CSV.exists():
            return defaults
        try:
            df = pd.read_csv(TRINO_CONFIG_CSV)
            if "parameter" in df.columns and "value" in df.columns:
                cfg = dict(zip(df["parameter"].astype(str), df["value"].astype(str)))
            else:
                cfg = df.iloc[0].to_dict()
            return {**defaults, **{k: v for k, v in cfg.items() if pd.notna(v) and str(v) != "nan"}}
        except Exception:
            return defaults

    def reload_config(self):
        self._cfg = self._load_config()
        self._conn = None

    def get_config(self) -> dict:
        return self._cfg.copy()

    # ── Connection ─────────────────────────────────────────────────────────────

    def _get_conn(self):
        if self._conn is None:
            auth = None
            if str(self._cfg.get("auth_type", "")).lower() == "basic":
                auth = trino.auth.BasicAuthentication(
                    str(self._cfg.get("user", "")),
                    str(self._cfg.get("password", "")),
                )
            self._conn = trino.dbapi.connect(
                host=str(self._cfg["host"]),
                port=int(self._cfg.get("port", 8080)),
                user=str(self._cfg["user"]),
                catalog=str(self._cfg.get("catalog", "hive")),
                schema=str(self._cfg.get("schema", "default")),
                auth=auth,
            )
        return self._conn

    # ── Query ──────────────────────────────────────────────────────────────────

    def execute_query(self, sql: str, limit: int = 1000) -> pd.DataFrame:
        sql_clean = sql.strip().rstrip(";")
        if "limit" not in sql_clean.lower():
            sql_clean = f"{sql_clean} LIMIT {limit}"
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(sql_clean)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        return pd.DataFrame(rows, columns=cols)

    def test_connection(self) -> tuple[bool, str]:
        try:
            self.execute_query("SELECT 1 AS ok", limit=1)
            return True, "✅ Connection successful"
        except Exception as e:
            return False, f"❌ Connection failed: {e}"
