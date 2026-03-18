"""Figure generation tools."""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def plot_chart(
    chart_type: str,
    data: Optional[dict[str, list]] = None,
    file_path: Optional[str] = None,
    x_column: Optional[str] = None,
    y_column: Optional[str] = None,
    title: str = "",
    xlabel: str = "",
    ylabel: str = "",
    figsize: tuple[int, int] = (10, 6),
    style: str = "seaborn-v0_8-whitegrid",
    save_path: Optional[str] = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Create a publication-quality chart."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import pandas as pd

        df = None
        if file_path:
            ext = Path(file_path).suffix.lower()
            if ext == ".csv":
                df = pd.read_csv(file_path)
            elif ext in (".xlsx", ".xls"):
                df = pd.read_excel(file_path)
        elif data:
            df = pd.DataFrame(data)

        if df is None:
            return {
                "error": "No data provided. Specify 'data' or 'file_path'.",
            }

        try:
            plt.style.use(style)
        except Exception:
            plt.style.use("default")

        fig, ax = plt.subplots(figsize=figsize)
        x = df[x_column] if x_column and x_column in df.columns else None
        y = df[y_column] if y_column and y_column in df.columns else None

        if chart_type == "line":
            if x is not None and y is not None:
                ax.plot(x, y, **kwargs)
            else:
                df.plot(ax=ax, **kwargs)
        elif chart_type == "scatter":
            if x is not None and y is not None:
                ax.scatter(x, y, **kwargs)
            else:
                return {"error": "Scatter plot requires x_column and y_column"}
        elif chart_type == "bar":
            if x is not None and y is not None:
                ax.bar(x, y, **kwargs)
            else:
                df.plot.bar(ax=ax, **kwargs)
        elif chart_type == "hist":
            col = df[y_column] if y_column else df.iloc[:, 0]
            ax.hist(col, **kwargs)
        elif chart_type == "box":
            df.plot.box(ax=ax, **kwargs)
        elif chart_type == "pie":
            if y_column:
                df.set_index(x_column or df.columns[0])[y_column].plot.pie(
                    ax=ax,
                    autopct="%1.1f%%",
                    **kwargs,
                )
        elif chart_type == "heatmap":
            numeric_df = df.select_dtypes(include="number")
            im = ax.imshow(numeric_df.corr(), cmap="coolwarm", aspect="auto")
            ax.set_xticks(range(len(numeric_df.columns)))
            ax.set_yticks(range(len(numeric_df.columns)))
            ax.set_xticklabels(numeric_df.columns, rotation=45, ha="right")
            ax.set_yticklabels(numeric_df.columns)
            fig.colorbar(im)
        else:
            return {"error": f"Unknown chart type: {chart_type}"}

        if title:
            ax.set_title(title, fontsize=14, fontweight="bold")
        if xlabel:
            ax.set_xlabel(xlabel)
        if ylabel:
            ax.set_ylabel(ylabel)

        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            return {"path": save_path, "status": "saved"}

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode("utf-8")
        return {"base64_png": b64, "status": "generated"}

    except ImportError as e:
        return {
            "error": f"Missing dependency: {e}. Run: pip install matplotlib pandas",
        }
    except Exception as e:
        logger.exception("Chart generation failed")
        return {"error": f"Chart generation failed: {e}"}


__all__ = ["plot_chart"]
