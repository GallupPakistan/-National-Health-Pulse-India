import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import textwrap
import json
import re

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
# DATA LOCATION
# Put the raw survey files in a "data" folder next to this file:
#   data/nss_health_master_FULL.csv
#   data/household.csv
#   data/person.csv
#   data/hospitalization_cases_full.csv
#   data/ailment_spells_full.csv
#   data/vaccination_full.csv
#   data/antenatal_full.csv
#   data/deaths_full.csv
# No merge / decode / to_parquet step is needed — these files are
# already fully decoded (human-readable text values).
# ---------------------------------------------------------------------
DATA_DIR = Path(__file__).parent / "data"


@st.cache_data
def load(name: str) -> pd.DataFrame:
    """Load a raw survey CSV straight from the data/ folder."""
    path = DATA_DIR / name
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, low_memory=False)
    # Some files carry a stray "99" (not-stated / invalid) code in the
    # state column instead of a real state name. It breaks charts (turns
    # a categorical axis numeric) and skews state-wise stats, so drop it.
    for state_col in ("state", "State", "st"):
        if state_col in df.columns:
            df = df[df[state_col].astype(str).str.strip() != "99"]
    return df


def has(df, *cols):
    return len(df) > 0 and all(c in df.columns for c in cols)


def weighted_mean(df: pd.DataFrame, col: str, weight: str) -> float:
    d = df[[col, weight]].dropna()
    d = d[pd.to_numeric(d[col], errors="coerce").notna()]
    if d.empty:
        return float("nan")
    d[col] = pd.to_numeric(d[col], errors="coerce")
    w = pd.to_numeric(d[weight], errors="coerce")
    if w.sum() == 0:
        return float("nan")
    return (d[col] * w).sum() / w.sum()


def weighted_pct(df: pd.DataFrame, group_col: str, weight: str) -> pd.DataFrame:
    d = df[[group_col, weight]].dropna()
    if d.empty:
        return pd.DataFrame(columns=[group_col, weight, "pct"])
    d = d.copy()
    d[weight] = pd.to_numeric(d[weight], errors="coerce")
    d = d.dropna(subset=[weight])
    tot = d[weight].sum()
    if tot == 0:
        return pd.DataFrame(columns=[group_col, weight, "pct"])
    out = d.groupby(group_col)[weight].sum().reset_index()
    out["pct"] = (out[weight] / tot * 100).round(2)
    return out.sort_values("pct", ascending=False)


def weighted_rate_per_1000(numerator_df: pd.DataFrame, denominator_df: pd.DataFrame,
                            weight: str) -> float:
    num = pd.to_numeric(numerator_df[weight], errors="coerce").sum() if weight in numerator_df else 0
    den = pd.to_numeric(denominator_df[weight], errors="coerce").sum() if weight in denominator_df else 0
    return (num / den * 1000) if den else float("nan")


def group_top_n_other(pct_df: pd.DataFrame, label_col: str, n: int = 6,
                       value_col: str = "pct") -> pd.DataFrame:
    """Collapse a weighted_pct() result down to the top `n` categories plus
    a single "Other" slice for everything else. Without this, a pie chart
    built straight from a high-cardinality text column (Religion, Social
    group, Place of delivery, ...) renders a wall of unreadable slivers."""
    if pct_df.empty or len(pct_df) <= n:
        return pct_df
    d = pct_df.sort_values(value_col, ascending=False).reset_index(drop=True)
    top = d.iloc[:n].copy()
    other_val = d.iloc[n:][value_col].sum()
    other_row = {c: ("Other" if c == label_col else other_val if c == value_col else None)
                 for c in d.columns}
    return pd.concat([top, pd.DataFrame([other_row])], ignore_index=True)


def wrap_labels(series, width=18):
    return series.astype(str).apply(
        lambda s: "<br>".join(textwrap.wrap(s, width, max_lines=2, placeholder="…")))


def style_pie(fig, height=430, hide_below=1.0):
    fig.update_traces(textposition="inside", textinfo="label+percent",
                       insidetextfont=dict(size=11, color="#FFFFFF"),
                       hovertemplate="%{label}: %{percent}")
    # hide the inside label on slivers under `hide_below`% — a "0%"/"0.4%"
    # label crammed into a tiny wedge is unreadable clutter, not information
    for tr in fig.data:
        if tr.values is not None:
            total = sum(v for v in tr.values if v is not None) or 1
            tr.text = [
                f"{lbl}<br>{v/total*100:.1f}%" if (v / total * 100) >= hide_below else ""
                for lbl, v in zip(tr.labels, tr.values)
            ]
            tr.texttemplate = "%{text}"
    fig.update_layout(
        height=height,
        legend=dict(orientation="h", yanchor="top", y=-0.12,
                    xanchor="center", x=0.5, font=dict(size=12),
                    itemwidth=40),
        margin=dict(t=40, b=60, l=10, r=10),
    )
    return fig


def style_bar(fig, height=None, horizontal=False, n_categories=None, unit="%", decimals=1):
    if height is None:
        n = n_categories or 6
        height = max(400, 70 * n) if horizontal else max(420, 60 * n)

    def fmt_val(v):
        if v is None:
            return ""
        try:
            v = float(v)
        except (TypeError, ValueError):
            return ""
        if round(v, decimals) == 0:
            return ""  # skip meaningless "0.0%" / "0" labels
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
        fig.update_layout(margin=dict(t=40, b=160, l=60, r=20))
        fig.update_xaxes(tickangle=-25, automargin=True)
        try:
            max_y = max((max(tr.y) for tr in fig.data if tr.y is not None and len(tr.y)), default=None)
            if max_y is not None and max_y > 0:
                fig.update_yaxes(range=[0, max_y * 1.18])
        except Exception:
            pass

    fig.update_layout(height=height, showlegend=False)
    return fig


def bar_with_table_toggle(container, d: pd.DataFrame, label_col: str, value_col: str,
                           title: str, top_n: int = 8, key: str = "", label_width: int = 34,
                           unit: str = "%", decimals: int = 1):
    d_sorted = d.sort_values(value_col, ascending=False).reset_index(drop=True)
    show_table = False
    if len(d_sorted) > top_n:
        if hasattr(container, "segmented_control"):
            choice = container.segmented_control(
                "View", options=["📊 Graph", "📋 Table"], default="📊 Graph",
                key=f"toggle_{key}", label_visibility="collapsed",
            )
        else:
            choice = container.radio(
                "View", options=["📊 Graph", "📋 Table"], index=0,
                horizontal=True, key=f"toggle_{key}", label_visibility="collapsed",
            )
        show_table = (choice == "📋 Table")
        if show_table:
            container.caption(f"Showing all {len(d_sorted)} categories")

    col_label = "%" if unit == "%" else (f"{unit} " if unit else "Value")
    if show_table:
        table = d_sorted[[label_col, value_col]].rename(columns={label_col: "Category", value_col: col_label})
        container.dataframe(table, use_container_width=True, hide_index=True, height=360)
    else:
        d_top = d_sorted.head(top_n).copy()
        d_top["_label"] = wrap_labels(d_top[label_col], label_width)
        fig = px.bar(d_top, x=value_col, y="_label", orientation="h", title=title,
                     color="_label", color_discrete_sequence=PALETTE)
        fig.update_layout(yaxis_title="", xaxis_title=col_label, showlegend=False,
                           yaxis={"categoryorder": "total ascending"})
        container.plotly_chart(style_bar(fig, horizontal=True, n_categories=len(d_top),
                                          unit=unit, decimals=decimals),
                                use_container_width=True)


def inject_kpi_style():
    st.markdown(
        """
        <style>
        div[data-testid="stHorizontalBlock"] { gap: 16px; }
        div[data-testid="stMetric"] {
            background: linear-gradient(135deg, #F0FDFA 0%, #FFFFFF 100%);
            border: 1px solid #D1FAE5;
            border-left: 5px solid #0F766E;
            border-radius: 12px;
            padding: 14px 16px 12px 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
            min-height: 108px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        div[data-testid="stMetric"] * {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
            -webkit-line-clamp: unset !important;
            -webkit-box-orient: unset !important;
            max-width: none !important;
            max-height: none !important;
            height: auto !important;
        }
        div[data-testid="stMetricLabel"] {
            font-size: 12.5px; font-weight: 600; letter-spacing: 0.02em;
            text-transform: uppercase; color: #0F766E;
            line-height: 1.35;
            word-break: break-word;
            overflow-wrap: break-word;
        }
        div[data-testid="stMetricLabel"] p,
        div[data-testid="stMetricLabel"] span,
        div[data-testid="stMetricLabel"] div,
        div[data-testid="stMetricLabel"] label {
            word-break: break-word !important;
            overflow-wrap: break-word !important;
            white-space: normal !important;
        }
        div[data-testid="stMetric"] { min-height: 116px; }
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


def page_header(icon: str, title: str, subtitle: str = "",
                 crumb: str = "", badge_label: str = "", badge_value: str = ""):
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
    st.markdown(
        f"""
        <div style="background:linear-gradient(135deg, {NAVY} 0%, {NAVY_LIGHT} 100%);
                    border-radius:16px; padding:20px 26px; margin-bottom:22px;
                    border-left:5px solid {ACCENT};
                    display:flex; justify-content:space-between; align-items:center;">
            <div>
                {crumb_html}
                <div style="font-size:30px; font-weight:800; color:#FFFFFF; margin-top:4px;">{icon} &nbsp;{title}</div>
                {f'<div style="font-size:14px; color:#CBD5E1; margin-top:4px;">{subtitle}</div>' if subtitle else ''}
            </div>
            {badge_html}
        </div>
        """, unsafe_allow_html=True)


def no_data(label):
    st.caption(f"⚠️ *{label} — not available in this file.*")


# ---------------------------------------------------------------------
# ADVANCED CHARTS — Choropleth / Sunburst-Treemap / Correlation / Combo
# These are new chart TYPES (not used anywhere else in the app) and each
# one is built on a metric/joint-view that isn't already shown by the
# existing bar/pie charts on that page.
# ---------------------------------------------------------------------
STATE_CODE_MAP = {
    1: "Jammu & Kashmir", 2: "Himachal Pradesh", 3: "Punjab", 4: "Chandigarh",
    5: "Uttarakhand", 6: "Haryana", 7: "Delhi", 8: "Rajasthan", 9: "Uttar Pradesh",
    10: "Bihar", 11: "Sikkim", 12: "Arunachal Pradesh", 13: "Nagaland", 14: "Manipur",
    15: "Mizoram", 16: "Tripura", 17: "Meghalaya", 18: "Assam", 19: "West Bengal",
    20: "Jharkhand", 21: "Odisha", 22: "Chhattisgarh", 23: "Madhya Pradesh",
    24: "Gujarat", 25: "D & N. Haveli & Daman & Diu", 27: "Maharashtra",
    28: "Andhra Pradesh", 29: "Karnataka", 30: "Goa", 31: "Lakshadweep",
    32: "Kerala", 33: "Tamil Nadu", 34: "Puducherry", 35: "Andaman & N. Island",
    36: "Telangana", 37: "Ladakh",
}

# survey state name -> geojson NAME_1 property (bundled India_states.geojson)
_GEOJSON_NAME_FIX = {
    "jammu & kashmir": "Jammu and Kashmir", "uttarakhand": "Uttaranchal",
    "odisha": "Orissa", "d & n. haveli & daman & diu": "Dadra and Nagar Haveli",
    "andaman & n. island": "Andaman and Nicobar",
}


def decode_state_code(df: pd.DataFrame, code_col: str = "st") -> pd.Series:
    """Turn a state column into readable state names.

    Handles both shapes seen across the survey files: a raw numeric state
    code (mapped through STATE_CODE_MAP) and an already-decoded text state
    name (e.g. hospitalization/ailment/person/vaccination files carry
    "Ladakh", "Tamil Nadu", ... directly in this column — passing those
    through pd.to_numeric() alone turned ~99% of rows to NaN and silently
    emptied every best/worst-state callout built on top of it).
    """
    raw = df[code_col]
    codes = pd.to_numeric(raw, errors="coerce")
    if codes.notna().mean() > 0.5:
        # mostly numeric -> treat as state codes
        return codes.map(STATE_CODE_MAP)
    # mostly text already -> just clean it up
    text = raw.astype(str).str.strip()
    return text.replace({"nan": None, "": None, "99": None})


def state_rank_avg(d: pd.DataFrame, state_code_col: str, value_col: str, weight_col: str):
    """Weighted national average of value_col, plus the best (lowest) and
    worst (highest) state. Returns (national_avg, best_state, best_val,
    worst_state, worst_val) — any of which may be None if data is missing."""
    if state_code_col not in d.columns or value_col not in d.columns or weight_col not in d.columns:
        return None, None, None, None, None
    s = d[[state_code_col, value_col, weight_col]].dropna().copy()
    s[weight_col] = pd.to_numeric(s[weight_col], errors="coerce")
    s[value_col] = pd.to_numeric(s[value_col], errors="coerce")
    s = s.dropna()
    if s.empty:
        return None, None, None, None, None
    national_avg = (s[value_col] * s[weight_col]).sum() / s[weight_col].sum()
    s["state"] = decode_state_code(s, state_code_col)
    s = s.dropna(subset=["state"])
    if s.empty:
        return national_avg, None, None, None, None
    s["_wsum"] = s[value_col] * s[weight_col]
    grp = s.groupby("state").agg(_wsum=("_wsum", "sum"), _wtot=(weight_col, "sum"))
    grp["avg"] = grp["_wsum"] / grp["_wtot"]
    grp = grp.replace([float("inf"), float("-inf")], pd.NA).dropna(subset=["avg"])
    if len(grp) < 2:
        return national_avg, None, None, None, None
    best_state, best_val = grp["avg"].idxmin(), grp["avg"].min()
    worst_state, worst_val = grp["avg"].idxmax(), grp["avg"].max()
    return national_avg, best_state, best_val, worst_state, worst_val


def render_insight_callout(national_val, best_state, best_val, worst_state, worst_val,
                            metric_label: str, fmt: str = "{:,.0f}", unit: str = "",
                            higher_is_worse: bool = True, show_badges: bool = True):
    """Renders a 'key takeaway' info box plus optional best/worst state badges."""
    if national_val is None:
        return
    takeaway = f"📌 **Key takeaway:** {metric_label} is **{unit}{fmt.format(national_val)}** on average, nationally."
    if best_state and worst_state:
        hi_state, hi_val = (worst_state, worst_val) if higher_is_worse else (best_state, best_val)
        lo_state, lo_val = (best_state, best_val) if higher_is_worse else (worst_state, worst_val)
        takeaway += (f" **{hi_state}** is highest (**{unit}{fmt.format(hi_val)}**), while "
                     f"**{lo_state}** is lowest (**{unit}{fmt.format(lo_val)}**).")
    st.info(takeaway)
    if show_badges and best_state and worst_state:
        b1, b2 = st.columns(2)
        good_state, good_val = (best_state, best_val) if higher_is_worse else (worst_state, worst_val)
        bad_state, bad_val = (worst_state, worst_val) if higher_is_worse else (best_state, best_val)
        b1.success(f"🏆 **Best (lowest):** {good_state} — {unit}{fmt.format(good_val)}")
        b2.error(f"⚠️ **Worst (highest):** {bad_state} — {unit}{fmt.format(bad_val)}")


@st.cache_data
def _load_india_geojson():
    path = DATA_DIR / "india_states.geojson"
    if not path.exists():
        return None
    with open(path) as f:
        gj = json.load(f)
    for feat in gj["features"]:
        feat["properties"]["match_key"] = re.sub(r"[^a-z]", "", feat["properties"]["NAME_1"].lower())
    return gj


def choropleth_state_map(d: pd.DataFrame, state_col: str, value_col: str, title: str,
                          unit: str = "%", height: int = 480):
    """India map choropleth for a state-wise metric. Returns True if drawn."""
    gj = _load_india_geojson()
    if gj is None or d.empty or state_col not in d.columns:
        return False
    d = d.copy()
    d["match_key"] = d[state_col].astype(str).apply(
        lambda s: re.sub(r"[^a-z]", "", _GEOJSON_NAME_FIX.get(s.strip().lower(), s).lower()))
    fig = px.choropleth(
        d, geojson=gj, locations="match_key", featureidkey="properties.match_key",
        color=value_col, color_continuous_scale="Teal",
        hover_name=state_col, labels={value_col: unit},
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(title=title, height=height, margin=dict(t=40, b=10, l=0, r=0))
    st.plotly_chart(fig, use_container_width=True)
    unmatched = set(d[state_col]) - {STATE_CODE_MAP.get(k) for k in STATE_CODE_MAP}
    return True


def nested_sunburst(d: pd.DataFrame, path_cols: list, weight_col: str, title: str,
                     height: int = 480, kind: str = "sunburst"):
    """Sunburst/treemap of a weighted joint distribution across 2-3 categorical
    columns — shows how categories combine, which a flat pie/bar can't."""
    cols = [c for c in path_cols if c in d.columns]
    if len(cols) < 2 or weight_col not in d.columns:
        return False
    g = d[cols + [weight_col]].dropna()
    g[weight_col] = pd.to_numeric(g[weight_col], errors="coerce")
    g = g.dropna(subset=[weight_col])
    if g.empty:
        return False
    grouped = g.groupby(cols)[weight_col].sum().reset_index()
    plot_fn = px.treemap if kind == "treemap" else px.sunburst
    fig = plot_fn(grouped, path=cols, values=weight_col, title=title,
                  color=cols[0], color_discrete_sequence=PALETTE)
    fig.update_layout(height=height, margin=dict(t=40, b=10, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)
    return True


def correlation_heatmap(d: pd.DataFrame, cols: list, labels: dict, title: str, height: int = 460):
    """Correlation matrix across numeric fields — reveals relationships
    (e.g. does household size move with expenditure?) that single-metric
    KPI cards and bar charts never surface."""
    use_cols = [c for c in cols if c in d.columns]
    if len(use_cols) < 2:
        return False
    num = d[use_cols].apply(pd.to_numeric, errors="coerce")
    num = num.dropna(how="all")
    if num.shape[0] < 5:
        return False
    corr = num.corr().round(2)
    disp_labels = [labels.get(c, c) for c in use_cols]
    fig = go.Figure(data=go.Heatmap(
        z=corr.values, x=disp_labels, y=disp_labels,
        colorscale="Tealrose", zmid=0, text=corr.values, texttemplate="%{text}",
        hovertemplate="%{y} vs %{x}: %{z}<extra></extra>",
    ))
    fig.update_layout(title=title, height=height, margin=dict(t=40, b=10, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)
    return True


def dual_axis_combo(d: pd.DataFrame, cat_col: str, weight_col: str, value_col: str,
                     title: str, bar_name: str, line_name: str, top_n: int = 10, height: int = 620):
    """Bar (weighted volume/count) + line (weighted average of a numeric
    field) on the same categorical axis, on two y-axes — links 'how many'
    with 'how much', which the separate bar and pie charts never combine."""
    if cat_col not in d.columns or weight_col not in d.columns or value_col not in d.columns:
        return False
    g = d[[cat_col, weight_col, value_col]].dropna()
    g[weight_col] = pd.to_numeric(g[weight_col], errors="coerce")
    g[value_col] = pd.to_numeric(g[value_col], errors="coerce")
    g = g.dropna()
    if g.empty:
        return False
    g["_wsum"] = g[value_col] * g[weight_col]
    agg = g.groupby(cat_col).agg(count_w=(weight_col, "sum"), _wsum=("_wsum", "sum")).reset_index()
    agg["avg_val"] = (agg["_wsum"] / agg["count_w"]).fillna(0)
    agg = agg.sort_values("count_w", ascending=False).head(top_n)

    # Long category text (e.g. full ailment descriptions) forces Plotly's
    # automargin to shrink the plot area down to a sliver. Truncate the
    # display labels but keep the full text available as hover text.
    agg["_label_full"] = agg[cat_col].astype(str)
    agg["_label"] = agg["_label_full"].apply(lambda s: s if len(s) <= 28 else s[:25] + "...")

    fig = go.Figure()
    fig.add_bar(x=agg["_label"], y=agg["count_w"], name=bar_name, marker_color=PALETTE[0], yaxis="y1",
                customdata=agg["_label_full"], hovertemplate="%{customdata}<br>" + bar_name + ": %{y}<extra></extra>")
    fig.add_trace(go.Scatter(x=agg["_label"], y=agg["avg_val"], name=line_name,
                              mode="lines+markers", marker_color=ACCENT, yaxis="y2",
                              customdata=agg["_label_full"],
                              hovertemplate="%{customdata}<br>" + line_name + ": %{y}<extra></extra>"))
    fig.update_layout(
        title=title, height=height,
        yaxis=dict(title=bar_name), yaxis2=dict(title=line_name, overlaying="y", side="right"),
        xaxis=dict(tickangle=-35, automargin=True, tickfont=dict(size=11)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        margin=dict(t=70, b=160, l=60, r=60),
    )
    st.plotly_chart(fig, use_container_width=True)
    return True


# ---------------------------------------------------------------------
# GLOBAL FILTERS
# Each source file uses slightly different column names for the same
# concept. FIELD_MAP tells the filter helpers which column to use for
# a given loaded table (keyed by a short "kind" tag each page passes).
# ---------------------------------------------------------------------
FIELD_MAPS = {
    # kind: (state_col, sector_col, gender_col, age_col, weight_col)
    "master": ("state", "sector", "Gender", "Age(in years)", "final_weight"),
    "detail": ("st", "sec", "b3c4", "b3c5", "wt"),   # generic detail tables merged w/ person cols
    "household": (None, "sec", None, None, "wt"),        # household.csv has no person/state text col directly
    "deaths": (None, "sec", None, "b4c4", "wt"),
}

STATE_LIST_CACHE = {}


def get_state_list(df: pd.DataFrame, state_col: str):
    if state_col and state_col in df.columns:
        return sorted(df[state_col].dropna().astype(str).unique().tolist())
    return []


def sidebar_filters(df: pd.DataFrame, kind: str = "master"):
    """Renders Sector / Gender / Age / State filters (only the ones that
    apply to this table) and returns a dict of selections."""
    state_col, sector_col, gender_col, age_col, weight_col = FIELD_MAPS.get(kind, FIELD_MAPS["master"])
    st.sidebar.header("🔍 Filters")

    sector = "All"
    if sector_col and sector_col in df.columns:
        vals = df[sector_col].dropna().astype(str).unique().tolist()
        opts = ["All"] + sorted(vals) if not set(vals) <= {"1", "2"} else ["All", "Rural", "Urban"]
        sector = st.sidebar.selectbox("Sector", opts, key=f"sector_{kind}")

    gender = "All"
    if gender_col and gender_col in df.columns:
        vals = sorted(df[gender_col].dropna().astype(str).unique().tolist())
        gender = st.sidebar.selectbox("Gender", ["All"] + vals, key=f"gender_{kind}")

    age_group = "All"
    if age_col and age_col in df.columns:
        age_group = st.sidebar.selectbox("Age group", ["All", "0-18", "19-40", "41-60", "60+"], key=f"age_{kind}")

    state = []
    if state_col and state_col in df.columns:
        states = sorted(df[state_col].dropna().astype(str).unique().tolist())
        state = st.sidebar.multiselect("State", states, default=[], key=f"state_{kind}",
                                        help="Leave empty to include every state")

    return {"sector": sector, "gender": gender, "age_group": age_group, "state": state,
            "_cols": (state_col, sector_col, gender_col, age_col, weight_col)}


def _age_mask(age: pd.Series, band: str) -> pd.Series:
    if band == "0-18":
        return age.between(0, 18)
    if band == "19-40":
        return age.between(19, 40)
    if band == "41-60":
        return age.between(41, 60)
    if band == "60+":
        return age >= 61
    return pd.Series(True, index=age.index)


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    if df.empty:
        return df
    state_col, sector_col, gender_col, age_col, weight_col = filters.get("_cols", (None, None, None, None, None))
    out = df

    if filters.get("sector", "All") != "All" and sector_col and sector_col in out.columns:
        vals = out[sector_col].dropna().astype(str).unique().tolist()
        if set(vals) <= {"1", "2"}:
            code = "1" if filters["sector"] == "Rural" else "2"
            out = out[out[sector_col].astype(str) == code]
        else:
            out = out[out[sector_col].astype(str) == filters["sector"]]

    if filters.get("gender", "All") != "All" and gender_col and gender_col in out.columns:
        out = out[out[gender_col].astype(str).str.lower() == filters["gender"].lower()]

    if filters.get("state") and state_col and state_col in out.columns:
        out = out[out[state_col].astype(str).isin(filters["state"])]

    age_group = filters.get("age_group", "All")
    if age_group != "All" and age_col and age_col in out.columns:
        age = pd.to_numeric(out[age_col], errors="coerce")
        out = out[_age_mask(age, age_group)]

    return out