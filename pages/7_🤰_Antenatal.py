import pandas as pd
import plotly.express as px
import streamlit as st

from utils import (branding, page_header, require, weighted_mean, weighted_pct, weighted_share, wsum, group_wmean,
                   sidebar_filters, apply_filters, style_bar, style_pie, show, note, bar_with_table_toggle,
                   rank_callout, choropleth_state_map, nested_sunburst, COLOR_SECTOR)

st.set_page_config(page_title="Antenatal & Childbirth — National Health Pulse India", layout="wide", page_icon="🤰")
branding()

W = "wt"
ACOLS = ["st", "sec", W, "b11c2", "b11c4", "b11c4_code", "b11c6", "b11c7", "b11c7_code", "b11c8", "b11c8_code", "b11c9",
         "b11c11", "b11c11_code", "b11c13"]
an = require("antenatal_full.csv", ACOLS)
filters = sidebar_filters(an, "ante")
d = apply_filters(an, filters, "ante")
page_header("🤰", "Antenatal, Childbirth & Postnatal Care",
            "Women aged 15-49 who were pregnant in the last 365 days: care received, place of delivery, outcome, cost",
            crumb="Dashboard / Antenatal", badge_label="Sample pregnancies", badge_value=f"{len(d):,}")
if d.empty:
    st.warning("No records for this combination of filters.")
    st.stop()

# Schedule 25.0, Block 11 codes:  col 4 / col 11 source of ANC / PNC (8 = no care received)
#   col 7 outcome: 1 continuing, 2 live birth, 3 stillbirth, 4 abortion, 5-7 mother died, 9 other
#   col 8 place of delivery: 1 govt hospital, 2 charitable/NGO, 3 private hospital, 4 home
c4 = pd.to_numeric(d["b11c4_code"], errors="coerce")
c7 = pd.to_numeric(d["b11c7_code"], errors="coerce")
c8 = pd.to_numeric(d["b11c8_code"], errors="coerce")
c11 = pd.to_numeric(d["b11c11_code"], errors="coerce")
childbirth = c7.isin([2, 3, 5, 6])                 # live birth or stillbirth (incl. mother died)
dcb = d[childbirth]

anc = weighted_share(d, c4 != 8, W, universe=c4.notna())
pnc = weighted_share(d, c11 != 8, W, universe=childbirth & c11.notna())
inst_mask = childbirth & c8.notna()
inst = weighted_share(d, c8.isin([1, 2, 3]), W, universe=inst_mask)

# ---------------- key takeaway ----------------
t = d[inst_mask].assign(i=c8[inst_mask].isin([1, 2, 3]))
t["wi"] = t[W] * t["i"]
st_inst = t.groupby("st", observed=True).agg(wi=("wi", "sum"), w=(W, "sum"), n=(W, "size")).reset_index()
st_inst["rate"] = st_inst["wi"] / st_inst["w"] * 100
rank_callout(st_inst, "st", "rate", "n", "The share of childbirths that took place in a medical institution", inst,
             fmt="{:.1f}", suffix="%",
             caution="Institutional delivery is high in most states; a few states with smaller samples differ more.")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("🤰 Pregnancies (weighted)", f"{wsum(d, W):,.0f}")
k2.metric("🩺 Received antenatal care", f"{anc:.1f}%", help="Any source other than 'no care was received'. Official: about 98%.")
k3.metric("🍼 Received postnatal care", f"{pnc:.1f}%", help="Among childbirths (live or stillbirth). Official: 92% rural, 95% urban.")
k4.metric("🏥 Childbirths in an institution", f"{inst:.1f}%", help="Government, charitable or private hospital. Official: about 96%.")
k5.metric("💰 Avg spend on antenatal care", f"Rs. {weighted_mean(d, 'b11c6', W):,.0f}",
          help="Per pregnancy, including those who spent nothing (excludes those with no ANC).")

st.divider()
st.subheader("🩺 Antenatal & postnatal care")
c1, c2 = st.columns(2)
with c1:
    show(style_pie(px.pie(weighted_pct(d, "b11c4", W), names="b11c4", values="pct", title="Major source of antenatal care", hole=0.45), height=430))
with c2:
    show(style_pie(px.pie(weighted_pct(dcb, "b11c11", W), names="b11c11", values="pct",
                          title="Major source of postnatal care (childbirths)", hole=0.45), height=430))
note("The number of ANC visits is not collected in this schedule; the indicators are whether care was received and from where.")

st.divider()
st.subheader("🏥 Childbirth")
c3, c4 = st.columns(2)
with c3:
    show(style_pie(px.pie(weighted_pct(d[inst_mask], "b11c8", W), names="b11c8", values="pct",
                          title="Place of delivery (childbirths)", hole=0.45), height=430))
with c4:
    bar_with_table_toggle(st, weighted_pct(d, "b11c7", W), "b11c7", "pct", "Outcome of pregnancy (all pregnancies)",
                          key="ante_outcome", top_n=8, label_width=46)
home = d[c8 == 4]
if len(home) and home["b11c9"].notna().any():
    st.subheader("🏠 Who attended home deliveries")
    bar_with_table_toggle(st, weighted_pct(home, "b11c9", W), "b11c9", "pct", "Delivery attended by (home deliveries)",
                          key="ante_attendant", top_n=6)

st.divider()
st.subheader("💰 Spending")
c5, c6 = st.columns(2)
with c5:
    rows = []
    for s in ["Rural", "Urban"]:
        ds = d[d["sec"].astype(str) == s]
        if len(ds):
            rows.append({"Sector": s, "Avg ANC spend (Rs.)": weighted_mean(ds, "b11c6", W),
                         "Avg PNC spend (Rs.)": weighted_mean(ds, "b11c13", W)})
    if rows:
        m = pd.DataFrame(rows).melt(id_vars="Sector", var_name="Measure", value_name="Rs.")
        fig = px.bar(m, x="Measure", y="Rs.", color="Sector", barmode="group", color_discrete_map=COLOR_SECTOR,
                     title="Average spend per pregnancy (Rs.)")
        show(fig)
with c6:
    by = group_wmean(d[d["b11c6"].notna()], "b11c4", "b11c6", W)
    if not by.empty:
        by["b11c4"] = by["b11c4"].astype(str)
        fig = px.bar(by.sort_values("mean"), x="mean", y="b11c4", orientation="h", color="b11c4",
                     title="Average antenatal spend by source of care (Rs.)")
        fig.update_layout(yaxis_title="", showlegend=False, xaxis_title="Rs.")
        show(style_bar(fig, horizontal=True, n_categories=len(by), unit="Rs.", decimals=0))

st.divider()
st.subheader("👩 Age of the women")
ag = d.assign(band=pd.cut(pd.to_numeric(d["b11c2"], errors="coerce"), [14, 19, 24, 29, 34, 39, 100],
                          labels=["15-19", "20-24", "25-29", "30-34", "35-39", "40+"]))
gg = ag.dropna(subset=["band"]).groupby("band", observed=True)[W].sum().reset_index()
gg["pct"] = gg[W] / gg[W].sum() * 100
gg["band"] = gg["band"].astype(str)
fig = px.bar(gg, x="band", y="pct", color="band", title="Age at pregnancy (years)")
show(style_bar(fig, n_categories=len(gg)))
note(f"Average age: {weighted_mean(d, 'b11c2', W):.1f} years. A few respondents are recorded above 49 (data as collected).")

st.divider()
st.subheader("🗺️ Institutional childbirth by state")
c7, c8m = st.columns(2)
with c7:
    bar_with_table_toggle(st, st_inst, "st", "rate", "Childbirths in a medical institution (%)", key="ante_state")
with c8m:
    choropleth_state_map(st_inst.rename(columns={"st": "state"}), "state", "rate", "Institutional childbirth (%)", unit="%", height=480)

st.divider()
st.subheader("🌞 Care pathway (childbirths)")
sb = dcb.assign(b11c4=dcb["b11c4"].astype(str), b11c8=dcb["b11c8"].astype(str), b11c7=dcb["b11c7"].astype(str))
nested_sunburst(sb, ["b11c4", "b11c8", "b11c7"], W, "Source of ANC → place of delivery → outcome")

st.caption("Source: antenatal_full.csv — weighted with `wt`.")
