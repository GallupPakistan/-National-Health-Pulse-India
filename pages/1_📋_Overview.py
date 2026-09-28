import pandas as pd
import plotly.express as px
import streamlit as st

from utils import (branding, page_header, require, weighted_mean, weighted_pct, weighted_share, wsum, group_wmean,
                   rate_by, age_band, sidebar_filters, apply_filters, style_bar, style_pie, show, note,
                   bar_with_table_toggle, rank_callout, choropleth_state_map, group_top_n_other,
                   COLOR_SECTOR, COLOR_GENDER, AGE_LABELS)

st.set_page_config(page_title="Overview — National Health Pulse India", layout="wide", page_icon="📋")
branding()

INS = "Whether covered by any scheme for health financing scheme insurance"
W = "final_weight"
master = require("nss_health_master_FULL.csv",
                 ["state", "sector", "Gender", "Age(in years)", W, "district_code", "household_id", "Religion",
                  "Social group", "n_ailment_spells_15d", INS])
hosp = require("hospitalization_cases_full.csv", ["st", "sec", "wt", "childbirth"], events=True)
hhs = require("household.csv", ["st", "sec", "wt", "hhsz", "umce"])

filters = sidebar_filters(master, "master")
d = apply_filters(master, filters, "master")                       # persons
hc = apply_filters(hosp, filters, "hosp")                          # hospitalization cases
hcn = hc[hc["childbirth"] == 0]                                    # official basis: excl. childbirth
hh = apply_filters(hhs, filters, "household")                      # households (state / sector filters only)

page_header("📋", "Overview",
            "PPRA, hospitalization rate, household expenditure, demographics and state comparison",
            crumb="Dashboard / Overview", badge_label="Sample persons", badge_value=f"{len(d):,}")

if d.empty:
    st.warning("No records for this combination of filters.")
    st.stop()

ppra = weighted_share(d, d["n_ailment_spells_15d"] > 0, W)
hosp_rate = wsum(hcn, "wt") / wsum(d, W) * 100

# ---------------- Key takeaway (neutral wording) ----------------
st_rate = rate_by(hcn, d, "st", "state", "wt", W)
rank_callout(st_rate, "group", "rate", "n_den", "The hospitalization rate (excluding childbirth)", hosp_rate,
             fmt="{:.1f}", suffix="%",
             caution="A higher rate can mean more illness or better access to care, and a lower rate can mean unmet "
                     "need — so states are shown as highest / lowest, not as better / worse.")

# ---------------- KPI row ----------------
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("👤 Persons (weighted estimate)", f"{wsum(d, W):,.0f}",
          help="Sum of survey weights. NSS advises using this survey for health indicators, not for population totals.")
k2.metric("🤒 Ailing persons, 15 days (PPRA)", f"{ppra:.1f}%",
          help="Persons who reported any ailment (chronic or not) in the last 15 days, as % of persons. Official: 13.1%.")
k3.metric("🏥 Hospitalization rate", f"{hosp_rate:.1f}%",
          help="Hospital admissions in the last 365 days excluding childbirth, per 100 persons. Official: 2.9%.")
k4.metric("💰 Avg household monthly expenditure",
          f"Rs. {weighted_mean(hh, 'umce', 'wt'):,.0f}" if len(hh) else "N/A",
          help="Household-weighted mean of usual monthly consumer expenditure (A+B+C+(D+E)/12). "
               "Uses the household file; ignores gender / age filters.")
k5.metric("🏠 Avg household size", f"{weighted_mean(hh, 'hhsz', 'wt'):.1f}" if len(hh) else "N/A",
          help="Household-weighted (a person-weighted average would overstate it).")

# ---------------- Rural vs Urban ----------------
st.divider()
st.subheader("🏘️ Rural vs Urban — headline indicators")
rows = []
for sec in ["Rural", "Urban"]:
    ds, hs, hcs = d[d["sector"] == sec], hh[hh["sec"] == sec], hcn[hcn["sec"] == sec]
    if ds.empty:
        continue
    rows.append({"Sector": sec,
                 "PPRA (%)": round(weighted_share(ds, ds["n_ailment_spells_15d"] > 0, W), 1),
                 "Hospitalization rate (%)": round(wsum(hcs, "wt") / wsum(ds, W) * 100, 1),
                 "Avg monthly HH expenditure (Rs.)": round(weighted_mean(hs, "umce", "wt")) if len(hs) else None,
                 "Sample persons": len(ds)})
if rows:
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

# ---------------- Demographics ----------------
st.divider()
st.subheader("👥 Who is in the sample")
note("Composition of the surveyed population, used to classify the health indicators. NSS advises against using "
     "these variables for independent estimates (population size, sex ratio, literacy).")
c1, c2, c3 = st.columns(3)
with c1:
    g = weighted_pct(d, "Gender", W)
    show(style_pie(px.pie(g, names="Gender", values="pct", title="Gender", hole=0.45,
                          color="Gender", color_discrete_map=COLOR_GENDER)))
with c2:
    r = group_top_n_other(weighted_pct(d, "Religion", W), "Religion")
    show(style_pie(px.pie(r, names="Religion", values="pct", title="Religion", hole=0.45)))
with c3:
    sg = group_top_n_other(weighted_pct(d, "Social group", W), "Social group")
    show(style_pie(px.pie(sg, names="Social group", values="pct", title="Social group", hole=0.45)))

c4, c5 = st.columns(2)
with c4:
    band = d.assign(band=age_band(d["Age(in years)"])).groupby("band", observed=True)[W].sum().reset_index()
    band["pct"] = band[W] / band[W].sum() * 100
    band["band"] = band["band"].astype(str)
    fig = px.bar(band, x="band", y="pct", title="Age-group distribution (official NSS groups; 0-4 includes infants)",
                 color="band", category_orders={"band": AGE_LABELS})
    show(style_bar(fig, n_categories=len(band)))
with c5:
    sec = weighted_pct(d, "sector", W)
    show(style_pie(px.pie(sec, names="sector", values="pct", title="Rural vs Urban", hole=0.45,
                          color="sector", color_discrete_map=COLOR_SECTOR)))

# ---------------- Hospitalization by age & gender ----------------
st.divider()
st.subheader("📈 Hospitalization rate by age group and gender")
nb, db = age_band(hcn["age_years"]), age_band(d["Age(in years)"])
curves = []
for label, hm, dm in [("Person", pd.Series(True, index=hcn.index), pd.Series(True, index=d.index)),
                      ("Male", hcn["gender"].astype(str) == "male", d["Gender"].astype(str) == "male"),
                      ("Female", hcn["gender"].astype(str) == "female", d["Gender"].astype(str) == "female")]:
    t = rate_by(hcn[hm], d[dm], nb[hm], db[dm], "wt", W)
    t["Series"] = label
    curves.append(t)
curve = pd.concat(curves)
curve["Age group"] = pd.Categorical(curve["group"].astype(str), categories=AGE_LABELS, ordered=True)
curve = curve.sort_values("Age group")
fig = px.line(curve, x="Age group", y="rate", color="Series", markers=True,
              title="Hospital admissions (excl. childbirth) per 100 persons, by age group",
              color_discrete_map={"Person": "#0B1F3A", "Male": "#0F766E", "Female": "#DB2777"})
fig.update_layout(yaxis_title="Hospitalization rate (%)", xaxis_title="Age group (years)")
show(fig)
note("Cases are matched to persons of the same age group and gender; admissions of members who died during the "
     "year are included (their gender comes from the deaths record).")

# ---------------- State-wise ----------------
st.divider()
st.subheader("🗺️ State-wise comparison")
c6, c7 = st.columns(2)
with c6:
    exp_state = group_wmean(hh, "st", "umce", "wt")
    if not exp_state.empty:
        bar_with_table_toggle(st, exp_state.rename(columns={"st": "state"}), "state", "mean",
                              "Avg monthly HH expenditure by state (Rs.)", key="exp_state", unit="Rs.", decimals=0)
with c7:
    if not st_rate.empty:
        bar_with_table_toggle(st, st_rate.rename(columns={"group": "state"}), "state", "rate",
                              "Hospitalization rate by state (%, excl. childbirth)", key="hosp_state")

map_l, map_r = st.columns(2)
with map_l:
    if not st_rate.empty:
        choropleth_state_map(st_rate.rename(columns={"group": "state"}), "state", "rate",
                             "Hospitalization rate (%)", unit="%", height=460)
with map_r:
    ins = d[["state", INS, W]].dropna()
    if not ins.empty:
        tot = ins.groupby("state", observed=True)[W].sum()
        cov = ins[ins[INS].astype(str) != "not covered"].groupby("state", observed=True)[W].sum()
        cov_pct = (cov.reindex(tot.index).fillna(0) / tot * 100).reset_index(name="Insurance coverage %")
        choropleth_state_map(cov_pct, "state", "Insurance coverage %",
                             "Persons covered by any health scheme / insurance (%)", unit="%", height=460)
note("Insurance is a single-response question: a person enrolled in several schemes is recorded under one, so these "
     "shares are not comparable with sources that count multiple schemes.")

# ---------------- State-wise PPRA ----------------
st.divider()
st.subheader("🤒 State-wise PPRA (persons ailing in the last 15 days)")
_p = d.assign(_a=d[W] * (d["n_ailment_spells_15d"] > 0))
ppra_state = _p.groupby("state", observed=True).agg(a=("_a", "sum"), w=(W, "sum"), n=(W, "size")).reset_index()
ppra_state["ppra"] = ppra_state["a"] / ppra_state["w"] * 100
p1, p2 = st.columns(2)
with p1:
    bar_with_table_toggle(st, ppra_state, "state", "ppra", "PPRA by state (%)", key="ppra_state", top_n=12)
with p2:
    choropleth_state_map(ppra_state, "state", "ppra", "PPRA (%)", unit="%", height=460)
note("Report 596, Table 2.2 groups states as: up to 10% (e.g. Bihar, UP, Karnataka), 11-20% (e.g. Maharashtra, Tamil Nadu), "
     "21-25% (West Bengal, Andhra Pradesh) and above 25% (Kerala).")

# ---------------- Sample coverage drill-down ----------------
st.divider()
st.subheader("🔎 Sample coverage — households and persons surveyed by district")
states_avail = sorted(d["state"].dropna().astype(str).unique().tolist())
if states_avail:
    picked = st.selectbox("Select a state", states_avail, key="drilldown_state")
    sub = d[d["state"].astype(str) == picked]
    dist = sub.groupby("district_code", observed=True).agg(Households=("household_id", "nunique"),
                                                           Persons=("household_id", "size")).reset_index()
    dist["district_code"] = dist["district_code"].astype(str)
    fig = px.bar(dist.sort_values("Households", ascending=False), x="district_code", y="Households",
                 title=f"{picked} — households surveyed by district code (unweighted)",
                 color="Households", color_continuous_scale="Teal")
    fig.update_layout(xaxis=dict(type="category"), xaxis_title="District code")
    show(fig)
    note("Unweighted sample sizes. District names are not in the file, and NSS estimates are designed for "
         "State/UT level — district-level rates from these samples would be unreliable.")

st.caption("Source: nss_health_master_FULL.csv (persons), hospitalization_cases_full.csv (cases), household.csv (households) "
           "— weighted with final_weight / wt.")
