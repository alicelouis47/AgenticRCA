from __future__ import annotations
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots


class Plotter:
    COLORS = {
        "primary": "#6366f1",
        "anomaly": "#ef4444",
        "bg": "#0f172a",
        "grid": "#1e293b",
        "text": "#e2e8f0",
    }

    def _base_layout(self, title: str) -> dict:
        return dict(
            title=dict(text=title, font=dict(size=18, color=self.COLORS["text"])),
            paper_bgcolor=self.COLORS["bg"],
            plot_bgcolor=self.COLORS["grid"],
            font=dict(color=self.COLORS["text"], family="Inter, sans-serif"),
            xaxis=dict(gridcolor="#334155", zerolinecolor="#334155"),
            yaxis=dict(gridcolor="#334155", zerolinecolor="#334155"),
            legend=dict(bgcolor="rgba(0,0,0,0.3)", bordercolor="#334155"),
            margin=dict(l=60, r=30, t=60, b=50),
            hovermode="x unified",
        )

    def _add_anomaly_markers(self, fig, df: pd.DataFrame, rca_report: dict, y_col: str, x_col: str | None):
        anomaly_df: pd.DataFrame = rca_report.get("anomaly_df", pd.DataFrame())
        if anomaly_df.empty:
            return
        x_vals = anomaly_df[x_col] if x_col and x_col in anomaly_df.columns else anomaly_df.index
        fig.add_trace(
            go.Scatter(
                x=x_vals,
                y=anomaly_df[y_col] if y_col in anomaly_df.columns else [None] * len(anomaly_df),
                mode="markers",
                name="⚠️ Anomaly",
                marker=dict(color=self.COLORS["anomaly"], size=10, symbol="x"),
            )
        )

    def create_plot(
        self,
        df: pd.DataFrame,
        plot_type: str,
        x_col: str | None,
        y_col: str,
        title: str,
        rca_report: dict | None = None,
    ) -> go.Figure:
        layout = self._base_layout(title)

        if plot_type == "time_series":
            x = df[x_col] if x_col and x_col in df.columns else df.index
            fig = go.Figure(layout=layout)
            fig.add_trace(
                go.Scatter(
                    x=x, y=df[y_col],
                    mode="lines+markers",
                    name=y_col,
                    line=dict(color=self.COLORS["primary"], width=2),
                    marker=dict(size=4),
                )
            )
            if rca_report:
                self._add_anomaly_markers(fig, df, rca_report, y_col, x_col)

        elif plot_type == "bar":
            x = df[x_col] if x_col and x_col in df.columns else df.index
            fig = go.Figure(layout=layout)
            fig.add_trace(go.Bar(x=x, y=df[y_col], name=y_col, marker_color=self.COLORS["primary"]))

        elif plot_type == "histogram":
            fig = go.Figure(layout=layout)
            fig.add_trace(go.Histogram(x=df[y_col], name=y_col, marker_color=self.COLORS["primary"]))

        elif plot_type == "scatter":
            x = df[x_col] if x_col and x_col in df.columns else df.index
            fig = go.Figure(layout=layout)
            fig.add_trace(
                go.Scatter(x=x, y=df[y_col], mode="markers", name=y_col,
                           marker=dict(color=self.COLORS["primary"], size=6))
            )
            if rca_report:
                self._add_anomaly_markers(fig, df, rca_report, y_col, x_col)

        elif plot_type == "box":
            fig = go.Figure(layout=layout)
            fig.add_trace(go.Box(y=df[y_col], name=y_col, marker_color=self.COLORS["primary"]))

        elif plot_type == "heatmap":
            numeric_df = df.select_dtypes(include="number")
            corr = numeric_df.corr()
            fig = go.Figure(layout=layout)
            fig.add_trace(
                go.Heatmap(z=corr.values, x=corr.columns, y=corr.columns,
                           colorscale="RdBu", zmid=0)
            )

        else:
            raise ValueError(f"Unsupported plot_type: {plot_type}")

        fig.update_layout(**layout)
        return fig
