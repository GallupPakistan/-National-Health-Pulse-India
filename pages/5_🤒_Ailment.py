import streamlit as st
import pandas as pd
import plotly.express as px
from utils import (branding, page_header, load, has, weighted_mean, weighted_pct,
                    sidebar_filters, apply_filters, style_bar, style_pie, no_data,
                    bar_with_table_toggle, COLOR_GENDER, nested_sunburst)

st.set_page_config(page_title="Ailment Deep-dive — National Health Pulse India", layout="wide", page_icon="🤒")
branding()

df = load("ailment_spells_full.csv")
if df.empty:
    st.error("`ailment_spells_full.csv` not found in the `data/` folder.")
    st.stop()

# b8i5 nature of ailment, b8i9 treatment source (allopathy/other),
# b8i7 duration flag, exp_total_spell / exp_oop_spell_total / exp_medical_spell / exp_oop_spell_medical
filters = sidebar_filters(df, kind="detail")
d = apply_filters(df, filters)
W = "wt"

page_header("🤒", "Ailment Deep-dive",
            "Nature of ailment, treatment source, duration of spell, expenditure per type, age/gender pattern, chronic vs acute",
            crumb="Dashboard / Ailment", badge_label="Spells", badge_value=f"{len(d):,}")

from utils import state_rank_avg, render_insight_callout
_nat, _bs, _bv, _ws, _wv = state_rank_avg(d, "st", "exp_total_spell", W)
render_insight_callout(_nat, _bs, _bv, _ws, _wv, "Avg total expenditure per ailment spell",
                        fmt="{:,.0f}", unit="Rs. ", higher_is_worse=True)

k1, k2, k3, k4 = st.columns(4)
k1.metric("🤒 Ailment spells (weighted)", f"{pd.to_numeric(d[W], errors='coerce').sum():,.0f}" if has(d, W) else "N/A")
k2.metric("💰 Avg total expenditure/spell", f"Rs. {weighted_mean(d, 'exp_total_spell', W):,.0f}" if has(d, "exp_total_spell", W) else "N/A")
k3.metric("💸 Avg OOP expenditure/spell", f"Rs. {weighted_mean(d, 'exp_oop_spell_total', W):,.0f}" if has(d, "exp_oop_spell_total", W) else "N/A")

if has(d, "b8i9"):
    ts = weighted_pct(d, "b8i9", W)
    allo = ts[ts["b8i9"].astype(str).str.lower().str.contains("allo")]
    k4.metric("💊 Allopathy treatment share", f"{allo['pct'].iloc[0]:.1f}%" if not allo.empty else "N/A")
else:
    k4.metric("💊 Allopathy treatment share", "N/A")

st.divider()

st.subheader("🦠 Top-10 ailment breakdown")
if has(d, "b8i5"):
    n = weighted_pct(d, "b8i5", W)
    bar_with_table_toggle(st, n, "b8i5", "pct", "Nature of ailment (top 10)", key="ail_top", top_n=10)
else:
    no_data("Nature of ailment")

st.divider()

c1, c2 = st.columns(2)
with c1:
    st.subheader("💊 Treatment source")
    if has(d, "b8i9"):
        ts = weighted_pct(d, "b8i9", W)
        fig = px.pie(ts, names="b8i9", values="pct", title="Allopathy vs AYUSH", hole=0.45)
        st.plotly_chart(style_pie(fig), use_container_width=True)
    else:
        no_data("Treatment source")
with c2:
    st.subheader("⏳ Duration of ailment spell")
    if has(d, "b8i7"):
        dur = weighted_pct(d, "b8i7", W)
        fig = px.pie(dur, names="b8i7", values="pct", title="When the ailment occurred", hole=0.45)
        st.plotly_chart(style_pie(fig), use_container_width=True)
    else:
        no_data("Duration of spell")

st.divider()

st.subheader("💵 Expenditure per ailment type (top 8 by spell count)")
if has(d, "b8i5", "exp_total_spell"):
    top_ailments = d["b8i5"].value_counts().head(8).index
    sub = d[d["b8i5"].isin(top_ailments)].copy()
    sub[W] = pd.to_numeric(sub[W], errors="coerce")
    sub["exp_total_spell"] = pd.to_numeric(sub["exp_total_spell"], errors="coerce")
    sub["_wsum"] = sub["exp_total_spell"] * sub[W]
    grp = sub.groupby("b8i5").agg(_wsum=("_wsum", "sum"), _wtot=(W, "sum")).reset_index()
    grp["pct"] = grp["_wsum"] / grp["_wtot"]
    exp_by_ail = grp[["b8i5", "pct"]].replace([float("inf"), float("-inf")], pd.NA).dropna().sort_values(
        "pct", ascending=True)
    fig = px.bar(exp_by_ail, x="pct", y="b8i5", orientation="h",
                 title="Avg total expenditure by ailment type (Rs.)", color="b8i5")
    fig.update_layout(yaxis_title="", xaxis_title="Rs.", showlegend=False)
    st.plotly_chart(style_bar(fig, horizontal=True, n_categories=len(exp_by_ail), unit="Rs.", decimals=0), use_container_width=True)
else:
    no_data("Expenditure by ailment type")

st.divider()

st.subheader("👤 Age / gender-wise ailment pattern")
c3, c4 = st.columns(2)
with c3:
    if has(d, "person_b3c4"):
        g = weighted_pct(d, "person_b3c4", W)
        fig = px.pie(g, names="person_b3c4", values="pct", title="Gender split", color="person_b3c4",
                     color_discrete_map=COLOR_GENDER, hole=0.45)
        st.plotly_chart(style_pie(fig), use_container_width=True)
    else:
        no_data("Gender")
with c4:
    if has(d, "person_b3c5"):
        age = d[["person_b3c5", W]].dropna().copy()
        age["person_b3c5"] = pd.to_numeric(age["person_b3c5"], errors="coerce")
        bins = [0, 5, 18, 30, 45, 60, 200]
        labels = ["0-5", "6-18", "19-30", "31-45", "46-60", "60+"]
        age["band"] = pd.cut(age["person_b3c5"], bins=bins, labels=labels, right=True)
        band = age.groupby("band", observed=True)[W].sum().reset_index()
        band["pct"] = (band[W] / band[W].sum() * 100).round(2)
        fig = px.bar(band, x="band", y="pct", title="Age-group distribution", color="band")
        st.plotly_chart(style_bar(fig, n_categories=len(band)), use_container_width=True)
    else:
        no_data("Age")

st.divider()

st.subheader("🔁 Chronic vs acute split")
if has(d, "person_b3c13"):
    cs = d.copy()
    cs["Type"] = cs["person_b3c13"].apply(
        lambda v: "Chronic" if pd.notna(v) and str(v).lower() != "not suffered" else "Acute / other")
    split = weighted_pct(cs, "Type", W)
    fig = px.pie(split, names="Type", values="pct", title="Chronic vs acute ailment spells", hole=0.45)
    st.plotly_chart(style_pie(fig), use_container_width=True)
else:
    no_data("Chronic ailment flag")

st.divider()

# ---------------- NEW: Treemap — a joint number not shown above ----------------
st.subheader("🌳 Ailment type × Treatment source — a joint view not shown above")
drawn = nested_sunburst(d, ["b8i5", "b8i9"], W,
                         "Weighted spells by Ailment type → Treatment source", kind="treemap")
if drawn:
    st.caption("Ailment type and treatment source were each shown separately above (one as a bar, one as a "
               "pie). This treemap shows them together — box size = number of spells — so you can see, for "
               "example, which specific ailments lean more on AYUSH vs. allopathy.")
else:
    no_data("Ailment × Treatment source treemap")

st.caption("Source: ailment_spells_full.csv — weighted using `wt`.")