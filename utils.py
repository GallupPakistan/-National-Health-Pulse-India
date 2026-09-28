"""Shared helpers for the National Health Pulse India dashboard (NSS 80th Round, Sch 25.0).

Design rules used everywhere in this app
----------------------------------------
* Every estimate is weighted (``final_weight`` in the master file, ``wt`` in the detail files).
* Rates use the official NSS definitions so they can be reconciled with Report No. 596
  (see the "Method & Checks" page, which recomputes the headline numbers live).
* Loaded data frames are cached and SHARED - never modify them in place, use ``.assign``.
"""
import json
import re
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------
# COLORS
# ---------------------------------------------------------------------
PALETTE = ["#0F766E", "#F97316", "#2563EB", "#DB2777", "#7C3AED",
           "#EAB308", "#059669", "#DC2626", "#0891B2", "#65A30D"]
px.defaults.color_discrete_sequence = PALETTE

COLOR_SECTOR = {"Rural": "#2563EB", "Urban": "#F97316"}
COLOR_GENDER = {"male": "#0F766E", "female": "#DB2777", "transgender": "#7C3AED"}

NAVY = "#0B1F3A"
NAVY_LIGHT = "#132A4D"
ACCENT = "#F97316"

# ---------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------
DATA_DIR = Path(__file__).parent / "data"

# A state is only ranked / flagged when it has at least this many unweighted
# sample records - tiny samples give unstable averages (e.g. a lowest-cost
# "state" that is really 40 hospital cases).
MIN_N = 100

# 16 households (46 persons) carry state code 99 in the source files. Their NSS
# regions (021/022) belong exclusively to Himachal Pradesh, so they are
# re-assigned there instead of being silently dropped. Set to {} to disable.
STATE_RECODE = {"99": "Himachal Pradesh"}

# Official NSS age groups (Report 596) - 0 means "under 1 year", so it is INCLUDED in 0-4.
AGE_BINS = [-1, 4, 14, 29, 44, 59, 200]
AGE_LABELS = ["0-4", "5-14", "15-29", "30-44", "45-59", "60+"]
AGE_RANGES = {"0-4": (0, 4), "5-14": (5, 14), "15-29": (15, 29),
              "30-44": (30, 44), "45-59": (45, 59), "60+": (60, 200)}

_AGE_COLS = {"Age(in years)", "b3c5", "b6i3", "b8i3", "b10i3", "b11c2", "b4c4", "age_years"}

# column roles per dataset: state, sector, gender, age, weight
FIELDS = {
    "master":    dict(state="state", sector="sector", gender="Gender", age="Age(in years)", w="final_weight"),
    "person":    dict(state="st", sector="sec", gender="b3c4", age="b3c5", w="wt"),
    "household": dict(state="st", sector="sec", gender=None, age=None, w="wt"),
    "hosp":      dict(state="st", sector="sec", gender="gender", age="age_years", w="wt"),
    "ailment":   dict(state="st", sector="sec", gender="gender", age="age_years", w="wt"),
    "vacc":      dict(state="st", sector="sec", gender="person_b3c4", age="b10i3", w="wt"),
    "ante":      dict(state="st", sector="sec", gender=None, age="b11c2", w="wt"),
    "deaths":    dict(state="st", sector="sec", gender="b4c3", age="b4c4", w="wt"),
}

# hospitalisation / ailment tables: (member serial column, own age column)
_EVENT_LINK = {"hospitalization_cases_full.csv": ("b6i2", "b6i3"),
               "ailment_spells_full.csv": ("b8i2", "b8i3")}


# ---------------------------------------------------------------------
# DATA LOADING  (usecols + category dtype keep memory low)
# ---------------------------------------------------------------------
def _is_lfs_pointer(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(40).startswith(b"version https://git-lfs")
    except OSError:
        return False


def _postprocess(name: str, df: pd.DataFrame) -> pd.DataFrame:
    for c in ("state", "st"):
        if c in df.columns and STATE_RECODE:
            txt = df[c].astype(str).str.strip()
            df[c] = txt.map(lambda s: STATE_RECODE.get(s, s)).where(df[c].notna())
    for c in _AGE_COLS & set(df.columns):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # Schedule 25.0, Block 8 item 9: code 5 = "no treatment" (missing from the codebook file)
    if name == "ailment_spells_full.csv" and "b8i9" in df.columns:
        df["b8i9"] = df["b8i9"].astype(str).replace({"5": "no treatment", "5.0": "no treatment"}) \
                                .where(df["b8i9"].notna())
    # text columns -> category (big memory saving)
    for c in df.columns:
        if df[c].dtype == object or str(df[c].dtype) in ("str", "string"):
            if df[c].nunique(dropna=True) <= 5000:
                df[c] = df[c].astype("category")
    return df


@st.cache_resource(show_spinner="Loading data…")
def _read_csv(name: str, cols) -> pd.DataFrame:
    path = DATA_DIR / name
    header = pd.read_csv(path, nrows=0).columns.tolist()
    use = None if cols is None else [c for c in cols if c in header]
    if use is not None and not use:
        return pd.DataFrame()
    df = pd.read_csv(path, usecols=use, low_memory=False)
    return _postprocess(name, df)


@st.cache_resource(show_spinner="Loading data…")
def _read_events(name: str, cols) -> pd.DataFrame:
    """Hospitalisation / ailment tables + complete `age_years` and `gender`.

    Age comes from the event's own age column (always filled). Gender comes from the
    person roster; members who died during the year are not in that roster, so their
    gender is taken from the deaths table (serial numbers 91+)."""
    link, agec = _EVENT_LINK[name]
    need = set(cols or []) | {"hhid", link, agec, "person_b3c4"}
    df = _read_csv(name, tuple(sorted(need))).copy()
    df["age_years"] = pd.to_numeric(df[agec], errors="coerce")
    gender = df["person_b3c4"].astype(object) if "person_b3c4" in df.columns else pd.Series(np.nan, index=df.index, dtype=object)
    dpath = DATA_DIR / "deaths_full.csv"
    if dpath.exists() and not _is_lfs_pointer(dpath):
        d = _read_csv("deaths_full.csv", ("hhid", "b4c1", "b4c3"))
        if not d.empty:
            d = d[pd.to_numeric(d["hhid"], errors="coerce") > 0].copy()   # negative = placeholder ids
            d["hhid"] = pd.to_numeric(d["hhid"], errors="coerce")
            d = d.rename(columns={"b4c1": link, "b4c3": "_dg"}).drop_duplicates(["hhid", link])
            d["_dg"] = d["_dg"].astype(object)
            tmp = df[["hhid", link]].copy()
            tmp["hhid"] = pd.to_numeric(tmp["hhid"], errors="coerce")
            tmp = tmp.merge(d, on=["hhid", link], how="left")
            gender = gender.where(gender.notna(), tmp["_dg"].values)
    df["gender"] = pd.Series(gender.values, index=df.index).astype("category")
    return df


def data_status(name: str):
    """(ok, message) - is `name` present in data/ and a real CSV (not a Git-LFS pointer)?"""
    path = DATA_DIR / name
    if not path.exists():
        return False, f"`{name}` not found in the `data/` folder."
    if _is_lfs_pointer(path):
        return False, (f"`{name}` is a Git-LFS *pointer* (a ~130-byte text stub), not the real data. "
                       "GitHub's 'Download ZIP' does not include LFS files - copy the real CSVs into `data/` "
                       "or use `git lfs pull` (see README).")
    return True, ""


def require(name: str, cols=None, events: bool = False) -> pd.DataFrame:
    """Load a CSV from data/ (only `cols`) or stop the page with a clear message."""
    ok, msg = data_status(name)
    if not ok:
        st.error(msg)
        st.stop()
    cols_t = tuple(cols) if cols is not None else None
    df = _read_events(name, cols_t) if events else _read_csv(name, cols_t)
    if df.empty:
        st.error(f"`{name}` could not be read (none of the expected columns were found).")
        st.stop()
    return df


def has(df, *cols):
    return len(df) > 0 and all(c in df.columns for c in cols)


# ---------------------------------------------------------------------
# WEIGHTED STATISTICS
# ---------------------------------------------------------------------
def _num(s):
    return pd.to_numeric(s, errors="coerce")


def wsum(d: pd.DataFrame, w: str) -> float:
    return float(_num(d[w]).sum())


def weighted_mean(df: pd.DataFrame, col: str, weight: str) -> float:
    x, w = _num(df[col]), _num(df[weight])
    ok = x.notna() & w.notna()
    tot = w[ok].sum()
    return float((x[ok] * w[ok]).sum() / tot) if tot else float("nan")


def weighted_share(d: pd.DataFrame, mask, weight: str, universe=None) -> float:
    """Weighted % of `universe` (default: all rows) for which `mask` is True."""
    w = _num(d[weight])
    u = pd.Series(True, index=d.index) if universe is None else universe
    den = w[u].sum()
    return float(w[u & mask].sum() / den * 100) if den else float("nan")


def weighted_pct(df: pd.DataFrame, group_col: str, weight: str) -> pd.DataFrame:
    d = df[[group_col, weight]].dropna().copy()
    d[weight] = _num(d[weight])
    d = d.dropna(subset=[weight])
    tot = d[weight].sum()
    if d.empty or tot == 0:
        return pd.DataFrame(columns=[group_col, weight, "pct"])
    out = d.groupby(group_col, observed=True)[weight].sum().reset_index()
    out["pct"] = out[weight] / tot * 100
    return out.sort_values("pct", ascending=False).reset_index(drop=True)


def group_wmean(d: pd.DataFrame, by: str, col: str, weight: str) -> pd.DataFrame:
    """Weighted mean of `col` per group + unweighted n (records with a value)."""
    t = d[[by, col, weight]].copy()
    t[col], t[weight] = _num(t[col]), _num(t[weight])
    t = t.dropna()
    if t.empty:
        return pd.DataFrame(columns=[by, "mean", "n", "w"])
    t["_xw"] = t[col] * t[weight]
    g = t.groupby(by, observed=True).agg(_xw=("_xw", "sum"), w=(weight, "sum"), n=(col, "size")).reset_index()
    g["mean"] = g["_xw"] / g["w"]
    return g[[by, "mean", "n", "w"]]


def age_band(s, bins=AGE_BINS, labels=AGE_LABELS):
    """Right-closed bins starting at -1 so age 0 (infants) is included in the first band."""
    return pd.cut(_num(s), bins=bins, labels=labels, right=True)


def rate_by(num: pd.DataFrame, den: pd.DataFrame, num_key, den_key, wn: str, wd: str) -> pd.DataFrame:
    """Weighted rate per 100 = sum(weights of numerator records)/sum(weights of denominator persons).

    `num_key` / `den_key` are column names or Series (e.g. an age band) of the two frames."""
    kn = num[num_key] if isinstance(num_key, str) else num_key
    kd = den[den_key] if isinstance(den_key, str) else den_key
    n = _num(num[wn]).groupby(kn, observed=True).sum()
    dsum = _num(den[wd]).groupby(kd, observed=True).sum()
    dn = den.groupby(kd, observed=True).size()
    for s in (n, dsum, dn):                       # plain labels -> safe alignment
        s.index = s.index.astype(object)
    t = pd.concat([n.rename("num"), dsum.rename("den"), dn.rename("n_den")], axis=1)
    t = t[t["den"].notna() & (t["den"] > 0)].fillna({"num": 0})
    t["rate"] = t["num"] / t["den"] * 100
    t.index.name = "group"
    return t.reset_index()


# ---------------------------------------------------------------------
# FORMATTING / CHART HELPERS
# ---------------------------------------------------------------------
def wrap_labels(series, width=18):
    return series.astype(str).apply(
        lambda s: "<br>".join(textwrap.wrap(s, width, max_lines=2, placeholder="…")))


def group_top_n_other(pct_df: pd.DataFrame, label_col: str, n: int = 6, value_col: str = "pct") -> pd.DataFrame:
    if pct_df.empty or len(pct_df) <= n:
        return pct_df
    d = pct_df.sort_values(value_col, ascending=False).reset_index(drop=True)
    top = d.iloc[:n].copy()
    other_val = d.iloc[n:][value_col].sum()
    other_row = {c: ("Other" if c == label_col else other_val if c == value_col else None) for c in d.columns}
    return pd.concat([top.astype({label_col: object}), pd.DataFrame([other_row])], ignore_index=True)


def show(fig):
    st.plotly_chart(fig, width="stretch")


def style_pie(fig, height=430, hide_below=1.0):
    fig.update_traces(textposition="inside", textinfo="label+percent",
                      insidetextfont=dict(size=11, color="#FFFFFF"),
                      hovertemplate="%{label}: %{percent}")
    for tr in fig.data:
        if tr.values is not None:
            total = sum(v for v in tr.values if v is not None) or 1
            tr.text = [f"{lbl}<br>{v/total*100:.1f}%" if (v / total * 100) >= hide_below else ""
                       for lbl, v in zip(tr.labels, tr.values)]
            tr.texttemplate = "%{text}"
    fig.update_layout(height=height,
                      legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="center", x=0.5,
                                  font=dict(size=12), itemwidth=40),
                      margin=dict(t=40, b=60, l=10, r=10))
    return fig


def style_bar(fig, height=None, horizontal=False, n_categories=None, unit="%", decimals=1):
    if height is None:
        n = n_categories or 6
        height = max(400, 70 * n) if horizontal else max(420, 60 * n)

    def fmt_val(v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return ""
        if v != v or round(v, decimals) == 0:
            return ""
        if unit == "%":
            return f"{v:.{decimals}f}%"
        if unit == "":
            return f"{v:,.{decimals}f}"
        return f"{unit} {v:,.{decimals}f}"

    if horizontal:
        for tr in fig.data:
            if tr.x is not None:
                tr.text = [fmt_val(v) for v in tr.x]
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_layout(margin=dict(t=40, b=40, l=10, r=90))
        fig.update_yaxes(automargin=True)
        try:
            max_x = max((max(tr.x) for tr in fig.data if tr.x is not None and len(tr.x)), default=None)
            if max_x is not None and max_x > 0:
                fig.update_xaxes(range=[0, max_x * 1.22])
        except Exception:
            pass
    else:
        for tr in fig.data:
            if tr.y is not None:
                tr.text = [fmt_val(v) for v in tr.y]
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_layout(margin=dict(t=40, b=120, l=60, r=20))
        fig.update_xaxes(tickangle=-25, automargin=True)
        try:
            max_y = max((max(tr.y) for tr in fig.data if tr.y is not None and len(tr.y)), default=None)
            if max_y is not None and max_y > 0:
                fig.update_yaxes(range=[0, max_y * 1.18])
        except Exception:
            pass
    fig.update_layout(height=height)
    return fig


def bar_with_table_toggle(container, d: pd.DataFrame, label_col: str, value_col: str, title: str,
                          top_n: int = 8, key: str = "", label_width: int = 34,
                          unit: str = "%", decimals: int = 1):
    d_sorted = d.sort_values(value_col, ascending=False).reset_index(drop=True)
    show_table = False
    if len(d_sorted) > top_n:
        if hasattr(container, "segmented_control"):
            choice = container.segmented_control("View", options=["📊 Graph", "📋 Table"], default="📊 Graph",
                                                 key=f"toggle_{key}", label_visibility="collapsed")
        else:
            choice = container.radio("View", options=["📊 Graph", "📋 Table"], index=0, horizontal=True,
                                     key=f"toggle_{key}", label_visibility="collapsed")
        show_table = (choice == "📋 Table")
        if show_table:
            container.caption(f"Showing all {len(d_sorted)} categories")

    col_label = "%" if unit == "%" else (f"{unit} " if unit else "Value")
    if show_table:
        table = d_sorted[[label_col, value_col]].rename(columns={label_col: "Category", value_col: col_label})
        container.dataframe(table, width="stretch", hide_index=True, height=360)
    else:
        d_top = d_sorted.head(top_n).copy()
        d_top["_label"] = wrap_labels(d_top[label_col], label_width)
        fig = px.bar(d_top, x=value_col, y="_label", orientation="h", title=title,
                     color="_label", color_discrete_sequence=PALETTE)
        fig.update_layout(yaxis_title="", xaxis_title=col_label, showlegend=False,
                          yaxis={"categoryorder": "total ascending"})
        container.plotly_chart(style_bar(fig, horizontal=True, n_categories=len(d_top), unit=unit,
                                         decimals=decimals), width="stretch")


def note(text: str):
    st.caption(f"ℹ️ {text}")


def no_data(label):
    st.caption(f"⚠️ *{label} — not available in this file.*")


# ---------------------------------------------------------------------
# PAGE CHROME (unchanged look)
# ---------------------------------------------------------------------
def inject_kpi_style():
    st.markdown(
        """
        <style>
        div[data-testid="stHorizontalBlock"] { gap: 16px; }
        div[data-testid="stMetric"] {
            background: linear-gradient(135deg, #F0FDFA 0%, #FFFFFF 100%);
            border: 1px solid #D1FAE5; border-left: 5px solid #0F766E; border-radius: 12px;
            padding: 14px 16px 12px 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
            min-height: 116px; display: flex; flex-direction: column; justify-content: center;
        }
        div[data-testid="stMetric"] * {
            white-space: normal !important; overflow: visible !important; text-overflow: clip !important;
            -webkit-line-clamp: unset !important; -webkit-box-orient: unset !important;
            max-width: none !important; max-height: none !important; height: auto !important;
        }
        div[data-testid="stMetricLabel"] {
            font-size: 12.5px; font-weight: 600; letter-spacing: 0.02em; text-transform: uppercase;
            color: #0F766E; line-height: 1.35; word-break: break-word; overflow-wrap: break-word;
        }
        div[data-testid="stMetricLabel"] p, div[data-testid="stMetricLabel"] span,
        div[data-testid="stMetricLabel"] div, div[data-testid="stMetricLabel"] label {
            word-break: break-word !important; overflow-wrap: break-word !important; white-space: normal !important;
        }
        div[data-testid="stMetricValue"] { font-size: 24px; font-weight: 800; color: #111827; }
        </style>
        """, unsafe_allow_html=True)


def inject_sidebar_style():
    st.markdown(
        f"""
        <style>
        section[data-testid="stSidebar"] {{ background-color: {NAVY}; }}
        section[data-testid="stSidebar"] * {{ color: #E5E7EB !important; }}
        section[data-testid="stSidebarNav"] a {{ border-radius: 8px; margin: 2px 8px; padding: 6px 10px !important; }}
        section[data-testid="stSidebarNav"] a:hover {{ background-color: {NAVY_LIGHT}; }}
        section[data-testid="stSidebarNav"] a[aria-current="page"] {{ background-color: {ACCENT}22; border-left: 3px solid {ACCENT}; }}
        section[data-testid="stSidebar"] hr {{ border-top: 1px solid #ffffff22; }}
        section[data-testid="stSidebar"] div[data-baseweb="select"] > div {{ background-color: {NAVY_LIGHT}; color: #E5E7EB; }}
        </style>
        """, unsafe_allow_html=True)


def branding():
    inject_kpi_style()
    inject_sidebar_style()
    st.sidebar.markdown(
        f"""
        <div style="padding: 8px 0 4px 0;">
            <span style="font-size: 26px;">🏥</span>
            <span style="font-size: 18px; font-weight: 700; color: #FFFFFF;">&nbsp;National Health Pulse India</span>
        </div>
        <div style="font-size: 12px; color: #9CA3AF; margin-bottom: 10px;">
            Household Social Consumption: Health Survey — NSS 80th Round
        </div>
        <hr style="margin: 4px 0 14px 0;">
        """, unsafe_allow_html=True)


def page_header(icon: str, title: str, subtitle: str = "", crumb: str = "", badge_label: str = "", badge_value: str = ""):
    crumb_html = f'<span style="color:#9CA3AF; font-size:12.5px;">🏠 &nbsp;{crumb}</span>' if crumb else ""
    badge_html = ""
    if badge_label and badge_value:
        badge_html = f"""
        <div style="background:{NAVY_LIGHT}; border:1px solid #ffffff22; border-radius:12px;
                    padding:10px 18px; text-align:center; min-width:110px;">
            <div style="font-size:22px; font-weight:800; color:#FFFFFF;">{badge_value}</div>
            <div style="font-size:10.5px; color:#9CA3AF; text-transform:uppercase; letter-spacing:0.04em;">{badge_label}</div>
        </div>
        """
    sub_html = f'<div style="font-size:14px; color:#CBD5E1; margin-top:4px;">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div style="background:linear-gradient(135deg, {NAVY} 0%, {NAVY_LIGHT} 100%);
                    border-radius:16px; padding:20px 26px; margin-bottom:22px;
                    border-left:5px solid {ACCENT};
                    display:flex; justify-content:space-between; align-items:center;">
            <div>
                {crumb_html}
                <div style="font-size:30px; font-weight:800; color:#FFFFFF; margin-top:4px;">{icon} &nbsp;{title}</div>
                {sub_html}
            </div>
            {badge_html}
        </div>
        """, unsafe_allow_html=True)


# ---------------------------------------------------------------------
# INSIGHT CALLOUT  (neutral wording - a higher rate/cost is not automatically "worse")
# ---------------------------------------------------------------------
def rank_callout(tbl: pd.DataFrame, label_col: str, value_col: str, n_col: str, metric: str,
                 national: float, fmt: str = "{:,.0f}", unit: str = "", suffix: str = "",
                 min_n: int = MIN_N, caution: str = ""):
    """Key-takeaway box: national value + highest / lowest group with a minimum sample size.
    Wording is deliberately neutral - a higher rate or cost is not automatically 'worse'."""
    if national is None or national != national:
        return
    f = lambda v: f"{unit}{fmt.format(v)}{suffix}"
    msg = f"📌 **Key takeaway:** {metric} is **{f(national)}** nationally."
    t = tbl[(tbl[n_col] >= min_n) & tbl[value_col].notna()]
    if len(t) >= 2:
        hi, lo = t.loc[t[value_col].idxmax()], t.loc[t[value_col].idxmin()]
        msg += (f" Among states with ≥{min_n} sample records, **{hi[label_col]}** is highest (**{f(hi[value_col])}**) "
                f"and **{lo[label_col]}** lowest (**{f(lo[value_col])}**).")
    if caution:
        msg += f" _{caution}_"
    st.info(msg)


# ---------------------------------------------------------------------
# MAP / ADVANCED CHARTS
# ---------------------------------------------------------------------
# survey state name -> normalised GeoJSON name
_GEOJSON_NAME_FIX = {
    "jammu & kashmir": "jammu and kashmir",
    "andaman & n. island": "andaman and nicobar islands",
    "d & n. haveli & daman & diu": "dadra and nagar haveli and daman and diu",
}


@st.cache_resource
def _load_india_geojson():
    path = DATA_DIR / "india_states.geojson"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        gj = json.load(f)
    for feat in gj["features"]:
        feat["properties"]["match_key"] = re.sub(r"[^a-z]", "", feat["properties"]["NAME_1"].lower())
    return gj


def _geo_key(s: str) -> str:
    s = str(s).strip().lower()
    return re.sub(r"[^a-z]", "", _GEOJSON_NAME_FIX.get(s, s))


def choropleth_state_map(d: pd.DataFrame, state_col: str, value_col: str, title: str,
                         unit: str = "%", height: int = 480):
    """India state choropleth. Returns True if drawn; states missing from the map are listed underneath."""
    gj = _load_india_geojson()
    if gj is None or d.empty or state_col not in d.columns:
        return False
    d = d.copy()
    d["match_key"] = d[state_col].astype(str).map(_geo_key)
    fig = px.choropleth(d, geojson=gj, locations="match_key", featureidkey="properties.match_key",
                        color=value_col, color_continuous_scale="Teal",
                        hover_name=state_col, labels={value_col: unit})
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(title=title, height=height, margin=dict(t=40, b=10, l=0, r=0))
    show(fig)
    geo_keys = {f["properties"]["match_key"] for f in gj["features"]}
    missing = sorted(set(d.loc[~d["match_key"].isin(geo_keys), state_col].astype(str)))
    if missing:
        st.caption("Not drawn on the map (no matching outline): " + ", ".join(missing))
    return True


def nested_sunburst(d: pd.DataFrame, path_cols: list, weight_col: str, title: str,
                    height: int = 480, kind: str = "sunburst"):
    cols = [c for c in path_cols if c in d.columns]
    if len(cols) < 2 or weight_col not in d.columns:
        return False
    g = d[cols + [weight_col]].dropna().copy()
    g[weight_col] = _num(g[weight_col])
    g = g.dropna(subset=[weight_col])
    if g.empty:
        return False
    for c in cols:
        g[c] = g[c].astype(str)
    grouped = g.groupby(cols, observed=True)[weight_col].sum().reset_index()
    plot_fn = px.treemap if kind == "treemap" else px.sunburst
    fig = plot_fn(grouped, path=cols, values=weight_col, title=title,
                  color=cols[0], color_discrete_sequence=PALETTE)
    fig.update_layout(height=height, margin=dict(t=40, b=10, l=10, r=10))
    show(fig)
    return True


def correlation_heatmap(d: pd.DataFrame, cols: list, labels: dict, title: str, height: int = 460):
    use_cols = [c for c in cols if c in d.columns]
    if len(use_cols) < 2:
        return False
    num = d[use_cols].apply(pd.to_numeric, errors="coerce").dropna(how="all")
    if num.shape[0] < 5:
        return False
    corr = num.corr().round(2)
    disp = [labels.get(c, c) for c in use_cols]
    fig = go.Figure(data=go.Heatmap(z=corr.values, x=disp, y=disp, colorscale="Tealrose", zmid=0,
                                    text=corr.values, texttemplate="%{text}",
                                    hovertemplate="%{y} vs %{x}: %{z}<extra></extra>"))
    fig.update_layout(title=title, height=height, margin=dict(t=40, b=10, l=10, r=10))
    show(fig)
    return True


def dual_axis_combo(d: pd.DataFrame, cat_col: str, weight_col: str, value_col: str, title: str,
                    bar_name: str, line_name: str, top_n: int = 10, height: int = 620):
    """Bars = weighted volume, line = weighted mean of value_col, per category (top_n by volume)."""
    if cat_col not in d.columns or weight_col not in d.columns or value_col not in d.columns:
        return False
    g = group_wmean(d, cat_col, value_col, weight_col)
    if g.empty:
        return False
    vol = d.groupby(cat_col, observed=True)[weight_col].sum()
    g["count_w"] = g[cat_col].map(vol)
    g = g.sort_values("count_w", ascending=False).head(top_n)
    g["_full"] = g[cat_col].astype(str)
    g["_label"] = g["_full"].apply(lambda s: s if len(s) <= 28 else s[:25] + "...")
    fig = go.Figure()
    fig.add_bar(x=g["_label"], y=g["count_w"], name=bar_name, marker_color=PALETTE[0], yaxis="y1",
                customdata=g["_full"], hovertemplate="%{customdata}<br>" + bar_name + ": %{y:,.0f}<extra></extra>")
    fig.add_trace(go.Scatter(x=g["_label"], y=g["mean"], name=line_name, mode="lines+markers",
                             marker_color=ACCENT, yaxis="y2", customdata=g["_full"],
                             hovertemplate="%{customdata}<br>" + line_name + ": %{y:,.0f}<extra></extra>"))
    fig.update_layout(title=title, height=height, yaxis=dict(title=bar_name),
                      yaxis2=dict(title=line_name, overlaying="y", side="right"),
                      xaxis=dict(tickangle=-35, automargin=True, tickfont=dict(size=11)),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
                      margin=dict(t=70, b=160, l=60, r=60))
    show(fig)
    return True


# ---------------------------------------------------------------------
# SIDEBAR FILTERS
# ---------------------------------------------------------------------
def sidebar_filters(df: pd.DataFrame, kind: str = "master") -> dict:
    """Sector / Gender / Age group / State filters (only those the dataset has)."""
    fm = FIELDS[kind]
    st.sidebar.header("🔍 Filters")
    sector = gender = age = "All"
    state = []
    if fm["sector"] and fm["sector"] in df.columns:
        vals = sorted(df[fm["sector"]].dropna().astype(str).unique().tolist())
        sector = st.sidebar.selectbox("Sector", ["All"] + vals, key=f"sector_{kind}")
    if fm["gender"] and fm["gender"] in df.columns:
        vals = sorted(df[fm["gender"]].dropna().astype(str).unique().tolist())
        gender = st.sidebar.selectbox("Gender", ["All"] + vals, key=f"gender_{kind}")
    if fm["age"] and fm["age"] in df.columns:
        age = st.sidebar.selectbox("Age group (years)", ["All"] + AGE_LABELS, key=f"age_{kind}")
    if fm["state"] and fm["state"] in df.columns:
        states = sorted(df[fm["state"]].dropna().astype(str).unique().tolist())
        state = st.sidebar.multiselect("State", states, default=[], key=f"state_{kind}",
                                       help="Leave empty to include every state")
    return {"sector": sector, "gender": gender, "age": age, "state": state}


def apply_filters(df: pd.DataFrame, f: dict, kind: str, skip=()) -> pd.DataFrame:
    """Apply the sidebar selections to any dataset of the given kind (`skip` = e.g. ('gender','age'))."""
    if df.empty:
        return df
    fm = FIELDS[kind]
    mask = pd.Series(True, index=df.index)
    if "sector" not in skip and f.get("sector", "All") != "All" and fm["sector"] in df.columns:
        mask &= df[fm["sector"]].astype(str) == f["sector"]
    if "gender" not in skip and f.get("gender", "All") != "All" and fm["gender"] and fm["gender"] in df.columns:
        mask &= df[fm["gender"]].astype(str).str.lower() == f["gender"].lower()
    if "state" not in skip and f.get("state") and fm["state"] in df.columns:
        mask &= df[fm["state"]].astype(str).isin(f["state"])
    if "age" not in skip and f.get("age", "All") != "All" and fm["age"] and fm["age"] in df.columns:
        lo, hi = AGE_RANGES[f["age"]]
        mask &= _num(df[fm["age"]]).between(lo, hi)
    return df[mask]
