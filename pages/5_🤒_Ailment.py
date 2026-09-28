import pandas as pd
import plotly.express as px
import streamlit as st

from utils import (branding, page_header, require, weighted_mean, weighted_pct, weighted_share, wsum, group_wmean,
                   age_band, sidebar_filters, apply_filters, style_bar, style_pie, show, note,
                   bar_with_table_toggle, rank_callout, nested_sunburst, MIN_N, COLOR_GENDER, COLOR_SECTOR, AGE_LABELS)

st.set_page_config(page_title="Ailment — National Health Pulse India", layout="wide", page_icon="🤒")
branding()

W = "wt"
ACOLS = ["st", "sec", W, "b8i5", "b8i6", "b8i7", "b8i9", "b8i10", "b8i11", "b8i12", "exp_total_spell",
         "exp_oop_spell_total", "exp_medical_spell", "exp_oop_spell_medical"]
ail = require("ailment_spells_full.csv", ACOLS, events=True)
master = require("nss_health_master_FULL.csv", ["state", "sector", "Gender", "Age(in years)", "final_weight",
                                                "n_ailment_spells_15d"])

filters = sidebar_filters(ail, "ailment")
da = apply_filters(ail, filters, "ailment")
pop = apply_filters(master, filters, "master")

page_header("🤒", "Ailment (last 15 days)",
            "Ailment spells reported for the 15 days before the survey: what, how treated, where, and at what cost",
            crumb="Dashboard / Ailment", badge_label="Sample spells", badge_value=f"{len(da):,}")
if da.empty or pop.empty:
    st.warning("No records for this combination of filters.")
    st.stop()

# Official basis for out-patient cost: spells that were NOT hospitalised (b8i10 = 2) and were treated on medical
# advice (b8i11 = 1). This reproduces the report's average of about Rs. 861 per treated spell.
b10 = pd.to_numeric(da["b8i10"], errors="coerce")
b11 = pd.to_numeric(da["b8i11"], errors="coerce")
treated = da[(b10 == 2) & (b11 == 1)]
ppra = weighted_share(pop, pop["n_ailment_spells_15d"] > 0, "final_weight")
chronic_share = weighted_share(da, pd.to_numeric(da["b8i6"], errors="coerce") == 1, W,
                               universe=pd.to_numeric(da["b8i6"], errors="coerce").notna())
no_tx = weighted_share(da, da["b8i9"].astype(str) == "no treatment", W, universe=da["b8i9"].notna())

# ---------------- key takeaway ----------------
st_cost = group_wmean(treated, "st", "exp_oop_spell_medical", W)
nat_cost = weighted_mean(treated, "exp_oop_spell_medical", W) if len(treated) else float("nan")
rank_callout(st_cost, "st", "mean", "n", "The average out-of-pocket medical expenditure per treated out-patient spell",
             nat_cost, unit="Rs. ",
             caution="Costs depend on the illness mix and provider type, so this is not a ranking of health systems.")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("🤒 Ailment spells (weighted)", f"{wsum(da, W):,.0f}")
k2.metric("📊 Ailing persons, 15 days (PPRA)", f"{ppra:.1f}%", help="Persons with at least one ailment in the last 15 days. Official: 13.1%.")
k3.metric("💊 Avg OOP medical / treated spell", f"Rs. {nat_cost:,.0f}" if nat_cost == nat_cost else "N/A",
          help="Non-hospitalised spells treated on medical advice; medical expenditure minus reimbursement. Official: about Rs. 861.")
k4.metric("🩺 Chronic share of spells", f"{chronic_share:.1f}%",
          help="Spells flagged chronic (Block 8, item 6) — spells, not persons.")
k5.metric("🚫 Spells with no treatment", f"{no_tx:.1f}%")

st.divider()
st.subheader("📈 Who reports an ailment — by age group and gender")
pp = pop.assign(band=age_band(pop["Age(in years)"]), ail=pop["n_ailment_spells_15d"] > 0)
pp["wa"] = pp["final_weight"] * pp["ail"]
g = pp.groupby(["band", "Gender"], observed=True).agg(wa=("wa", "sum"), w=("final_weight", "sum")).reset_index()
g = g[g["Gender"].astype(str).isin(["male", "female"])]
if not g.empty:
    g["rate"] = g["wa"] / g["w"] * 100
    g["band"], g["Gender"] = g["band"].astype(str), g["Gender"].astype(str)
    fig = px.bar(g, x="band", y="rate", color="Gender", barmode="group", color_discrete_map=COLOR_GENDER,
                 category_orders={"band": AGE_LABELS}, title="PPRA: % of persons with an ailment in the last 15 days")
    fig.update_layout(yaxis_title="%", xaxis_title="Age group (years)")
    show(fig)

st.divider()
st.subheader("🦠 What people suffer from")
c1, c2 = st.columns([3, 2])
with c1:
    bar_with_table_toggle(st, weighted_pct(da, "b8i5", W), "b8i5", "pct", "Nature of ailment (% of spells)",
                          key="a_nature", top_n=10, label_width=46)
with c2:
    ch = da.assign(kind=pd.to_numeric(da["b8i6"], errors="coerce").map({1.0: "Chronic", 2.0: "Not chronic"}))
    show(style_pie(px.pie(weighted_pct(ch.dropna(subset=["kind"]), "kind", W), names="kind", values="pct",
                          title="Chronic vs not chronic (spells)", hole=0.45), height=400))
    bar_with_table_toggle(st, weighted_pct(da, "b8i7", W), "b8i7", "pct", "Status of ailment (onset / continuation)",
                          key="a_status", top_n=5, label_width=34)

st.divider()
st.subheader("💊 How and where ailments are treated")
c3, c4 = st.columns(2)
with c3:
    tx = da[(da["b8i9"].astype(str) != "no treatment") & da["b8i9"].notna()]
    bar_with_table_toggle(st, weighted_pct(tx, "b8i9", W), "b8i9", "pct", "System of treatment (treated spells only)",
                          key="a_tx", top_n=6, label_width=34)
    note("'Allopathy' etc. describe the system of medicine used; untreated spells are shown as a KPI above.")
with c4:
    lc = da[(b10 == 2) & da["b8i12"].notna()]
    rows = []
    for s in ["Rural", "Urban"]:
        ds = lc[lc["sec"].astype(str) == s]
        if len(ds):
            t = weighted_pct(ds, "b8i12", W)
            t["Sector"] = s
            rows.append(t)
    if rows:
        lct = pd.concat(rows)
        lct["b8i12"] = lct["b8i12"].astype(str)
        fig = px.bar(lct, x="b8i12", y="pct", color="Sector", barmode="group", color_discrete_map=COLOR_SECTOR,
                     title="Level of care used (non-hospitalised spells), by sector")
        fig.update_layout(xaxis_title="", yaxis_title="%")
        fig.update_xaxes(tickangle=-20)
        show(fig)

st.divider()
st.subheader("💰 Cost of out-patient care")
c5, c6 = st.columns(2)
with c5:
    if len(treated):
        means = pd.DataFrame({"Measure": ["Medical expenditure", "Out-of-pocket medical", "Total expenditure", "Out-of-pocket total"],
                              "Rs.": [weighted_mean(treated, "exp_medical_spell", W), nat_cost,
                                      weighted_mean(treated, "exp_total_spell", W), weighted_mean(treated, "exp_oop_spell_total", W)]})
        fig = px.bar(means, x="Measure", y="Rs.", color="Measure", title="Average per treated out-patient spell (Rs.)")
        show(style_bar(fig, n_categories=4, unit="Rs.", decimals=0))
        note("Treated = not hospitalised and treated on medical advice. Total expenditure adds transport and other "
             "non-medical costs to the medical expenditure.")
with c6:
    if len(treated):
        top = weighted_pct(treated, "b8i5", W).head(8)["b8i5"].astype(str).tolist()
        sub = treated[treated["b8i5"].astype(str).isin(top)].assign(b8i5=lambda x: x["b8i5"].astype(str))
        by = group_wmean(sub, "b8i5", "exp_oop_spell_medical", W)
        by = by[by["n"] >= 30]
        if not by.empty:
            fig = px.bar(by.sort_values("mean"), x="mean", y="b8i5", orientation="h", color="b8i5",
                         title="Avg out-of-pocket medical cost — 8 most frequent ailments (Rs.)")
            fig.update_layout(yaxis_title="", xaxis_title="Rs. per treated spell", showlegend=False)
            show(style_bar(fig, horizontal=True, n_categories=len(by), unit="Rs.", decimals=0))
            note("Ailments with fewer than 30 sampled treated spells are left out.")

st.divider()
st.subheader("🌳 Ailment → system of treatment")
tr = da.dropna(subset=["b8i5", "b8i9"]).assign(b8i5=lambda x: x["b8i5"].astype(str))
top10 = weighted_pct(tr, "b8i5", W).head(10)["b8i5"].tolist()
nested_sunburst(tr[tr["b8i5"].isin(top10)], ["b8i5", "b8i9"], W, "10 most frequent ailments and how they were treated",
                kind="treemap", height=520)

st.caption("Source: ailment_spells_full.csv (spells) and nss_health_master_FULL.csv (persons) — weighted.")
