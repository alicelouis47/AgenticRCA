from __future__ import annotations

import pandas as pd
from sqlalchemy import create_engine, text
from config import TRINO_CONFIG_CSV


class TrinoClient:
    def __init__(self):
        self._cfg = self._load_config()
        self._engine = None

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
            "http_scheme": "http",
            "verify": "true",
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
        self._engine = None

    def get_config(self) -> dict:
        return self._cfg.copy()

    # ── Engine ─────────────────────────────────────────────────────────────────

    def _get_engine(self):
        """Build a SQLAlchemy engine using the trino:// dialect."""
        if self._engine is None:
            cfg = self._cfg
            user = str(cfg.get("user", "analyst"))
            password = str(cfg.get("password", ""))
            host = str(cfg.get("host", "localhost"))
            port = int(cfg.get("port", 8080))
            catalog = str(cfg.get("catalog", "hive"))
            schema = str(cfg.get("schema", "default"))
            http_scheme = str(cfg.get("http_scheme", "http"))
            verify = str(cfg.get("verify", "true"))

            # trino://user[:password]@host:port/catalog/schema
            if password and str(cfg.get("auth_type", "none")).lower() == "basic":
                userinfo = f"{user}:{password}"
            else:
                userinfo = user

            url = f"trino://{userinfo}@{host}:{port}/{catalog}/{schema}"

            connect_args: dict = {
                "http_scheme": http_scheme,
            }

            # verify: "true" / "false" / path-to-cert
            v_lower = verify.lower()
            if v_lower == "true":
                connect_args["verify"] = True
            elif v_lower == "false":
                connect_args["verify"] = False
            else:
                connect_args["verify"] = verify  # path to CA bundle

            self._engine = create_engine(url, connect_args=connect_args)
        return self._engine

    # ── Query ──────────────────────────────────────────────────────────────────

    def execute_query(self, sql: str, limit: int = 1000) -> pd.DataFrame:
        sql_clean = sql.strip().rstrip(";")
        if "limit" not in sql_clean.lower():
            sql_clean = f"{sql_clean} LIMIT {limit}"
        engine = self._get_engine()
        with engine.connect() as conn:
            result = conn.execute(text(sql_clean))
            cols = list(result.keys())
            rows = result.fetchall()
        return pd.DataFrame(rows, columns=cols)

    def test_connection(self) -> tuple[bool, str]:
        try:
            self.execute_query("SELECT 1 AS ok", limit=1)
            return True, "✅ Connection successful"
        except Exception as e:
            return False, f"❌ Connection failed: {e}"
