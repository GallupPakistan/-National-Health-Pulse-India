import streamlit as st
import pandas as pd
import plotly.express as px
from utils import (branding, page_header, load, has, weighted_mean, weighted_pct,
                    sidebar_filters, apply_filters, style_bar, style_pie, no_data,
                    bar_with_table_toggle, COLOR_SECTOR, COLOR_GENDER, choropleth_state_map)

st.set_page_config(page_title="Overview — National Health Pulse India", layout="wide", page_icon="📋")
branding()

df = load("nss_health_master_FULL.csv")
if df.empty:
    st.error("`nss_health_master_FULL.csv` not found in the `data/` folder.")
    st.stop()

filters = sidebar_filters(df, kind="master")
d = apply_filters(df, filters)
W = "final_weight"

page_header("📋", "Overview", "Summary snapshot — population, ailment rate, hospitalization rate, demographics, state-wise expenditure",
            crumb="Dashboard / Overview", badge_label="Records", badge_value=f"{len(d):,}")

# ---------------- NEW: Key takeaway + best/worst state ----------------
_hosp_rate_national = None
if has(d, "Whether hospitalised"):
    _h = weighted_pct(d, "Whether hospitalised", W)
    _hy = _h[_h.iloc[:, 0].astype(str).str.strip().isin(["1", "1.0", "yes"])]
    _hosp_rate_national = _hy["pct"].iloc[0] if not _hy.empty else None

_best_state, _worst_state, _best_val, _worst_val = None, None, None, None
if has(d, "state", "Whether hospitalised", W):
    _sdf = d[["state", "Whether hospitalised", W]].dropna().copy()
    _sdf[W] = pd.to_numeric(_sdf[W], errors="coerce")
    _tot = _sdf.groupby("state")[W].sum()
    _yes = _sdf[_sdf["Whether hospitalised"].astype(str).str.strip().isin(["1", "1.0", "yes"])].groupby("state")[W].sum()
    _rate = (_yes / _tot * 100).dropna()
    if len(_rate) > 1:
        _best_state, _best_val = _rate.idxmin(), _rate.min()   # lowest hospitalization rate = "best"
        _worst_state, _worst_val = _rate.idxmax(), _rate.max()  # highest = "worst"

if _hosp_rate_national is not None:
    takeaway = f"📌 **Key takeaway:** Nationally, **{_hosp_rate_national:.1f}%** of the surveyed population reported hospitalization."
    if _best_state and _worst_state:
        takeaway += (f" **{_worst_state}** has the highest hospitalization rate (**{_worst_val:.1f}%**), while "
                     f"**{_best_state}** has the lowest (**{_best_val:.1f}%**).")
    st.info(takeaway)

if _best_state and _worst_state:
    bcol1, bcol2 = st.columns(2)
    bcol1.success(f"🏆 **Best (lowest hosp. rate):** {_best_state} — {_best_val:.1f}%")
    bcol2.error(f"⚠️ **Worst (highest hosp. rate):** {_worst_state} — {_worst_val:.1f}%")

# ---------------- KPI row ----------------
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("👤 Population estimate", f"{d[W].sum():,.0f}" if has(d, W) else "N/A")

if has(d, "Whether suffered/suffering from any other ailment: any time during last 15 days"):
    ail = weighted_pct(d, "Whether suffered/suffering from any other ailment: any time during last 15 days", W)
    yes = ail[ail.iloc[:, 0].astype(str).str.strip().isin(["1", "1.0", "yes"])]
    k2.metric("🤒 Ailment rate (15 days)", f"{yes['pct'].iloc[0]:.1f}%" if not yes.empty else "0%")
else:
    k2.metric("🤒 Ailment rate (15 days)", "N/A")

if has(d, "Whether hospitalised"):
    hosp = weighted_pct(d, "Whether hospitalised", W)
    yes = hosp[hosp.iloc[:, 0].astype(str).str.strip().isin(["1", "1.0", "yes"])]
    k3.metric("🏥 Hospitalization rate", f"{yes['pct'].iloc[0]:.1f}%" if not yes.empty else "0%")
else:
    k3.metric("🏥 Hospitalization rate", "N/A")

if has(d, "household_monthly_consumer_expenditure_rs"):
    k4.metric("💰 Avg monthly HH expenditure", f"Rs. {weighted_mean(d, 'household_monthly_consumer_expenditure_rs', W):,.0f}")
else:
    k4.metric("💰 Avg monthly HH expenditure", "N/A")

if has(d, "household_size"):
    k5.metric("🏠 Avg household size", f"{weighted_mean(d, 'household_size', W):.1f}")
else:
    k5.metric("🏠 Avg household size", "N/A")

st.divider()

# ---------------- Demographics ----------------
st.subheader("👥 Demographics")
c1, c2, c3 = st.columns(3)

with c1:
    if has(d, "Gender"):
        g = weighted_pct(d, "Gender", W)
        fig = px.pie(g, names="Gender", values="pct", title="Gender split", hole=0.45,
                     color="Gender", color_discrete_map=COLOR_GENDER)
        st.plotly_chart(style_pie(fig), use_container_width=True)
    else:
        no_data("Gender")

with c2:
    if has(d, "Religion"):
        r = weighted_pct(d, "Religion", W)
        fig = px.pie(r, names="Religion", values="pct", title="Religion", hole=0.45)
        st.plotly_chart(style_pie(fig), use_container_width=True)
    else:
        no_data("Religion")

with c3:
    if has(d, "Social group"):
        sg = weighted_pct(d, "Social group", W)
        fig = px.pie(sg, names="Social group", values="pct", title="Social group", hole=0.45)
        st.plotly_chart(style_pie(fig), use_container_width=True)
    else:
        no_data("Social group")

c4, c5 = st.columns(2)
with c4:
    if has(d, "Age(in years)"):
        age = d[["Age(in years)", W]].dropna().copy()
        age["Age(in years)"] = pd.to_numeric(age["Age(in years)"], errors="coerce")
        bins = [0, 5, 18, 30, 45, 60, 200]
        labels = ["0-5", "6-18", "19-30", "31-45", "46-60", "60+"]
        age["band"] = pd.cut(age["Age(in years)"], bins=bins, labels=labels, right=True)
        band = age.groupby("band", observed=True)[W].sum().reset_index()
        band["pct"] = (band[W] / band[W].sum() * 100).round(2)
        fig = px.bar(band, x="band", y="pct", title="Age-group distribution", color="band")
        st.plotly_chart(style_bar(fig, n_categories=len(band)), use_container_width=True)
    else:
        no_data("Age")

with c5:
    if has(d, "sector"):
        sec = weighted_pct(d, "sector", W)
        fig = px.pie(sec, names="sector", values="pct", title="Rural vs Urban",
                     color="sector", color_discrete_map=COLOR_SECTOR, hole=0.45)
        st.plotly_chart(style_pie(fig), use_container_width=True)
    else:
        no_data("Sector")

st.divider()

# ---------------- NEW: Age trend — hospitalization rate ----------------
st.subheader("📈 Hospitalization rate by age group — trend")
if has(d, "Age(in years)", "Whether hospitalised", W):
    tr = d[["Age(in years)", "Whether hospitalised", W]].dropna().copy()
    tr["Age(in years)"] = pd.to_numeric(tr["Age(in years)"], errors="coerce")
    tr[W] = pd.to_numeric(tr[W], errors="coerce")
    tr = tr.dropna()
    bins = [0, 5, 18, 30, 45, 60, 200]
    labels = ["0-5", "6-18", "19-30", "31-45", "46-60", "60+"]
    tr["band"] = pd.cut(tr["Age(in years)"], bins=bins, labels=labels, right=True, ordered=True)
    tot = tr.groupby("band", observed=True)[W].sum()
    yes = tr[tr["Whether hospitalised"].astype(str).str.strip().isin(["1", "1.0", "yes"])].groupby(
        "band", observed=True)[W].sum()
    rate = (yes / tot * 100).reindex(labels).reset_index()
    rate.columns = ["band", "pct"]
    rate = rate.dropna()
    if not rate.empty:
        fig = px.line(rate, x="band", y="pct", markers=True,
                       title="Hospitalization rate across age groups (weighted)")
        fig.update_traces(line=dict(width=3, color="#EF553B"),
                           marker=dict(size=10, color="#EF553B", line=dict(width=2, color="white")))
        fig.update_layout(xaxis_title="Age group", yaxis_title="Hospitalization rate (%)")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Shows how hospitalization risk changes across the life course — typically higher for "
                   "young children and older adults than for young/middle adults.")
    else:
        no_data("Age trend")
else:
    no_data("Age trend")

st.divider()

# ---------------- State-wise ----------------
st.subheader("🗺️ State-wise comparison")
c6, c7 = st.columns(2)

with c6:
    if has(d, "state", "household_monthly_consumer_expenditure_rs"):
        es = d[["state", "household_monthly_consumer_expenditure_rs", W]].copy()
        es[W] = pd.to_numeric(es[W], errors="coerce")
        es["household_monthly_consumer_expenditure_rs"] = pd.to_numeric(
            es["household_monthly_consumer_expenditure_rs"], errors="coerce")
        es["_wsum"] = es["household_monthly_consumer_expenditure_rs"] * es[W]
        grp = es.groupby("state").agg(_wsum=("_wsum", "sum"), _wtot=(W, "sum")).reset_index()
        grp["avg_expenditure"] = grp["_wsum"] / grp["_wtot"]
        exp_state = grp[["state", "avg_expenditure"]].replace([float("inf"), float("-inf")], pd.NA).dropna()
        bar_with_table_toggle(st, exp_state.rename(columns={"avg_expenditure": "pct"}), "state", "pct",
                               "Avg monthly HH expenditure by state (Rs.)", key="exp_state",
                               unit="Rs.", decimals=0)
    else:
        no_data("State-wise expenditure")

with c7:
    if has(d, "state", "Whether hospitalised"):
        hs = d[["state", "Whether hospitalised", W]].dropna().copy()
        hs[W] = pd.to_numeric(hs[W], errors="coerce")
        tot = hs.groupby("state")[W].sum()
        yes = hs[hs["Whether hospitalised"].astype(str).str.strip().isin(["1", "1.0", "yes"])].groupby("state")[W].sum()
        rate = (yes / tot * 100).reset_index(name="pct").dropna()
        bar_with_table_toggle(st, rate, "state", "pct", "Hospitalization rate by state (%)", key="hosp_state")
    else:
        no_data("State-wise hospitalization")

st.divider()

# ---------------- NEW: State-wise ranked trend ----------------
st.subheader("📈 States ranked — hospitalization rate (highest to lowest)")
if has(d, "state", "Whether hospitalised", W):
    hs2 = d[["state", "Whether hospitalised", W]].dropna().copy()
    hs2[W] = pd.to_numeric(hs2[W], errors="coerce")
    tot2 = hs2.groupby("state")[W].sum()
    yes2 = hs2[hs2["Whether hospitalised"].astype(str).str.strip().isin(["1", "1.0", "yes"])].groupby("state")[W].sum()
    rate2 = (yes2 / tot2 * 100).reset_index(name="pct").dropna().sort_values("pct", ascending=False)
    if not rate2.empty:
        fig = px.line(rate2, x="state", y="pct", markers=True,
                       title="States ranked by hospitalization rate (weighted, %)")
        fig.update_traces(line=dict(width=2, color="#636EFA"),
                           marker=dict(size=8, color="#636EFA", line=dict(width=1, color="white")))
        fig.update_layout(xaxis_title="State (ranked)", yaxis_title="Hospitalization rate (%)",
                           xaxis=dict(tickangle=-45, automargin=True), margin=dict(b=140), height=500)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Same states as the bar chart above, but ordered highest-to-lowest so the gap between "
                   "best- and worst-performing states is easy to read at a glance.")
    else:
        no_data("State-wise ranked trend")
else:
    no_data("State-wise ranked trend")

st.divider()

# ---------------- NEW: Insurance coverage — India map ----------------
st.subheader("🗺️🛡️ Insurance coverage across India — a number not shown anywhere above")
INS_COL = "Whether covered by any scheme for health financing scheme insurance"
if has(d, "state", INS_COL, W):
    ins = d[["state", INS_COL, W]].dropna().copy()
    ins[W] = pd.to_numeric(ins[W], errors="coerce")
    tot = ins.groupby("state")[W].sum()
    covered = ins[~ins[INS_COL].astype(str).str.lower().str.contains("not")].groupby("state")[W].sum()
    cov_pct = (covered / tot * 100).reset_index(name="Insurance coverage %").dropna()
    drawn = choropleth_state_map(cov_pct, "state", "Insurance coverage %",
                                  "Health insurance coverage % by state (weighted)")
    if not drawn:
        no_data("Insurance coverage map")
    st.caption("This is a fresh cut of the data — insurance coverage has only been shown so far as a single "
               "national KPI on the home page; here it's broken out state-by-state on the map for the first time.")
else:
    no_data("Insurance coverage map")

st.divider()

# ---------------- NEW: Drill-down — state to district ----------------
st.subheader("🔎 Drill-down — pick a state to see its district-wise breakdown")
if has(d, "state", "district_code", W):
    dd_states = sorted(d["state"].dropna().astype(str).unique().tolist())
    if dd_states:
        picked_state = st.selectbox("Select a state to drill into", dd_states, key="drilldown_state")
        st.session_state["selected_state"] = picked_state  # shared across the page below (basic cross-filter)
        dsub = d[d["state"].astype(str) == picked_state][["district_code", W]].dropna().copy()
        dsub[W] = pd.to_numeric(dsub[W], errors="coerce")
        dist = dsub.groupby("district_code")[W].sum().reset_index()
        dist.columns = ["District code", "Weighted persons"]
        dist = dist.sort_values("Weighted persons", ascending=False)
        if not dist.empty:
            fig = px.bar(dist, x="District code", y="Weighted persons",
                         title=f"{picked_state} — persons surveyed by district (weighted)",
                         color="Weighted persons", color_continuous_scale="Teal")
            fig.update_layout(xaxis=dict(type="category"))
            st.plotly_chart(fig, use_container_width=True)
            st.caption("District names aren't in this file, only numeric codes — shown as-is. "
                       "Selecting a different state above instantly re-draws this chart.")
        else:
            no_data("District drill-down")
    else:
        no_data("District drill-down")
else:
    no_data("District drill-down")

st.caption("Source: nss_health_master_FULL.csv — weighted using `final_weight`.")