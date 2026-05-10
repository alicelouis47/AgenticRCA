from __future__ import annotations
import numpy as np
import pandas as pd
from scipy import stats
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL


class RCAEngine:
    def __init__(self):
        self._llm = OpenAI(api_key=OPENAI_API_KEY)

    # ── Anomaly Detection ─────────────────────────────────────────────────────

    def _detect_zscore(self, series: pd.Series, threshold: float) -> pd.Series:
        z = np.abs(stats.zscore(series.dropna()))
        mask = pd.Series(False, index=series.index)
        mask.iloc[series.dropna().index] = z > threshold
        return mask

    def _detect_iqr(self, series: pd.Series, threshold: float) -> pd.Series:
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        return (series < q1 - threshold * iqr) | (series > q3 + threshold * iqr)

    def _detect_changepoint(self, series: pd.Series, _threshold: float) -> pd.Series:
        try:
            import ruptures as rpt
            model = rpt.Pelt(model="rbf").fit(series.values)
            breaks = model.predict(pen=10)
            mask = pd.Series(False, index=series.index)
            for bp in breaks[:-1]:
                if bp < len(series):
                    mask.iloc[bp] = True
            return mask
        except ImportError:
            return self._detect_zscore(series, _threshold)

    # ── LLM Narrative ─────────────────────────────────────────────────────────

    def _llm_analysis(self, df: pd.DataFrame, metric_col: str, anomaly_df: pd.DataFrame) -> str:
        summary = df[metric_col].describe().to_string()
        anomaly_preview = anomaly_df.head(5).to_string(index=False) if not anomaly_df.empty else "None"
        prompt = (
            f"You are an RCA expert. Analyze the following metric '{metric_col}'.\n\n"
            f"Statistics:\n{summary}\n\n"
            f"Detected anomalies (top 5):\n{anomaly_preview}\n\n"
            f"Provide a concise root cause analysis in 3-5 bullet points."
        )
        resp = self._llm.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
        )
        return resp.choices[0].message.content or ""

    # ── Main analyze ──────────────────────────────────────────────────────────

    def analyze(
        self,
        df: pd.DataFrame,
        metric_col: str,
        time_col: str | None = None,
        method: str = "zscore",
        threshold: float = 2.5,
    ) -> dict:
        if metric_col not in df.columns:
            raise ValueError(f"Column '{metric_col}' not found. Available: {list(df.columns)}")

        series = pd.to_numeric(df[metric_col], errors="coerce")

        if method == "iqr":
            mask = self._detect_iqr(series, threshold)
        elif method == "changepoint":
            mask = self._detect_changepoint(series, threshold)
        else:
            mask = self._detect_zscore(series, threshold)

        anomaly_df = df[mask].copy()
        anomaly_df["_is_anomaly"] = True

        llm_text = self._llm_analysis(df, metric_col, anomaly_df)

        return {
            "total_points": len(df),
            "anomaly_count": int(mask.sum()),
            "anomaly_rate": float(mask.mean()),
            "anomaly_indices": list(anomaly_df.index[:20]),
            "anomaly_df": anomaly_df,
            "metric_col": metric_col,
            "time_col": time_col,
            "method": method,
            "threshold": threshold,
            "llm_analysis": llm_text,
        }
