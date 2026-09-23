import streamlit as st
import pandas as pd
import plotly.express as px
from utils import (branding, page_header, load, has, weighted_mean, weighted_pct,
                    sidebar_filters, apply_filters, style_bar, style_pie, no_data,
                    bar_with_table_toggle, COLOR_GENDER, COLOR_SECTOR, nested_sunburst)

st.set_page_config(page_title="Deaths — National Health Pulse India", layout="wide", page_icon="⚰️")
branding()

df = load("deaths_full.csv")
if df.empty:
    st.error("`deaths_full.csv` not found in the `data/` folder.")
    st.stop()

# b4c3 gender, b4c4 age at death, b4c12 cause context (e.g. "during delivery")
filters = sidebar_filters(df, kind="deaths")
d = apply_filters(df, filters)
W = "wt"

page_header("⚰️", "Deaths", "Mortality context captured by the survey — age, gender, state/sector, delivery-related deaths",
            crumb="Dashboard / Deaths", badge_label="Records", badge_value=f"{len(d):,}")

if has(d, "b4c4", W):
    _avg_age = weighted_mean(d, "b4c4", W)
    if _avg_age == _avg_age:  # not NaN
        st.info(f"📌 **Key takeaway:** The average age at death recorded in this survey is "
                f"**{_avg_age:.1f} years**. (Shown as a neutral summary statistic only — this figure "
                f"reflects reported deaths within the survey, not a ranked comparison across states.)")

k1, k2, k3 = st.columns(3)
k1.metric("⚰️ Deaths (weighted)", f"{pd.to_numeric(d[W], errors='coerce').sum():,.0f}" if has(d, W) else "N/A")
k2.metric("📆 Avg age at death", f"{weighted_mean(d, 'b4c4', W):.1f} yrs" if has(d, "b4c4", W) else "N/A")

if has(d, "b4c12"):
    delivery = d[d["b4c12"].astype(str).str.lower() == "during delivery"]
    share = (pd.to_numeric(delivery[W], errors="coerce").sum() / pd.to_numeric(d[W], errors="coerce").sum() * 100) if has(d, W) else float("nan")
    k3.metric("🤰 Delivery-related deaths", f"{share:.2f}%" if share == share else "N/A")
else:
    k3.metric("🤰 Delivery-related deaths", "N/A")

st.divider()

st.subheader("👤 Gender & age pattern")
c1, c2 = st.columns(2)
with c1:
    if has(d, "b4c3"):
        g = weighted_pct(d, "b4c3", W)
        fig = px.pie(g, names="b4c3", values="pct", title="Gender split", color="b4c3",
                     color_discrete_map=COLOR_GENDER, hole=0.45)
        st.plotly_chart(style_pie(fig), use_container_width=True)
    else:
        no_data("Gender")
with c2:
    if has(d, "b4c4"):
        age = d[["b4c4", W]].dropna().copy()
        age["b4c4"] = pd.to_numeric(age["b4c4"], errors="coerce")
        bins = [-1, 1, 5, 18, 40, 60, 200]
        labels = ["<1 yr", "1-5 yrs", "6-18 yrs", "19-40 yrs", "41-60 yrs", "60+ yrs"]
        age["band"] = pd.cut(age["b4c4"], bins=bins, labels=labels, right=True)
        band = age.groupby("band", observed=True)[W].sum().reset_index()
        band["pct"] = (band[W] / band[W].sum() * 100).round(2)
        fig = px.bar(band, x="band", y="pct", title="Age-at-death distribution", color="band")
        st.plotly_chart(style_bar(fig, n_categories=len(band)), use_container_width=True)
    else:
        no_data("Age at death")

st.divider()

st.subheader("🗺️ State / sector-wise distribution")
c3, c4 = st.columns(2)
with c3:
    if has(d, "sec"):
        sec = weighted_pct(d, "sec", W)
        fig = px.pie(sec, names="sec", values="pct", title="Rural vs Urban", color="sec",
                     color_discrete_map=COLOR_SECTOR, hole=0.45)
        st.plotly_chart(style_pie(fig), use_container_width=True)
    else:
        no_data("Sector")
with c4:
    if has(d, "st"):
        s = weighted_pct(d, "st", W)
        bar_with_table_toggle(st, s, "st", "pct", "Deaths by state", key="deaths_state", top_n=10)
    else:
        no_data("State")

st.divider()

st.subheader("🤰 Delivery-related deaths")
if has(d, "b4c12"):
    dd = d.copy()
    dd["Delivery related"] = dd["b4c12"].apply(
        lambda v: "During delivery" if pd.notna(v) and str(v).lower() == "during delivery" else "Other")
    split = weighted_pct(dd, "Delivery related", W)
    fig = px.pie(split, names="Delivery related", values="pct", title="Share of deaths occurring during delivery", hole=0.45)
    st.plotly_chart(style_pie(fig), use_container_width=True)
else:
    no_data("Delivery-related cause flag")

st.divider()

# ---------------- NEW: Treemap — a joint number not shown above ----------------
st.subheader("🌳 Sector × Gender × Age-at-death — a joint view not shown above")
if has(d, "sec", "b4c3", "b4c4"):
    dd2 = d.copy()
    dd2["b4c4"] = pd.to_numeric(dd2["b4c4"], errors="coerce")
    bins = [-1, 1, 5, 18, 40, 60, 200]
    labels = ["<1 yr", "1-5 yrs", "6-18 yrs", "19-40 yrs", "41-60 yrs", "60+ yrs"]
    dd2["Age band"] = pd.cut(dd2["b4c4"], bins=bins, labels=labels, right=True)
    drawn = nested_sunburst(dd2, ["sec", "b4c3", "Age band"], W,
                             "Weighted deaths: Sector → Gender → Age band", kind="treemap")
    if drawn:
        st.caption("Sector, gender and age-at-death were each shown separately above. This treemap combines "
                   "all three — box size = weighted death count — surfacing, for instance, whether Rural "
                   "male deaths skew older or younger than Urban male deaths.")
    else:
        no_data("Sector × Gender × Age treemap")
else:
    no_data("Sector × Gender × Age treemap")

st.caption("Source: deaths_full.csv — weighted using `wt`.")