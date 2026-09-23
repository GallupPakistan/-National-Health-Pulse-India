import streamlit as st
import pandas as pd
import plotly.express as px
from utils import (branding, page_header, load, has, weighted_mean, weighted_pct,
                    sidebar_filters, apply_filters, style_bar, style_pie, no_data,
                    bar_with_table_toggle, COLOR_SECTOR, nested_sunburst)

st.set_page_config(page_title="Antenatal Care — National Health Pulse India", layout="wide", page_icon="🤰")
branding()

df = load("antenatal_full.csv")
if df.empty:
    st.error("`antenatal_full.csv` not found in the `data/` folder.")
    st.stop()

# b11c2 no. of ANC visits, b11c4 source of ANC care, b11c6 expenditure on ANC,
# b11c7 pregnancy/birth outcome, b11c8 place of delivery, birth_outcome flag
filters = sidebar_filters(df, kind="detail")
d = apply_filters(df, filters)
W = "wt"

page_header("🤰", "Antenatal Care Deep-dive",
            "ANC visit count distribution, source of care, birth outcome breakdown, state/sector-wise coverage for women",
            crumb="Dashboard / Antenatal Care", badge_label="Records", badge_value=f"{len(d):,}")

from utils import state_rank_avg, render_insight_callout
_nat, _bs, _bv, _ws, _wv = state_rank_avg(d, "st", "b11c2", W)
render_insight_callout(_nat, _bs, _bv, _ws, _wv, "Avg number of ANC visits",
                        fmt="{:.1f}", unit="", higher_is_worse=False)

k1, k2, k3, k4 = st.columns(4)
k1.metric("🤰 ANC records (weighted)", f"{pd.to_numeric(d[W], errors='coerce').sum():,.0f}" if has(d, W) else "N/A")
k2.metric("📅 Avg ANC visits", f"{weighted_mean(d, 'b11c2', W):.1f}" if has(d, "b11c2", W) else "N/A")
k3.metric("💰 Avg ANC expenditure", f"Rs. {weighted_mean(d, 'b11c6', W):,.0f}" if has(d, "b11c6", W) else "N/A")

if has(d, "birth_outcome"):
    bo = weighted_pct(d, "birth_outcome", W)
    live = bo[bo["birth_outcome"].astype(str) == "1"]
    k4.metric("👶 Live-birth share", f"{live['pct'].iloc[0]:.1f}%" if not live.empty else "N/A")
else:
    k4.metric("👶 Live-birth share", "N/A")

st.divider()

st.subheader("📊 ANC visit count distribution")
if has(d, "b11c2"):
    vc = d[["b11c2", W]].dropna().copy()
    vc["b11c2"] = pd.to_numeric(vc["b11c2"], errors="coerce")
    bins = [-1, 0, 3, 6, 9, 200]
    labels = ["0 visits", "1-3 visits", "4-6 visits", "7-9 visits", "10+ visits"]
    vc["band"] = pd.cut(vc["b11c2"], bins=bins, labels=labels, right=True)
    band = vc.groupby("band", observed=True)[W].sum().reset_index()
    band["pct"] = (band[W] / band[W].sum() * 100).round(2)
    fig = px.bar(band, x="band", y="pct", title="Number of antenatal visits", color="band")
    st.plotly_chart(style_bar(fig, n_categories=len(band)), use_container_width=True)
else:
    no_data("ANC visit count")

st.divider()

c1, c2 = st.columns(2)
with c1:
    st.subheader("🏥 Source of ANC care")
    if has(d, "b11c4"):
        src = weighted_pct(d, "b11c4", W)
        bar_with_table_toggle(st, src, "b11c4", "pct", "Where antenatal care was received", key="anc_src", top_n=6)
    else:
        no_data("Source of ANC care")
with c2:
    st.subheader("🏠 Place of delivery")
    if has(d, "b11c8"):
        pod = weighted_pct(d, "b11c8", W)
        fig = px.pie(pod, names="b11c8", values="pct", title="Place of delivery", hole=0.45)
        st.plotly_chart(style_pie(fig), use_container_width=True)
    else:
        no_data("Place of delivery")

st.divider()

st.subheader("👶 Birth outcome breakdown")
if has(d, "b11c7"):
    bo = weighted_pct(d, "b11c7", W)
    fig = px.pie(bo, names="b11c7", values="pct", title="Pregnancy / birth outcome", hole=0.45)
    st.plotly_chart(style_pie(fig), use_container_width=True)
else:
    no_data("Birth outcome")

st.divider()

st.subheader("🗺️ State/sector-wise antenatal care coverage")
c3, c4 = st.columns(2)
with c3:
    if has(d, "sec"):
        s = d.copy()
        s["Sector"] = s["sec"].map({1: "Rural", 2: "Urban", "1": "Rural", "2": "Urban"}).fillna(s["sec"].astype(str))
        sec = weighted_pct(s, "Sector", W)
        fig = px.pie(sec, names="Sector", values="pct", title="Rural vs Urban", color="Sector",
                     color_discrete_map=COLOR_SECTOR, hole=0.45)
        st.plotly_chart(style_pie(fig), use_container_width=True)
    else:
        no_data("Sector")
with c4:
    if has(d, "st"):
        state_cov = weighted_pct(d, "st", W).rename(columns={"st": "State code"})
        bar_with_table_toggle(st, state_cov, "State code", "pct", "Records by state code", key="anc_state", top_n=10)
    else:
        no_data("State")

st.divider()

# ---------------- NEW: Sunburst — a joint number not shown above ----------------
st.subheader("🌞 Source of care × Place of delivery × Birth outcome — a joint view not shown above")
drawn = nested_sunburst(d, ["b11c4", "b11c8", "b11c7"], W,
                         "Weighted records: Source of ANC care → Place of delivery → Birth outcome")
if drawn:
    st.caption("Source of care, place of delivery and birth outcome were each shown separately above as "
               "individual bar/pie charts. This combines all three so you can see, for example, whether "
               "home deliveries after private ANC care show a different outcome mix than hospital deliveries.")
else:
    no_data("Source × Place × Outcome sunburst")

st.caption("Source: antenatal_full.csv — weighted using `wt`. Focused view for women of reproductive age captured by the survey.")