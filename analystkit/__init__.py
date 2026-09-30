"""analystkit - shared plumbing for the nine portfolio projects.

Deliberately small. Three jobs:
  1. One visual system for every chart (theme.py)
  2. One place to write chart/table outputs (io.py)
  3. One HTML dashboard renderer (dashboard.py)

Nothing analytical lives here. Analysis belongs in each project's src/.
"""
from .theme import PALETTE, INK, STATUS, SEQ_BLUE, apply_theme, save_fig, fmt_gbp, fmt_int, fmt_pct
from .io import write_table, project_paths, run_sql_file
from .dashboard import Dashboard, Kpi

__all__ = [
    "PALETTE", "INK", "STATUS", "SEQ_BLUE", "apply_theme", "save_fig",
    "fmt_gbp", "fmt_int", "fmt_pct", "write_table", "project_paths",
    "Dashboard", "Kpi",
]
