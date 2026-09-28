import pandas as pd
import plotly.express as px
import streamlit as st

from utils import (branding, page_header, require, weighted_mean, weighted_pct, weighted_share, wsum, group_wmean,
                   sidebar_filters, apply_filters, style_bar, style_pie, show, note, bar_with_table_toggle,
                   rank_callout, correlation_heatmap, group_top_n_other, COLOR_SECTOR)

st.set_page_config(page_title="Household Profile — National Health Pulse India", layout="wide", page_icon="🏠")
branding()

W = "wt"
COLS = ["st", "sec", W, "hhsz", "umce", "b5i2", "b5i3", "b5i4", "b5i5", "b5i6", "b5i7", "b5i8", "b5i9", "b5i10", "b5i11",
        "svc", "b1i16", "b2i9"]
df = require("household.csv", COLS)

filters = sidebar_filters(df, "household")
d = apply_filters(df, filters, "household")
if d.empty:
    st.warning("No records for this combination of filters.")
    st.stop()

# Schedule 25.0 Block 5: A = purchases (monthly), B = home-grown (monthly), C = wages in kind / free collection /
# gifts (monthly), D = clothing & footwear (LAST 365 DAYS), E = durables (LAST 365 DAYS).
# Usual monthly consumer expenditure = A + B + C + (D + E) / 12.  b5i6 = medical insurance premium (365 days).
d = d.assign(d_month=pd.to_numeric(d["b5i10"], errors="coerce") / 12,
             e_month=pd.to_numeric(d["b5i11"], errors="coerce") / 12)

page_header("🏠", "Household Profile",
            "Household type, insurance premium, monthly expenditure components, outbreak flag, survey quality",
            crumb="Dashboard / Household Profile", badge_label="Households sampled", badge_value=f"{len(d):,}")

st_exp = group_wmean(d, "st", "umce", W)
rank_callout(st_exp, "st", "mean", "n", "Average usual monthly consumer expenditure per household",
             weighted_mean(d, "umce", W), unit="Rs. ",
             caution="Household expenditure differs with prices and household composition; it is not a quality ranking.")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("🏠 Households (weighted)", f"{wsum(d, W):,.0f}")
k2.metric("👥 Avg household size", f"{weighted_mean(d, 'hhsz', W):.1f}")
k3.metric("💰 Avg monthly consumer expenditure", f"Rs. {weighted_mean(d, 'umce', W):,.0f}")
out = pd.to_numeric(d["b5i5"], errors="coerce")
k4.metric("⚠️ Community disease outbreak reported", f"{weighted_share(d, out == 1, W, universe=out.notna()):.1f}%",
          help="Households reporting a sudden outbreak of a communicable disease in the community in the last 365 days.")
prem = pd.to_numeric(d["b5i6"], errors="coerce")
k5.metric("🛡️ Households paying a medical insurance premium", f"{weighted_share(d, prem > 0, W, universe=prem.notna()):.1f}%",
          help="Premium paid for household members in the last 365 days (b5i6 > 0).")

st.divider()
st.subheader("🏘️ Household type & sector")
c1, c2 = st.columns(2)
with c1:
    t = d[["sec", "b5i4", W]].dropna().groupby(["sec", "b5i4"], observed=True)[W].sum().reset_index()
    if not t.empty:
        t["pct"] = t[W] / t.groupby("sec", observed=True)[W].transform("sum") * 100
        t["b5i4"] = t["b5i4"].astype(str)
        fig = px.bar(t.sort_values("pct"), x="pct", y="b5i4", color="sec", orientation="h", barmode="group",
                     title="Household type (usual livelihood) — % within sector", color_discrete_map=COLOR_SECTOR)
        fig.update_layout(yaxis_title="", xaxis_title="% of households in the sector", height=520,
                          legend_title="Sector", margin=dict(l=10, r=20))
        show(fig)
        note("Rural and urban households use different code lists (e.g. 'self-employed in agriculture' exists only in rural areas).")
with c2:
    sec = weighted_pct(d, "sec", W)
    show(style_pie(px.pie(sec, names="sec", values="pct", title="Rural vs Urban households", hole=0.45,
                          color="sec", color_discrete_map=COLOR_SECTOR)))

st.divider()
st.subheader("🧾 Household characteristics")
c3, c4 = st.columns(2)
with c3:
    rel = group_top_n_other(weighted_pct(d, "b5i2", W), "b5i2")
    show(style_pie(px.pie(rel, names="b5i2", values="pct", title="Religion of the household", hole=0.45)))
with c4:
    sg = group_top_n_other(weighted_pct(d, "b5i3", W), "b5i3")
    show(style_pie(px.pie(sg, names="b5i3", values="pct", title="Social group", hole=0.45)))

st.divider()
st.subheader("💵 Monthly consumer expenditure — the five components")
comp = {"A · Purchased goods & services": "b5i7", "B · Home-grown produce": "b5i8",
        "C · Wages in kind / free collection / gifts": "b5i9", "D · Clothing & footwear (annual ÷ 12)": "d_month",
        "E · Household durables (annual ÷ 12)": "e_month"}
rows = []
for label, col in comp.items():
    rows.append({"Component": label, "Sector": "All", "Avg monthly value (Rs.)": weighted_mean(d, col, W)})
    for s in ["Rural", "Urban"]:
        ds = d[d["sec"] == s]
        if len(ds):
            rows.append({"Component": label, "Sector": s, "Avg monthly value (Rs.)": weighted_mean(ds, col, W)})
comp_df = pd.DataFrame(rows)
c5, c6 = st.columns([3, 2])
with c5:
    fig = px.bar(comp_df, x="Component", y="Avg monthly value (Rs.)", color="Sector", barmode="group",
                 title="Average monthly value per household, by component",
                 color_discrete_map={"All": "#0B1F3A", **COLOR_SECTOR})
    fig.update_layout(height=470, xaxis_title="", margin=dict(b=140))
    fig.update_xaxes(tickangle=-20)
    show(fig)
with c6:
    tot_components = comp_df[comp_df["Sector"] == "All"]["Avg monthly value (Rs.)"].sum()
    st.metric("Sum of the five components", f"Rs. {tot_components:,.0f}")
    st.metric("Usual monthly consumer expenditure (file)", f"Rs. {weighted_mean(d, 'umce', W):,.0f}")
    note("A + B + C + (D + E)/12 reproduces the usual monthly consumer expenditure. D and E are recorded for the "
         "last 365 days, so they are divided by 12 to be comparable with A-C.")

st.divider()
st.subheader("🛡️ Medical insurance premium (last 365 days)")
c7, c8 = st.columns(2)
payers = d[prem.reindex(d.index) > 0]
with c7:
    prem_rows = []
    for s in ["All", "Rural", "Urban"]:
        ds = d if s == "All" else d[d["sec"] == s]
        if ds.empty:
            continue
        p = pd.to_numeric(ds["b5i6"], errors="coerce")
        prem_rows.append({"Sector": s, "Households paying (%)": weighted_share(ds, p > 0, W, universe=p.notna()),
                          "Avg premium among payers (Rs./year)": weighted_mean(ds[p > 0], "b5i6", W) if (p > 0).any() else float("nan")})
    st.dataframe(pd.DataFrame(prem_rows).round(1), width="stretch", hide_index=True)
with c8:
    if len(payers):
        pp = payers.assign(band=pd.cut(pd.to_numeric(payers["b5i6"], errors="coerce"),
                                       [0, 1000, 5000, 10000, 25000, 1e9],
                                       labels=["≤ 1,000", "1,001-5,000", "5,001-10,000", "10,001-25,000", "> 25,000"]))
        bd = pp.groupby("band", observed=True)[W].sum().reset_index()
        bd["pct"] = bd[W] / bd[W].sum() * 100
        bd["band"] = bd["band"].astype(str)
        fig = px.bar(bd, x="band", y="pct", title="Premium paid per year (households paying)", color="band")
        show(style_bar(fig, n_categories=len(bd)))

st.divider()
st.subheader("📋 Survey response quality")
c9, c10, c11 = st.columns(3)
with c9:
    sv = weighted_pct(d, "svc", W)
    show(style_pie(px.pie(sv, names="svc", values="pct", title="Original vs substitute households", hole=0.45), height=380))
with c10:
    if d["b1i16"].notna().any():
        rq = weighted_pct(d, "b1i16", W)
        bar_with_table_toggle(st, rq, "b1i16", "pct", "Reason for substitution (substituted households only)", key="hh_sub")
with c11:
    q = weighted_pct(d, "b2i9", W)
    bar_with_table_toggle(st, q, "b2i9", "pct", "Informant quality", key="hh_quality")

st.divider()
st.subheader("🗺️ Expenditure by state")
if not st_exp.empty:
    bar_with_table_toggle(st, st_exp.rename(columns={"st": "state"}), "state", "mean",
                          "Avg monthly consumer expenditure by state (Rs.)", key="hh_state", unit="Rs.", decimals=0, top_n=12)

st.divider()
st.subheader("🔗 How household numbers move together (unweighted sample correlation)")
corr_cols = ["hhsz", "umce", "b5i7", "b5i8", "b5i9", "d_month", "e_month", "b5i6"]
labels = {"hhsz": "Household size", "umce": "Monthly expenditure", "b5i7": "Purchases (A)", "b5i8": "Home-grown (B)",
          "b5i9": "Wages in kind/free (C)", "d_month": "Clothing (D/12)", "e_month": "Durables (E/12)",
          "b5i6": "Insurance premium (yr)"}
if correlation_heatmap(d, corr_cols, labels, "Correlation matrix: household size, expenditure components, premium"):
    note("Computed on sampled households without weights; values near +1 move together, near 0 are unrelated.")

st.caption("Source: household.csv — weighted with `wt` (household multiplier / 100).")
