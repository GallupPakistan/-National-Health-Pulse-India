import streamlit as st
import pandas as pd
import plotly.express as px
from utils import (branding, page_header, load, has, weighted_mean, weighted_pct,
                    sidebar_filters, apply_filters, style_bar, style_pie, no_data,
                    bar_with_table_toggle, COLOR_SECTOR, correlation_heatmap, group_top_n_other)

st.set_page_config(page_title="Household Profile — National Health Pulse India", layout="wide", page_icon="🏠")
branding()

df = load("household.csv")
if df.empty:
    st.error("`household.csv` not found in the `data/` folder.")
    st.stop()

filters = sidebar_filters(df, kind="household")
d = apply_filters(df, filters)
W = "wt"

page_header("🏠", "Household Profile", "Household type, insurance premium, consumption expenditure breakdown, outbreak flag, survey quality",
            crumb="Dashboard / Household Profile", badge_label="Households", badge_value=f"{len(d):,}")

from utils import state_rank_avg, render_insight_callout
_nat, _bs, _bv, _ws, _wv = state_rank_avg(d, "st", "umce", W)
render_insight_callout(_nat, _bs, _bv, _ws, _wv, "Avg monthly consumer expenditure",
                        fmt="{:,.0f}", unit="Rs. ", higher_is_worse=True)

k1, k2, k3, k4 = st.columns(4)
k1.metric("🏠 Households (weighted)", f"{pd.to_numeric(d[W], errors='coerce').sum():,.0f}" if has(d, W) else "N/A")
k2.metric("👥 Avg household size", f"{weighted_mean(d, 'hhsz', W):.1f}" if has(d, "hhsz", W) else "N/A")
k3.metric("💰 Avg monthly consumer expenditure", f"Rs. {weighted_mean(d, 'umce', W):,.0f}" if has(d, "umce", W) else "N/A")

if has(d, "b5i5"):
    ob = weighted_pct(d, "b5i5", W)
    ob_yes = ob[ob["b5i5"].astype(str) == "1"]
    k4.metric("⚠️ Disease outbreak reported", f"{ob_yes['pct'].iloc[0]:.1f}%" if not ob_yes.empty else "N/A")
else:
    k4.metric("⚠️ Disease outbreak reported", "N/A")

st.divider()

st.subheader("🏘️ Household type distribution")
c1, c2 = st.columns(2)
with c1:
    if has(d, "b5i4"):
        ht = weighted_pct(d, "b5i4", W)
        bar_with_table_toggle(st, ht, "b5i4", "pct", "Household type (by usual means of livelihood)", key="hh_type")
    else:
        no_data("Household type")
with c2:
    if has(d, "sec"):
        sec_map = {1: "Rural", 2: "Urban", "1": "Rural", "2": "Urban"}
        s = d.copy()
        s["Sector"] = s["sec"].map(sec_map).fillna(s["sec"].astype(str))
        sec = weighted_pct(s, "Sector", W)
        fig = px.pie(sec, names="Sector", values="pct", title="Rural vs Urban",
                     color="Sector", color_discrete_map=COLOR_SECTOR, hole=0.45)
        st.plotly_chart(style_pie(fig), use_container_width=True)
    else:
        no_data("Sector")

st.divider()

st.subheader("🧾 Household demographics")
c3, c4 = st.columns(2)
with c3:
    if has(d, "b5i2"):
        rel = group_top_n_other(weighted_pct(d, "b5i2", W), "b5i2")
        fig = px.pie(rel, names="b5i2", values="pct", title="Religion of household head", hole=0.45)
        st.plotly_chart(style_pie(fig), use_container_width=True)
    else:
        no_data("Religion")
with c4:
    if has(d, "b5i3"):
        sg = group_top_n_other(weighted_pct(d, "b5i3", W), "b5i3")
        fig = px.pie(sg, names="b5i3", values="pct", title="Social group", hole=0.45)
        st.plotly_chart(style_pie(fig), use_container_width=True)
    else:
        no_data("Social group")

st.divider()

st.subheader("💵 Consumption expenditure breakdown (5 components)")
comp_map = {
    "b5i7": "Purchased goods",
    "b5i6": "Home-grown produce",
    "b5i8": "Wages-in-kind",
    "b5i9": "Free collection",
    "b5i10": "Clothing & durables",
}
avail = {c: label for c, label in comp_map.items() if c in d.columns}
if avail:
    rows = []
    for c, label in avail.items():
        val = weighted_mean(d, c, W)
        rows.append({"Component": label, "Avg monthly value (Rs.)": val})
    comp_df = pd.DataFrame(rows).sort_values("Avg monthly value (Rs.)", ascending=False)
    fig = px.bar(comp_df, x="Component", y="Avg monthly value (Rs.)",
                 title="Average value per household by expenditure component", color="Component")
    st.plotly_chart(style_bar(fig, n_categories=len(comp_df), unit="Rs.", decimals=0), use_container_width=True)
    st.caption("Component labels are best-effort mappings of the survey's b5i6–b5i10 items; "
               "refer to the NSS Schedule 25.0 instruction manual for exact item definitions.")
else:
    no_data("Expenditure components")

st.divider()

st.subheader("🛡️ Insurance premium & survey response quality")
c5, c6 = st.columns(2)
with c5:
    if has(d, "b1i16"):
        rq = weighted_pct(d, "b1i16", W)
        bar_with_table_toggle(st, rq, "b1i16", "pct", "Reason for substitution (if any)", key="hh_sub")
    else:
        no_data("Substitution reason")
with c6:
    if has(d, "b2i9"):
        q = weighted_pct(d, "b2i9", W)
        bar_with_table_toggle(st, q, "b2i9", "pct", "Survey response / informant quality", key="hh_quality")
    else:
        no_data("Survey response quality")

st.divider()

# ---------------- NEW: Correlation heatmap — a number not shown above ----------------
st.subheader("🔗 How household numbers move together — not shown as bars/pies above")
corr_cols = ["hhsz", "umce", "b5i6", "b5i7", "b5i8", "b5i9", "b5i10"]
corr_labels = {
    "hhsz": "Household size", "umce": "Monthly expenditure",
    "b5i6": "Home-grown produce", "b5i7": "Purchased goods",
    "b5i8": "Wages-in-kind", "b5i9": "Free collection", "b5i10": "Clothing & durables",
}
drawn = correlation_heatmap(d, corr_cols, corr_labels,
                             "Correlation matrix: household size vs expenditure components")
if drawn:
    st.caption("The bar chart above only shows each component's *average value*. This heatmap answers a "
               "different question — do bigger households also spend more on each component, or not? "
               "Values near +1 move together, near -1 move oppositely, near 0 are unrelated.")
else:
    no_data("Correlation heatmap")

st.caption("Source: household.csv — weighted using `wt`.")