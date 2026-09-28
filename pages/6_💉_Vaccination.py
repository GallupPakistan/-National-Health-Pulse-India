import pandas as pd
import plotly.express as px
import streamlit as st

from utils import (branding, page_header, require, weighted_mean, weighted_pct, weighted_share, wsum, age_band,
                   sidebar_filters, apply_filters, style_bar, style_pie, show, note, bar_with_table_toggle,
                   rank_callout, choropleth_state_map, COLOR_GENDER, COLOR_SECTOR, AGE_LABELS)

st.set_page_config(page_title="Vaccination — National Health Pulse India", layout="wide", page_icon="💉")
branding()

W = "wt"
VAC = "Whether received any vaccine"
# Schedule 25.0, Block 10, item 4 - short names for the 27 vaccine codes (1-9 = Universal Immunization Programme)
SHORT = {1: "Birth & first doses (BCG, OPV, Hep B, Penta-1, RVV-1, fIPV)", 2: "PCV-1", 3: "OPV-2, Penta-2, RVV-2",
         4: "OPV-3, Penta-3, fIPV-2, RVV-3, PCV-2", 5: "MR-1, JE-1, PCV booster, fIPV-3",
         6: "MR-2, JE-2, DPT booster-1, OPV booster", 7: "DPT booster-2", 8: "Td (tetanus & adult diphtheria)",
         9: "Td1 / Td2 / Td booster (pregnant women)", 10: "Hepatitis A", 11: "DTwP / DTaP", 12: "IPV",
         13: "MMR (3rd dose)", 14: "Pneumococcal conjugate (sickle cell)", 15: "Tdap / Td", 16: "Varicella",
         17: "HPV (2 doses)", 18: "HPV (3 doses)", 19: "PSV23 (pneumococcal)", 20: "Herpes zoster", 21: "Hepatitis B booster",
         22: "Oral cholera", 23: "Yellow fever", 24: "Rabies", 25: "COVID-19 booster", 26: "Meningococcal",
         27: "Annual influenza"}
VAGE_BINS = [-1, 0, 1, 4, 14, 49, 200]
VAGE_LABELS = ["Under 1", "1", "2-4", "5-14", "15-49", "50+"]

vac = require("vaccination_full.csv", ["st", "sec", W, "b10i3", "b10i4", "b10i4_code", "b10i5", "b10i6", "b10i7", "person_b3c4"])
master = require("nss_health_master_FULL.csv", ["state", "sector", "Gender", "Age(in years)", "final_weight", VAC])

filters = sidebar_filters(vac, "vacc")
dv = apply_filters(vac, filters, "vacc")
pop = apply_filters(master, filters, "master")
pop_any_age = apply_filters(master, filters, "master", skip=("age",))

page_header("💉", "Vaccination",
            "Who received a vaccine in the last 365 days, which vaccines, from where, and at what cost",
            crumb="Dashboard / Vaccination", badge_label="Vaccination records", badge_value=f"{len(dv):,}")
if dv.empty or pop.empty:
    st.warning("No records for this combination of filters.")
    st.stop()

if "b10i4_code" in dv.columns:
    code = pd.to_numeric(dv["b10i4_code"], errors="coerce")
    dv = dv.assign(vaccine=code.map(SHORT).fillna(dv["b10i4"].astype(str)), uip=(code <= 9).map({True: "Universal Immunization Programme (codes 1-9)", False: "Other vaccines (codes 10-27)"}))
else:
    dv = dv.assign(vaccine=dv["b10i4"].astype(str), uip="Unknown")

vacc_flag = pd.to_numeric(pop[VAC], errors="coerce")
coverage = weighted_share(pop, vacc_flag == 1, "final_weight", universe=vacc_flag.notna())
kids = pop_any_age[pd.to_numeric(pop_any_age["Age(in years)"], errors="coerce").between(0, 4)]
kflag = pd.to_numeric(kids[VAC], errors="coerce")
kid_cov = weighted_share(kids, kflag == 1, "final_weight", universe=kflag.notna()) if len(kids) else float("nan")
paid = pd.to_numeric(dv["b10i6"], errors="coerce") == 1
govt = dv["b10i5"].astype(str).str.startswith("govt")

# ---------------- state coverage table (real coverage: persons vaccinated / persons) ----------------
p = pop.assign(v=(vacc_flag == 1), vw=lambda x: x["final_weight"] * (vacc_flag == 1))
st_cov = p.groupby("state", observed=True).agg(vw=("vw", "sum"), w=("final_weight", "sum"), n=("v", "size")).reset_index()
st_cov["cov"] = st_cov["vw"] / st_cov["w"] * 100
rank_callout(st_cov, "state", "cov", "n", "The share of persons who received any vaccine in the last 365 days", coverage,
             fmt="{:.1f}", suffix="%",
             caution="This counts anyone vaccinated in the year (any age, any vaccine), so it mostly tracks the share of "
                     "young children and pregnant women in each state.")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("💉 Persons vaccinated, last 365 days", f"{coverage:.1f}%", help="Weighted % of persons who received any vaccine.")
k2.metric("👶 Children aged 0-4 vaccinated", f"{kid_cov:.1f}%" if kid_cov == kid_cov else "N/A",
          help="Same measure restricted to ages 0-4 (ignores the age filter).")
k3.metric("🧮 Vaccine doses recorded (weighted)", f"{wsum(dv, W):,.0f}")
k4.metric("💳 Records where a fee was paid", f"{weighted_share(dv, paid, W):.1f}%")
k5.metric("💰 Avg fee where paid", f"Rs. {weighted_mean(dv[paid], 'b10i7', W):,.0f}" if paid.any() else "N/A")

st.divider()
st.subheader("📈 Coverage by age group and gender")
cv = pop.assign(band=age_band(pop["Age(in years)"]), vw=pop["final_weight"] * (vacc_flag == 1))
g = cv.groupby(["band", "Gender"], observed=True).agg(vw=("vw", "sum"), w=("final_weight", "sum")).reset_index()
g = g[g["Gender"].astype(str).isin(["male", "female"])]
if not g.empty:
    g["cov"] = g["vw"] / g["w"] * 100
    g["band"], g["Gender"] = g["band"].astype(str), g["Gender"].astype(str)
    fig = px.bar(g, x="band", y="cov", color="Gender", barmode="group", color_discrete_map=COLOR_GENDER,
                 category_orders={"band": AGE_LABELS}, title="% of persons who received any vaccine in the last 365 days")
    fig.update_layout(yaxis_title="%", xaxis_title="Age group (years)")
    show(fig)
    note("Age 0 (infants) is counted in the 0-4 group. The question covers the last 365 days only, so this is "
         "vaccination received during the year, not completed immunisation status.")

st.divider()
st.subheader("🗺️ Coverage by state")
c1, c2 = st.columns(2)
with c1:
    bar_with_table_toggle(st, st_cov, "state", "cov", "Persons vaccinated in the last 365 days (%)", key="v_state")
with c2:
    choropleth_state_map(st_cov, "state", "cov", "Persons vaccinated (%)", unit="%", height=480)

st.divider()
st.subheader("🧬 Which vaccines")
c3, c4 = st.columns([3, 2])
with c3:
    bar_with_table_toggle(st, weighted_pct(dv, "vaccine", W), "vaccine", "pct", "Vaccine records (% of all doses recorded)",
                          key="v_type", top_n=10, label_width=50)
with c4:
    show(style_pie(px.pie(weighted_pct(dv, "uip", W), names="uip", values="pct",
                          title="Universal Immunization Programme vs other", hole=0.45), height=400))
note("Each row is one vaccine record (one person can have several). Code groups follow Schedule 25.0, Block 10.")

st.divider()
st.subheader("🏥 Source of vaccination and cost")
c5, c6, c7 = st.columns(3)
with c5:
    show(style_pie(px.pie(weighted_pct(dv, "b10i5", W), names="b10i5", values="pct", title="Where vaccinated", hole=0.45), height=400))
with c6:
    by_src = dv[paid].assign(b10i5=lambda x: x["b10i5"].astype(str))
    if len(by_src):
        rows = by_src.assign(fee=pd.to_numeric(by_src["b10i7"], errors="coerce"), w=by_src[W])
        rows["fw"] = rows["fee"] * rows["w"]
        t = rows.dropna(subset=["fee"]).groupby("b10i5", observed=True).agg(fw=("fw", "sum"), w=("w", "sum")).reset_index()
        t["mean"] = t["fw"] / t["w"]
        fig = px.bar(t.sort_values("mean"), x="mean", y="b10i5", orientation="h", color="b10i5", title="Avg fee where a fee was paid (Rs.)")
        fig.update_layout(yaxis_title="", showlegend=False, xaxis_title="Rs.")
        show(style_bar(fig, horizontal=True, n_categories=len(t), unit="Rs.", decimals=0))
with c7:
    share_paid = dv.assign(paid=paid.map({True: "Fee paid", False: "No fee"}))
    show(style_pie(px.pie(weighted_pct(share_paid, "paid", W), names="paid", values="pct", title="Records with a fee", hole=0.45), height=400))

st.divider()
st.subheader("👥 Age of the vaccinated person (records)")
ag = dv.assign(vband=pd.cut(pd.to_numeric(dv["b10i3"], errors="coerce"), VAGE_BINS, labels=VAGE_LABELS)).dropna(subset=["vband"])
gg = ag.groupby("vband", observed=True)[W].sum().reset_index()
gg["pct"] = gg[W] / gg[W].sum() * 100
gg["vband"] = gg["vband"].astype(str)
fig = px.bar(gg, x="vband", y="pct", color="vband", category_orders={"vband": VAGE_LABELS},
             title="Vaccine records by age of the person (years; 'Under 1' = age 0)")
show(style_bar(fig, n_categories=len(gg)))

st.caption("Source: nss_health_master_FULL.csv (coverage) and vaccination_full.csv (records) — weighted.")
