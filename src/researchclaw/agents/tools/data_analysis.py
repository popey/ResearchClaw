"""Data analysis tools.

Provides functions for statistical analysis and data querying aimed at
academic research workflows.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def data_describe(
    file_path: str,
    columns: Optional[list[str]] = None,
    head_rows: int = 5,
) -> dict[str, Any]:
    """Load and describe a data file (CSV, Excel, JSON, TSV).

    Parameters
    ----------
    file_path:
        Path to the data file.
    columns:
        Optional subset of columns to describe.
    head_rows:
        Number of rows to show in the preview (default 5).

    Returns
    -------
    dict
        Data description including shape, dtypes, statistics, and preview.
    """
    try:
        import pandas as pd

        # Auto-detect file type
        ext = Path(file_path).suffix.lower()
        read_funcs = {
            ".csv": pd.read_csv,
            ".tsv": lambda f: pd.read_csv(f, sep="\t"),
            ".xlsx": pd.read_excel,
            ".xls": pd.read_excel,
            ".json": pd.read_json,
            ".parquet": pd.read_parquet,
        }

        reader = read_funcs.get(ext)
        if reader is None:
            return {"error": f"Unsupported file type: {ext}"}

        df = reader(file_path)

        if columns:
            missing = [c for c in columns if c not in df.columns]
            if missing:
                return {"error": f"Columns not found: {missing}"}
            df = df[columns]

        # Build description
        result: dict[str, Any] = {
            "shape": {"rows": df.shape[0], "columns": df.shape[1]},
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "preview": df.head(head_rows).to_string(),
            "missing_values": df.isnull().sum().to_dict(),
        }

        # Add statistics for numeric columns
        numeric_df = df.select_dtypes(include="number")
        if not numeric_df.empty:
            result["statistics"] = numeric_df.describe().to_dict()

        return result

    except ImportError:
        return {"error": "pandas not installed. Run: pip install pandas"}
    except Exception as e:
        logger.exception("Data describe failed")
        return {"error": f"Failed to describe data: {e}"}


def data_query(
    file_path: str,
    query: str,
    output_format: str = "text",
) -> dict[str, Any]:
    """Query a data file using pandas expressions.

    Parameters
    ----------
    file_path:
        Path to the data file.
    query:
        Pandas query string (e.g. ``"age > 25 and score >= 90"``) or
        a Python expression using ``df`` (e.g. ``"df.groupby('category').mean()"``).
    output_format:
        ``"text"`` (default), ``"csv"``, or ``"json"``.

    Returns
    -------
    dict
        Query result with ``data``, ``shape``, and ``preview``.
    """
    try:
        import pandas as pd

        ext = Path(file_path).suffix.lower()
        if ext == ".csv":
            df = pd.read_csv(file_path)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(file_path)
        elif ext == ".json":
            df = pd.read_json(file_path)
        elif ext == ".tsv":
            df = pd.read_csv(file_path, sep="\t")
        else:
            return {"error": f"Unsupported file type: {ext}"}

        # Try pandas query first, then eval
        try:
            result_df = df.query(query)
        except Exception:
            # Allow more complex expressions
            local_vars = {"df": df, "pd": pd}
            import numpy as np

            local_vars["np"] = np
            result = eval(
                query,
                {"__builtins__": {}},
                local_vars,
            )  # noqa: S307
            if isinstance(result, pd.DataFrame):
                result_df = result
            elif isinstance(result, pd.Series):
                result_df = result.to_frame()
            else:
                return {"data": str(result), "type": type(result).__name__}

        if output_format == "csv":
            return {
                "data": result_df.to_csv(index=False),
                "shape": list(result_df.shape),
            }
        elif output_format == "json":
            return {
                "data": result_df.to_json(orient="records"),
                "shape": list(result_df.shape),
            }
        else:
            return {
                "data": result_df.to_string(),
                "shape": list(result_df.shape),
                "preview": result_df.head(20).to_string(),
            }

    except ImportError:
        return {"error": "pandas not installed. Run: pip install pandas"}
    except Exception as e:
        logger.exception("Data query failed")
        return {"error": f"Query failed: {e}"}
