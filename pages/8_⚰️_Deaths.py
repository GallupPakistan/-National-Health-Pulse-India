import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from utils import (branding, page_header, require, weighted_mean, weighted_pct, weighted_share, wsum, age_band,
                   sidebar_filters, apply_filters, style_bar, style_pie, show, note, bar_with_table_toggle,
                   nested_sunburst, COLOR_GENDER, COLOR_SECTOR)

st.set_page_config(page_title="Deaths — National Health Pulse India", layout="wide", page_icon="⚰️")
branding()

W = "wt"
DBINS = [-1, 0, 4, 14, 29, 44, 59, 200]
DLABELS = ["Under 1", "1-4", "5-14", "15-29", "30-44", "45-59", "60+"]
de = require("deaths_full.csv", ["st", "sec", W, "b4c3", "b4c4", "b4c5", "b4c6", "b4c7", "b4c12"])
filters = sidebar_filters(de, "deaths")
d = apply_filters(de, filters, "deaths")
page_header("⚰️", "Deaths",
            "Members of the household who died in the last 365 days: age, gender, and care received before death",
            crumb="Dashboard / Deaths", badge_label="Sample deaths", badge_value=f"{len(d):,}")
if d.empty:
    st.warning("No records for this combination of filters.")
    st.stop()

att = pd.to_numeric(d["b4c5"], errors="coerce")
hosp = pd.to_numeric(d["b4c6"], errors="coerce")
times = pd.to_numeric(d["b4c7"], errors="coerce")
d = d.assign(band=pd.cut(pd.to_numeric(d["b4c4"], errors="coerce"), DBINS, labels=DLABELS))

st.info("📌 **Please note:** these are deaths *reported by surveyed households* — a count of events, not a mortality "
        "rate (no population denominator is used here). The sample is small (a few thousand deaths), so slices by state "
        "or narrow age groups are only indicative.")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("⚰️ Deaths reported (weighted)", f"{wsum(d, W):,.0f}")
k2.metric("🎂 Average age at death", f"{weighted_mean(d, 'b4c4', W):.1f} yrs")
k3.metric("🩺 Had medical attention before death", f"{weighted_share(d, att == 1, W, universe=att.notna()):.1f}%")
k4.metric("🏥 Hospitalised at least once in the year", f"{weighted_share(d, hosp == 1, W, universe=hosp.notna()):.1f}%")
k5.metric("🔁 Avg admissions (if hospitalised)", f"{weighted_mean(d[hosp == 1], 'b4c7', W):.1f}" if (hosp == 1).any() else "N/A")

st.divider()
c1, c2, c3 = st.columns(3)
with c1:
    show(style_pie(px.pie(weighted_pct(d, "b4c3", W), names="b4c3", values="pct", title="Gender", hole=0.45,
                          color="b4c3", color_discrete_map=COLOR_GENDER), height=400))
with c2:
    show(style_pie(px.pie(weighted_pct(d, "sec", W), names="sec", values="pct", title="Rural vs Urban", hole=0.45,
                          color="sec", color_discrete_map=COLOR_SECTOR), height=400))
with c3:
    ab = d.dropna(subset=["band"]).groupby("band", observed=True)[W].sum().reset_index()
    ab["pct"] = ab[W] / ab[W].sum() * 100
    ab["band"] = ab["band"].astype(str)
    fig = px.bar(ab, x="band", y="pct", color="band", category_orders={"band": DLABELS}, title="Age at death (years)")
    show(style_bar(fig, height=400, n_categories=len(ab)))
note("'Under 1' is age 0 (infants); ages are grouped as 1-4, 5-14, 15-29, 30-44, 45-59, 60+ so that no age is counted twice.")

st.divider()
st.subheader("🩺 Care before death")
c4, c5 = st.columns(2)
with c4:
    rows = []
    for label, s in [("Medical attention received", att), ("Hospitalised at least once", hosp)]:
        for g in ["male", "female"]:
            m = d["b4c3"].astype(str) == g
            if (m & s.notna()).any():
                rows.append({"Measure": label, "Gender": g, "%": weighted_share(d, s == 1, W, universe=m & s.notna())})
    if rows:
        fig = px.bar(pd.DataFrame(rows), x="Measure", y="%", color="Gender", barmode="group", color_discrete_map=COLOR_GENDER,
                     title="Share of deaths with … before death, by gender")
        show(fig)
with c5:
    tt = d[times.notna()].assign(n=lambda x: pd.to_numeric(x["b4c7"], errors="coerce").clip(upper=4).astype(int).astype(str).replace({"4": "4 or more"}))
    if len(tt):
        cnt = tt.groupby("n", observed=True)[W].sum().reset_index()
        cnt["pct"] = cnt[W] / cnt[W].sum() * 100
        fig = px.bar(cnt, x="n", y="pct", color="n", title="Number of admissions (among those hospitalised)")
        show(style_bar(fig, n_categories=len(cnt)))

st.divider()
st.subheader("🌍 Deaths by state (share of all reported deaths)")
bar_with_table_toggle(st, weighted_pct(d, "st", W), "st", "pct", "Share of deaths by state (%)", key="d_state", top_n=12)
note("Shares follow both state population and sample design — this is not a state mortality comparison.")

st.divider()
st.subheader("🤰 Women who died after being pregnant during the year")
tm = d[d["b4c12"].notna()]
if len(tm):
    lab = weighted_pct(tm, "b4c12", W)
    bar_with_table_toggle(st, lab, "b4c12", "pct", "Timing of death (women 15-49 pregnant at some point in the year)",
                          key="d_timing", top_n=6, label_width=40)
    note(f"Only {len(tm)} sampled deaths fall in this group — far too few for percentages to be reliable. Shown for completeness.")
else:
    note("No deaths in this group under the current filters.")

st.divider()
st.subheader("🌳 Gender → age group → sector")
tr = d.dropna(subset=["band"]).assign(band=lambda x: x["band"].astype(str))
nested_sunburst(tr, ["b4c3", "band", "sec"], W, "Deaths: Gender → Age group → Sector", kind="treemap")

st.caption("Source: deaths_full.csv — weighted with `wt`.")
