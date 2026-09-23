import streamlit as st
import pandas as pd
import plotly.express as px
from utils import (branding, page_header, load, has, weighted_pct, weighted_mean,
                    sidebar_filters, apply_filters, style_bar, style_pie, no_data,
                    bar_with_table_toggle, COLOR_SECTOR, decode_state_code, choropleth_state_map)

st.set_page_config(page_title="Vaccination — National Health Pulse India", layout="wide", page_icon="💉")
branding()

df = load("vaccination_full.csv")
if df.empty:
    st.error("`vaccination_full.csv` not found in the `data/` folder.")
    st.stop()

# b10i4 vaccine type(s), b10i5 source of vaccination, b10i7 expenditure
filters = sidebar_filters(df, kind="detail")
d = apply_filters(df, filters)
W = "wt"

page_header("💉", "Vaccination Deep-dive",
            "Vaccine-type wise coverage count, age-wise vaccination completion (children), state/sector-wise comparison",
            crumb="Dashboard / Vaccination", badge_label="Records", badge_value=f"{len(d):,}")

from utils import state_rank_avg, render_insight_callout
_nat, _bs, _bv, _ws, _wv = state_rank_avg(d, "st", "b10i7", W)
render_insight_callout(_nat, _bs, _bv, _ws, _wv, "Avg expenditure on vaccination",
                        fmt="{:,.0f}", unit="Rs. ", higher_is_worse=True)

k1, k2, k3 = st.columns(3)
k1.metric("💉 Vaccination records (weighted)", f"{pd.to_numeric(d[W], errors='coerce').sum():,.0f}" if has(d, W) else "N/A")
if has(d, "b10i7", W):
    from utils import weighted_mean
    k2.metric("💰 Avg expenditure on vaccination", f"Rs. {weighted_mean(d, 'b10i7', W):,.0f}")
else:
    k2.metric("💰 Avg expenditure on vaccination", "N/A")
if has(d, "person_b3c5"):
    kids = d[pd.to_numeric(d["person_b3c5"], errors="coerce") <= 5]
    k3.metric("👶 Records for children ≤5 yrs", f"{len(kids):,}")
else:
    k3.metric("👶 Records for children ≤5 yrs", "N/A")

st.divider()

st.subheader("💉 Vaccine-type wise coverage count")
if has(d, "b10i4"):
    vt = weighted_pct(d, "b10i4", W)
    bar_with_table_toggle(st, vt, "b10i4", "pct", "Vaccine(s) received (top combinations)", key="vac_type", top_n=10, label_width=45)
else:
    no_data("Vaccine type")

st.divider()

c1, c2 = st.columns(2)
with c1:
    st.subheader("🏥 Source of vaccination")
    if has(d, "b10i5"):
        src = weighted_pct(d, "b10i5", W)
        fig = px.pie(src, names="b10i5", values="pct", title="Govt. vs Private source", hole=0.45)
        st.plotly_chart(style_pie(fig), use_container_width=True)
    else:
        no_data("Source of vaccination")
with c2:
    st.subheader("🚻 Sector split")
    if has(d, "sec"):
        s = d.copy()
        s["Sector"] = s["sec"].map({1: "Rural", 2: "Urban", "1": "Rural", "2": "Urban"}).fillna(s["sec"].astype(str))
        sec = weighted_pct(s, "Sector", W)
        fig = px.pie(sec, names="Sector", values="pct", title="Rural vs Urban", color="Sector",
                     color_discrete_map=COLOR_SECTOR, hole=0.45)
        st.plotly_chart(style_pie(fig), use_container_width=True)
    else:
        no_data("Sector")

st.divider()

st.subheader("👶 Age-wise vaccination completion (children focus)")
if has(d, "person_b3c5"):
    age = d[["person_b3c5", W]].dropna().copy()
    age["person_b3c5"] = pd.to_numeric(age["person_b3c5"], errors="coerce")
    bins = [-1, 1, 2, 5, 12, 18, 200]
    labels = ["<1 yr", "1-2 yrs", "3-5 yrs", "6-12 yrs", "13-18 yrs", "18+ yrs"]
    age["band"] = pd.cut(age["person_b3c5"], bins=bins, labels=labels, right=True)
    band = age.groupby("band", observed=True)[W].sum().reset_index()
    band["pct"] = (band[W] / band[W].sum() * 100).round(2)
    fig = px.bar(band, x="band", y="pct", title="Vaccination records by age-group", color="band")
    st.plotly_chart(style_bar(fig, n_categories=len(band)), use_container_width=True)
else:
    no_data("Age of vaccinated person")

st.divider()

st.subheader("🗺️ State-wise vaccination coverage")
if has(d, "st"):
    from utils import get_state_list
    st_col = d.copy()
    cov = weighted_pct(st_col, "st", W)
    cov = cov.rename(columns={"st": "State code"})
    bar_with_table_toggle(st, cov, "State code", "pct", "Records by state code", key="vac_state", top_n=10)
    st.caption("State shown by numeric code (state names not present in this file); "
               "cross-reference with the Overview page's state list if needed.")
else:
    no_data("State")

st.caption("Source: vaccination_full.csv — weighted using `wt`.")