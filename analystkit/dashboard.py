"""Self-contained HTML dashboard renderer.

Why HTML and not a .pbix: a portfolio needs a LIVE artefact a hiring manager can
click without installing Power BI. Each project also ships a powerbi/ folder with
the star schema and DAX so the same thing can be rebuilt natively.

Everything is inlined (charts as base64 PNG), so the file works offline and
survives a strict CSP.
"""
from __future__ import annotations
import base64
import html
from dataclasses import dataclass, field
from pathlib import Path
import pandas as pd


@dataclass
class Kpi:
    label: str
    value: str
    note: str = ""
    tone: str = "neutral"   # neutral | good | warning | serious | critical


@dataclass
class Page:
    name: str
    blocks: list = field(default_factory=list)


class Dashboard:
    def __init__(self, title: str, subtitle: str, footnote: str = "",
                 eyebrow: str = ""):
        self.title, self.subtitle, self.footnote = title, subtitle, footnote
        self.eyebrow = eyebrow
        self.pages: list[Page] = []

    def page(self, name: str) -> Page:
        p = Page(name)
        self.pages.append(p)
        return p

    # ---- block builders -------------------------------------------------
    @staticmethod
    def kpis(page: Page, items: list[Kpi]):
        page.blocks.append(("kpis", items))

    @staticmethod
    def chart(page: Page, img_path, caption: str = "", wide: bool = False):
        b64 = base64.b64encode(Path(img_path).read_bytes()).decode()
        page.blocks.append(("chart", {"src": "data:image/png;base64," + b64,
                                      "caption": caption, "wide": wide}))

    @staticmethod
    def table(page: Page, df: pd.DataFrame, caption: str = "", max_rows: int = 40):
        page.blocks.append(("table", {"df": df.head(max_rows), "caption": caption,
                                      "truncated": len(df) > max_rows,
                                      "total": len(df), "shown": min(max_rows, len(df))}))

    @staticmethod
    def note(page: Page, heading: str, body_md: str):
        page.blocks.append(("note", {"heading": heading, "body": body_md}))

    # ---- render ---------------------------------------------------------
    def _render_blocks(self, page: Page) -> str:
        out = []
        for kind, payload in page.blocks:
            if kind == "kpis":
                cells = "".join(
                    '<div class="kpi tone-' + html.escape(k.tone) + '">'
                    '<div class="kpi-label">' + html.escape(k.label) + '</div>'
                    '<div class="kpi-value">' + html.escape(k.value) + '</div>'
                    '<div class="kpi-note">' + html.escape(k.note) + '</div></div>'
                    for k in payload)
                out.append('<div class="kpi-row">' + cells + '</div>')

            elif kind == "chart":
                cls = "card chart wide" if payload["wide"] else "card chart"
                cap = ('<p class="cap">' + html.escape(payload["caption"]) + '</p>'
                       if payload["caption"] else "")
                out.append('<figure class="' + cls + '"><img src="' + payload["src"]
                           + '" alt="' + html.escape(payload["caption"]) + '">'
                           + cap + '</figure>')

            elif kind == "table":
                df = payload["df"]
                head = "".join("<th>" + html.escape(str(c)) + "</th>" for c in df.columns)
                rows = "".join(
                    "<tr>" + "".join(
                        "<td>" + html.escape("" if pd.isna(v) else str(v)) + "</td>"
                        for v in row) + "</tr>"
                    for row in df.itertuples(index=False, name=None))
                extra = ""
                if payload["truncated"]:
                    extra = ('<p class="cap">Showing ' + f'{payload["shown"]:,}'
                             + " of " + f'{payload["total"]:,}'
                             + " rows. Full table in outputs/tables/.</p>")
                cap = ('<p class="cap">' + html.escape(payload["caption"]) + '</p>'
                       if payload["caption"] else "")
                out.append('<div class="card wide">' + cap + '<div class="tw"><table>'
                           '<thead><tr>' + head + '</tr></thead><tbody>' + rows
                           + "</tbody></table></div>" + extra + "</div>")

            elif kind == "note":
                paras = []
                for chunk in payload["body"].strip().split("\n\n"):
                    lines = [ln.strip() for ln in chunk.strip().split("\n") if ln.strip()]
                    if lines and all(ln.startswith("- ") for ln in lines):
                        items = "".join("<li>" + _md(ln[2:]) + "</li>" for ln in lines)
                        paras.append("<ul>" + items + "</ul>")
                    else:
                        paras.append("<p>" + _md(" ".join(lines)) + "</p>")
                out.append('<div class="card wide note"><h3>'
                           + html.escape(payload["heading"]) + "</h3>"
                           + "".join(paras) + "</div>")
        return "\n".join(out)

    def render(self, path: str | Path) -> Path:
        tabs = "".join(
            '<button class="tab' + (" on" if i == 0 else "") + '" data-i="' + str(i)
            + '">' + html.escape(p.name) + "</button>"
            for i, p in enumerate(self.pages))
        panes = "".join(
            '<section class="pane' + (" on" if i == 0 else "") + '" data-i="' + str(i)
            + '">' + self._render_blocks(p) + "</section>"
            for i, p in enumerate(self.pages))
        doc = (_SHELL
               .replace("@@TITLE@@", html.escape(self.title))
               .replace("@@SUBTITLE@@", html.escape(self.subtitle))
               .replace("@@FOOTNOTE@@", html.escape(self.footnote))
               .replace("@@EYEBROW@@", html.escape(self.eyebrow))
               .replace("@@CSS@@", _CSS)
               .replace("@@TABS@@", tabs)
               .replace("@@PANES@@", panes))
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(doc, encoding="utf-8")
        return path


def _md(s: str) -> str:
    s = html.escape(s)
    while s.count("**") >= 2:
        s = s.replace("**", "<strong>", 1).replace("**", "</strong>", 1)
    while s.count("`") >= 2:
        s = s.replace("`", "<code>", 1).replace("`", "</code>", 1)
    return s


_CSS = """
/* Light palette is the complete set. Dark blocks below redefine TOKENS ONLY,
   under both the media query (OS setting, un-stamped root) and the [data-theme]
   stamp (explicit toggle), so all three viewer states resolve as a set. */
:root{
  color-scheme:light;
  --plane:#f2f2ef;          /* page ground - cool-biased, not a default grey */
  --surface:#fcfcfb;        /* matches the matplotlib chart surface exactly */
  --ink:#12140f;
  --ink2:#4e5148;
  --muted:#83867c;
  --hair:#e2e2db;           /* hairline */
  --rule:#c8c9c0;           /* heavier rule */
  --accent:#2a78d6;         /* == categorical slot 1, so chrome and data agree */
  --good:#0ca30c;--warn:#fab219;--serious:#ec835a;--crit:#d03b3b;
  --shadow:0 1px 2px rgba(18,20,15,.04);
  --display:"Source Serif 4",Georgia,"Times New Roman",serif;
  --ui:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,"Cascadia Mono",Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  color-scheme:dark;
  --plane:#0e0f0d;--surface:#1a1a19;--ink:#f6f6f2;--ink2:#c0c1b6;
  --muted:#83867c;--hair:#2b2c29;--rule:#3b3c37;--accent:#3987e5;
  --shadow:0 1px 2px rgba(0,0,0,.3);
}}
:root[data-theme="dark"]{
  color-scheme:dark;
  --plane:#0e0f0d;--surface:#1a1a19;--ink:#f6f6f2;--ink2:#c0c1b6;
  --muted:#83867c;--hair:#2b2c29;--rule:#3b3c37;--accent:#3987e5;
  --shadow:0 1px 2px rgba(0,0,0,.3);
}
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--ink);
  font-family:var(--ui);font-size:15px;line-height:1.55;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:1200px;margin:0 auto;padding:0 20px 72px}

/* --- masthead: a report banner, not a hero ------------------------------ */
.mast{padding:34px 0 22px;border-bottom:2px solid var(--ink)}
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.13em;
  text-transform:uppercase;color:var(--accent);margin:0 0 11px;font-weight:500}
.mast h1{font-family:var(--display);font-weight:600;
  font-size:clamp(26px,4.1vw,42px);line-height:1.1;letter-spacing:-.015em;
  margin:0 0 12px;text-wrap:balance;max-width:19ch}
.mast p{margin:0;color:var(--ink2);font-size:15.5px;max-width:66ch;line-height:1.6}

/* --- tabs --------------------------------------------------------------- */
nav{display:flex;gap:0;flex-wrap:wrap;margin:0 0 26px;
  border-bottom:1px solid var(--hair);overflow-x:auto}
.tab{background:none;border:0;border-bottom:2px solid transparent;
  color:var(--muted);font-family:var(--mono);font-size:12px;letter-spacing:.05em;
  text-transform:uppercase;padding:14px 16px 12px;cursor:pointer;
  white-space:nowrap;transition:color .12s}
.tab:first-child{padding-left:0}
.tab:hover{color:var(--ink)}
.tab:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
.tab.on{color:var(--ink);border-bottom-color:var(--accent)}

.pane{display:none;gap:18px;grid-template-columns:repeat(2,minmax(0,1fr))}
.pane.on{display:grid}
@media(max-width:860px){.pane.on{grid-template-columns:1fr}}

/* --- KPI readout: hairline-divided strip, not floating cards ------------- */
.kpi-row{grid-column:1/-1;display:grid;
  grid-template-columns:repeat(auto-fit,minmax(172px,1fr));
  border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);
  background:var(--surface)}
.kpi{padding:17px 18px;border-left:1px solid var(--hair)}
.kpi:first-child{border-left:0}
.kpi-label{font-family:var(--mono);font-size:10.5px;text-transform:uppercase;
  letter-spacing:.09em;color:var(--muted)}
.kpi-value{font-family:var(--mono);font-size:25px;font-weight:600;
  letter-spacing:-.025em;margin:7px 0 4px;font-variant-numeric:tabular-nums;
  line-height:1.05}
.kpi-note{font-size:12.5px;color:var(--ink2);line-height:1.4}
.tone-good .kpi-value{color:var(--good)}
.tone-warning .kpi-value{color:var(--warn)}
.tone-serious .kpi-value{color:var(--serious)}
.tone-critical .kpi-value{color:var(--crit)}
/* status colour never carries meaning alone: a leading glyph doubles it */
.tone-good .kpi-label::before{content:"+ "}
.tone-warning .kpi-label::before{content:"! "}
.tone-serious .kpi-label::before{content:"! "}
.tone-critical .kpi-label::before{content:"x "}

/* --- cards -------------------------------------------------------------- */
.card{background:var(--surface);border:1px solid var(--hair);border-radius:4px;
  padding:18px;margin:0;min-width:0;box-shadow:var(--shadow)}
.card.wide{grid-column:1/-1}
.chart img{width:100%;height:auto;display:block}
.cap{font-family:var(--ui);font-size:12.5px;color:var(--muted);margin:12px 0 0;
  line-height:1.5;max-width:88ch}

/* --- tables ------------------------------------------------------------- */
.tw{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:12.5px}
th{text-align:left;font-family:var(--mono);font-size:10.5px;text-transform:uppercase;
  letter-spacing:.07em;color:var(--muted);border-bottom:1px solid var(--rule);
  padding:9px 14px 9px 0;white-space:nowrap;font-weight:500}
td{padding:8px 14px 8px 0;border-bottom:1px solid var(--hair);color:var(--ink2);
  white-space:nowrap;font-variant-numeric:tabular-nums;
  font-family:var(--mono);font-size:11.8px}
td:first-child{color:var(--ink)}
tbody tr:hover td{color:var(--ink);background:var(--plane)}

/* --- prose notes -------------------------------------------------------- */
.note h3{font-family:var(--display);font-weight:600;margin:0 0 11px;
  font-size:19px;letter-spacing:-.01em;text-wrap:balance}
.note p,.note li{font-size:14.5px;color:var(--ink2);margin:0 0 11px;
  line-height:1.62;max-width:70ch}
.note ul{margin:0 0 4px;padding-left:19px}
.note li{margin-bottom:7px}
.note strong{color:var(--ink);font-weight:600}
code{font-family:var(--mono);background:var(--plane);padding:1.5px 5px;
  border-radius:3px;font-size:12.5px;color:var(--ink)}

footer{margin-top:40px;padding-top:18px;border-top:1px solid var(--hair);
  color:var(--muted);font-size:12.5px;max-width:82ch;line-height:1.6}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
"""

_SHELL = """<title>@@TITLE@@</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,600&display=swap">
<style>@@CSS@@</style>
<div class="wrap">
<header class="mast">
<p class="eyebrow">@@EYEBROW@@</p>
<h1>@@TITLE@@</h1><p>@@SUBTITLE@@</p></header>
<nav>@@TABS@@</nav>
@@PANES@@
<footer>@@FOOTNOTE@@</footer>
</div>
<script>
document.querySelectorAll('.tab').forEach(function (t) {
  t.addEventListener('click', function () {
    document.querySelectorAll('.tab').forEach(function (x) { x.classList.remove('on'); });
    document.querySelectorAll('.pane').forEach(function (x) { x.classList.remove('on'); });
    t.classList.add('on');
    var sel = '.pane[data-i="' + t.dataset.i + '"]';
    document.querySelector(sel).classList.add('on');
  });
});
</script>
"""
