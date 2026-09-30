from __future__ import annotations
from pathlib import Path
import pandas as pd


def project_paths(project_dir: str | Path) -> dict:
    p = Path(project_dir)
    paths = {
        "root": p, "raw": p / "data" / "raw", "processed": p / "data" / "processed",
        "charts": p / "outputs" / "charts", "tables": p / "outputs" / "tables",
        "sql": p / "sql", "dashboard": p / "dashboard", "outputs": p / "outputs",
    }
    for v in paths.values():
        v.mkdir(parents=True, exist_ok=True)
    return paths


def write_table(df: pd.DataFrame, path: str | Path, index: bool = False) -> Path:
    """Every number that appears in a chart or a summary must also exist as a
    CSV a reviewer can open. That is the reconciliation rule."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=index)
    return path


def run_sql_file(con, path, verbose: bool = False) -> None:
    """Execute a .sql file statement by statement.

    WHY NOT con.execute(whole_file): DuckDB's Python API runs one statement per
    call, and when a file fails you want to know WHICH statement failed rather
    than being handed a parser error against 200 lines.

    WHY COMMENTS ARE STRIPPED BEFORE SPLITTING, not after. Splitting the raw
    text on ';' breaks the moment a comment contains a semicolon - and prose
    comments contain semicolons all the time. The remainder of the comment then
    arrives at the parser as if it were SQL. Strip first, split second.
    """
    import re
    from pathlib import Path as _P
    sql = _P(path).read_text(encoding="utf-8")
    # remove line comments, keeping the newlines so error line numbers survive
    sql = re.sub(r"--[^\n]*", "", sql)
    for stmt in sql.split(";"):
        if stmt.strip():
            if verbose:
                first = next((l for l in stmt.strip().splitlines() if l.strip()), "")
                print(f"    {first[:70]}")
            con.execute(stmt)
