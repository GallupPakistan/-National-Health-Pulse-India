import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from utils import (branding, page_header, require, weighted_mean, weighted_pct, wsum, group_wmean, rate_by, age_band,
                   sidebar_filters, apply_filters, style_bar, style_pie, show, note, bar_with_table_toggle,
                   rank_callout, dual_axis_combo, correlation_heatmap, group_top_n_other, MIN_N,
                   COLOR_GENDER, AGE_LABELS)

st.set_page_config(page_title="Hospitalization — National Health Pulse India", layout="wide", page_icon="🏥")
branding()

W = "wt"
HCOLS = ["st", "sec", W, "childbirth", "b6i5", "b6i7", "b6i9", "b6i12", "exp_total_hosp", "exp_oop_hosp_total",
         "exp_medical_hosp", "exp_oop_hosp_medical", "b7i5", "b7i17",
         "b6i8", "b7i6", "b7i7", "b7i8", "b7i9", "b7i10", "b7i11", "b7i13", "b7i14", "b7i18", "b7i20"]
hosp = require("hospitalization_cases_full.csv", HCOLS, events=True)
master = require("nss_health_master_FULL.csv", ["state", "sector", "Gender", "Age(in years)", "final_weight"])

filters = sidebar_filters(hosp, "hosp")
scope = st.sidebar.radio("Cases included", ["Excluding childbirth (official basis)", "Childbirth only", "All cases"],
                         key="hosp_scope")
all_cases = apply_filters(hosp, filters, "hosp")
non_cb = all_cases[all_cases["childbirth"] == 0]
dc = {"Excluding childbirth (official basis)": non_cb,
      "Childbirth only": all_cases[all_cases["childbirth"] == 1], "All cases": all_cases}[scope]
pop = apply_filters(master, filters, "master")          # persons - denominator for rates

page_header("🏥", "Hospitalization",
            "In-patient admissions in the last 365 days: nature of ailment, hospital type, stay, expenditure and rates",
            crumb="Dashboard / Hospitalization", badge_label="Sample cases", badge_value=f"{len(dc):,}")
if dc.empty or pop.empty:
    st.warning("No records for this combination of filters.")
    st.stop()

rate = wsum(non_cb, W) / wsum(pop, "final_weight") * 100
oop_med = weighted_mean(dc, "exp_oop_hosp_medical", W)

# ---------------- key takeaway ----------------
st_cost = group_wmean(dc, "st", "exp_oop_hosp_medical", W)
rank_callout(st_cost, "st", "mean", "n", "The average out-of-pocket medical expenditure per hospitalization case", oop_med,
             unit="Rs. ",
             caution="Costs reflect the mix of hospitals used and the illnesses treated, not only prices; "
                     "states with fewer than the minimum sample are left out of the ranking.")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("🏥 Cases (weighted)", f"{wsum(dc, W):,.0f}", help=f"Scope: {scope}")
k2.metric("📊 Hospitalization rate", f"{rate:.1f}%",
          help="Admissions excluding childbirth per 100 persons in the selected population. Official: 2.9%.")
k3.metric("💊 Avg out-of-pocket medical exp. / case", f"Rs. {oop_med:,.0f}",
          help="Medical expenditure minus reimbursement (floored at 0). Official (excl. childbirth): about Rs. 34,064.")
k4.metric("🧾 Avg total expenditure / case", f"Rs. {weighted_mean(dc, 'exp_total_hosp', W):,.0f}",
          help="Medical + transport + other non-medical, before reimbursement.")
k5.metric("🛏️ Avg length of stay", f"{weighted_mean(dc, 'b6i12', W):.1f} days")

st.divider()
st.subheader("🩺 What people are admitted for")
c1, c2 = st.columns([3, 2])
with c1:
    bar_with_table_toggle(st, weighted_pct(dc, "b6i5", W), "b6i5", "pct", "Nature of ailment (% of cases)",
                          key="h_ailment", top_n=10, label_width=48)
with c2:
    show(style_pie(px.pie(weighted_pct(dc, "b6i7", W), names="b6i7", values="pct",
                          title="Type of medical institution", hole=0.45), height=420))

c3, c4, c5 = st.columns(3)
with c3:
    show(style_pie(px.pie(weighted_pct(dc, "b6i9", W), names="b6i9", values="pct",
                          title="Type of ward", hole=0.45), height=400))
with c4:
    bar_with_table_toggle(st, weighted_pct(dc, "b7i17", W), "b7i17", "pct", "Major source of finance", key="h_fin",
                          top_n=6, label_width=30)
with c5:
    show(style_pie(px.pie(weighted_pct(dc, "b7i5", W), names="b7i5", values="pct",
                          title="Any medical service provided free?", hole=0.45), height=400))

st.divider()
st.subheader("💰 What a hospitalization costs")
c6, c7 = st.columns(2)
with c6:
    means = pd.DataFrame({"Measure": ["Medical expenditure", "Out-of-pocket medical", "Total expenditure",
                                      "Out-of-pocket total"],
                          "Rs.": [weighted_mean(dc, "exp_medical_hosp", W), oop_med,
                                  weighted_mean(dc, "exp_total_hosp", W), weighted_mean(dc, "exp_oop_hosp_total", W)]})
    fig = px.bar(means, x="Measure", y="Rs.", color="Measure", title="Average per case (Rs.)")
    show(style_bar(fig, n_categories=4, unit="Rs.", decimals=0))
    note("Out-of-pocket = expenditure minus the amount reimbursed by insurance / employer (never below 0).")
with c7:
    by_type = group_wmean(dc, "b6i7", "exp_oop_hosp_medical", W)
    if not by_type.empty:
        by_type["b6i7"] = by_type["b6i7"].astype(str)
        fig = px.bar(by_type.sort_values("mean"), x="mean", y="b6i7", orientation="h", color="b6i7",
                     title="Average out-of-pocket medical expenditure by type of institution (Rs.)")
        fig.update_layout(yaxis_title="", xaxis_title="Rs. per case", showlegend=False)
        show(style_bar(fig, horizontal=True, n_categories=len(by_type), unit="Rs.", decimals=0))

cost_band = pd.cut(pd.to_numeric(dc["exp_oop_hosp_medical"], errors="coerce"), [-1, 0, 5000, 20000, 50000, 1e12],
                   labels=["Rs. 0", "1 – 5,000", "5,001 – 20,000", "20,001 – 50,000", "> 50,000"])
cb = dc.assign(cost_band=cost_band).dropna(subset=["cost_band"]).groupby("cost_band", observed=True)[W].sum().reset_index()
cb["pct"] = cb[W] / cb[W].sum() * 100
cb["cost_band"] = cb["cost_band"].astype(str)
fig = px.bar(cb, x="cost_band", y="pct", color="cost_band", title="Cases by out-of-pocket medical expenditure band")
show(style_bar(fig, n_categories=len(cb)))

st.divider()
st.subheader("🧮 Where the money goes — cost components per case")
comp_cols = {"Package component": "b7i6", "Doctor / surgeon fee": "b7i7", "Medicines": "b7i8", "Diagnostic tests": "b7i9",
             "Bed charges": "b7i10", "Other medical (attendant, physio, blood, oxygen…)": "b7i11",
             "Transport for patient": "b7i13", "Other non-medical (food, escort, lodging…)": "b7i14"}
comp_rows = [{"Component": k, "Rs.": weighted_mean(dc, v, W), "Type": "Medical" if v not in ("b7i13", "b7i14") else "Non-medical"}
             for k, v in comp_cols.items()]
comp_df = pd.DataFrame(comp_rows)
cc1, cc2 = st.columns([3, 2])
with cc1:
    fig = px.bar(comp_df.sort_values("Rs."), x="Rs.", y="Component", orientation="h", color="Type",
                 color_discrete_map={"Medical": "#0F766E", "Non-medical": "#F97316"},
                 title="Average expenditure per case by component (Rs., before reimbursement)")
    fig.update_layout(yaxis_title="", xaxis_title="Rs. per case", height=470)
    show(fig)
with cc2:
    st.metric("Sum of the eight components", f"Rs. {comp_df['Rs.'].sum():,.0f}")
    st.metric("Total expenditure per case", f"Rs. {weighted_mean(dc, 'exp_total_hosp', W):,.0f}")
    st.metric("Avg income loss to household per case", f"Rs. {weighted_mean(dc, 'b7i20', W):,.0f}")
    note("Package + doctor + medicines + tests + bed + other medical = medical expenditure; adding transport and other "
         "non-medical gives total expenditure. Cases with no package have a package value of 0. Income loss is "
         "reported separately and is not part of the total.")

st.subheader("🏛️ Why people did not use a government hospital")
priv = dc[dc["b6i8"].notna()]
if len(priv):
    bar_with_table_toggle(st, weighted_pct(priv, "b6i8", W), "b6i8", "pct",
                          "Main reason (% of cases treated in a private or charitable hospital)", key="h_reason", top_n=9, label_width=48)
    note("Asked only when the patient went to a private or charitable hospital. These are reasons reported by the household, "
         "not a measure of hospital quality.")
else:
    note("No private / charitable hospital cases under the current filters.")

st.subheader("📍 Where treatment was received")
pl = dc[dc["b7i18"].notna()]
if len(pl):
    pt = weighted_pct(pl, "b7i18", W)
    show(style_pie(px.pie(pt, names="b7i18", values="pct", title="Place of hospitalisation", hole=0.45), height=420))

st.divider()
st.subheader("👶 Childbirth vs other admissions")
cbrows = []
for lbl, sub in [("Childbirth", all_cases[all_cases["childbirth"] == 1]), ("Other admissions", non_cb)]:
    if len(sub):
        pub = sub["b6i7"].astype(str).str.startswith("govt")
        cbrows.append({"Group": lbl, "Cases (weighted)": round(wsum(sub, W)),
                       "Share in government hospitals (%)": round(wsum(sub[pub], W) / wsum(sub, W) * 100, 1),
                       "Avg out-of-pocket medical (Rs.)": round(weighted_mean(sub, "exp_oop_hosp_medical", W)),
                       "Avg length of stay (days)": round(weighted_mean(sub, "b6i12", W), 1)})
if cbrows:
    st.dataframe(pd.DataFrame(cbrows), width="stretch", hide_index=True)
    note("The official hospitalization rate excludes childbirth; it is shown separately here (ignores the 'Cases included' choice). "
         "Average out-of-pocket medical cost for childbirth computes to about Rs. 15,150 here against Rs. 14,775 in Report 596 "
         "(about 2.6% higher; median 3,000 vs 2,851). The report does not say exactly "
         "which cases it includes, so treat the childbirth cost as approximate.")

st.divider()
st.subheader("👥 Who gets admitted — rate by age group and gender")
nb, db = age_band(non_cb["age_years"]), age_band(pop["Age(in years)"])
rows = []
for gname in ["male", "female"]:
    hm, dm = non_cb["gender"].astype(str) == gname, pop["Gender"].astype(str) == gname
    if hm.any() and dm.any():
        t = rate_by(non_cb[hm], pop[dm], nb[hm], db[dm], W, "final_weight")
        t["Gender"] = gname
        rows.append(t)
if rows:
    rt = pd.concat(rows)
    rt["Age group"] = rt["group"].astype(str)
    fig = px.bar(rt, x="Age group", y="rate", color="Gender", barmode="group", color_discrete_map=COLOR_GENDER,
                 category_orders={"Age group": AGE_LABELS}, title="Admissions (excl. childbirth) per 100 persons")
    fig.update_layout(yaxis_title="%", xaxis_title="Age group (years)")
    show(fig)

st.divider()
st.subheader("📊 Volume vs cost — top ailments")
dual_axis_combo(dc, "b6i5", W, "exp_oop_hosp_medical", "Weighted cases (bars) and average out-of-pocket medical cost (line)",
                "Weighted cases", "Avg OOP medical (Rs.)")

st.divider()
st.subheader("🔗 Stay, cost and reimbursement")
c8, c9 = st.columns(2)
with c8:
    labels = {"b6i12": "Length of stay", "exp_medical_hosp": "Medical exp.", "exp_oop_hosp_medical": "OOP medical",
              "exp_total_hosp": "Total exp.", "exp_oop_hosp_total": "OOP total"}
    correlation_heatmap(dc, list(labels), labels, "Correlation (all sampled cases, unweighted)", height=420)
with c9:
    pts = dc[(pd.to_numeric(dc["exp_oop_hosp_medical"], errors="coerce") > 0) & dc["b6i12"].notna()]
    if len(pts):
        pts = pts.sample(min(4000, len(pts)), random_state=0).assign(b6i7=lambda x: x["b6i7"].astype(str))
        fig = px.scatter(pts, x="b6i12", y="exp_oop_hosp_medical", color="b6i7", log_y=True, opacity=0.5,
                         title="Stay vs out-of-pocket medical cost (random sample of 4,000 cases, log scale)")
        fig.update_layout(xaxis_title="Length of stay (days)", yaxis_title="Rs. (log)", legend_title="Institution")
        show(fig)
note("Correlations and the scatter use unweighted sample cases (the scatter shows a random subsample and only cases with a cost above 0).")

st.divider()
st.subheader("🔍 States that stand out on cost")
sc = st_cost[st_cost["n"] >= MIN_N].copy()
if len(sc) >= 5:
    sc["z"] = (sc["mean"] - sc["mean"].mean()) / sc["mean"].std()
    sc["Flag"] = np.where(sc["z"].abs() > 1.5, "Unusually high / low vs other states", "Within the usual range")
    fig = px.bar(sc.sort_values("mean"), x="mean", y="st", orientation="h", color="Flag", height=max(450, 22 * len(sc)),
                 color_discrete_map={"Unusually high / low vs other states": "#F97316", "Within the usual range": "#0F766E"},
                 title="Average out-of-pocket medical expenditure per case, by state (Rs.)")
    fig.add_vline(x=oop_med, line_dash="dash", line_color="#0B1F3A", annotation_text="National (weighted)")
    fig.update_layout(yaxis_title="", xaxis_title="Rs. per case")
    show(fig)
    note(f"Only states with at least {MIN_N} sample cases are shown. 'Unusual' means more than 1.5 standard deviations "
         "from the average of state averages — a prompt to look closer, not a finding of error or poor performance.")
else:
    note("Not enough states with a sufficient sample under the current filters.")

st.caption("Source: hospitalization_cases_full.csv (cases) and nss_health_master_FULL.csv (persons) — weighted.")
