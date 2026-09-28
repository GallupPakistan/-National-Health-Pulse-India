import pandas as pd
import plotly.express as px
import streamlit as st

from utils import (branding, page_header, require, weighted_pct, weighted_share, wsum, age_band, sidebar_filters,
                   apply_filters, style_bar, style_pie, show, note, bar_with_table_toggle, rank_callout,
                   nested_sunburst, COLOR_GENDER, AGE_LABELS)

st.set_page_config(page_title="Person Profile — National Health Pulse India", layout="wide", page_icon="🧑")
branding()

W = "wt"
COLS = ["st", "sec", W, "b3c3", "b3c4", "b3c5", "b3c6", "b3c7", "b3c13", "b3c14", "b3c15", "b3c17"]
df = require("person.csv", COLS)

# Schedule 25.0 Block 3:  col 13 = communicable disease (01-12, 19 = not suffered)
#                         col 14 = chronic ailment (1 yes / 2 no)   col 15 = any OTHER ailment, last 15 days
filters = sidebar_filters(df, "person")
d = apply_filters(df, filters, "person")
if d.empty:
    st.warning("No records for this combination of filters.")
    st.stop()

chronic = pd.to_numeric(d["b3c14"], errors="coerce")
other = pd.to_numeric(d["b3c15"], errors="coerce")
known = chronic.notna() | other.notna()
comm = d["b3c13"].astype(str)
d = d.assign(chronic_flag=chronic, chronic_lbl=chronic.map({1.0: "Chronic ailment", 2.0: "No chronic ailment"}))

page_header("🧑", "Person Profile",
            "Chronic ailment, communicable disease, insurance scheme, education, marital status and relation to head",
            crumb="Dashboard / Person Profile", badge_label="Sample persons", badge_value=f"{len(d):,}")

# ---------------- key takeaway ----------------
t = d.dropna(subset=["chronic_flag"]).copy()
t["wc"] = t[W] * (t["chronic_flag"] == 1)
g = t.groupby("st", observed=True).agg(wc=("wc", "sum"), w=(W, "sum"), n=(W, "size")).reset_index()
g["rate"] = g["wc"] / g["w"] * 100
nat_chronic = weighted_share(d, chronic == 1, W, universe=chronic.notna())
rank_callout(g, "st", "rate", "n", "The share of persons with a chronic ailment", nat_chronic, fmt="{:.1f}", suffix="%",
             caution="Prevalence rises steeply with age, so state differences partly reflect age structure.")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("👤 Persons (weighted)", f"{wsum(d, W):,.0f}")
k2.metric("🤒 Ailing persons, 15 days (PPRA)", f"{weighted_share(d, (chronic == 1) | (other == 1), W, universe=known):.1f}%",
          help="Chronic ailment OR any other ailment in the last 15 days. Official: 13.1%.")
k3.metric("🩺 Chronic ailment prevalence", f"{nat_chronic:.1f}%")
k4.metric("🦠 Communicable disease reported", f"{weighted_share(d, comm != 'not suffered', W, universe=d['b3c13'].notna()):.1f}%",
          help="Suffered from malaria, hepatitis, diarrhoea, dengue, TB etc. in the reference period (column 13).")
k5.metric("🛡️ Persons with health insurance / scheme",
          f"{weighted_share(d, d['b3c17'].astype(str) != 'not covered', W, universe=d['b3c17'].notna()):.1f}%",
          help="Single-response question — one scheme per person.")

st.divider()
st.subheader("🩺 Chronic ailment prevalence by age and gender")
tt = t.assign(band=age_band(t["b3c5"]))
gg = tt.groupby(["band", "b3c4"], observed=True).agg(wc=("wc", "sum"), w=(W, "sum")).reset_index()
gg = gg[gg["b3c4"].astype(str).isin(["male", "female"])]
if not gg.empty:
    gg["rate"] = gg["wc"] / gg["w"] * 100
    gg["band"] = gg["band"].astype(str)
    gg["b3c4"] = gg["b3c4"].astype(str)
    fig = px.bar(gg, x="band", y="rate", color="b3c4", barmode="group", color_discrete_map=COLOR_GENDER,
                 category_orders={"band": AGE_LABELS}, title="% of persons with a chronic ailment")
    fig.update_layout(yaxis_title="%", xaxis_title="Age group (years)", legend_title="Gender")
    show(fig)

st.divider()
c1, c2 = st.columns(2)
with c1:
    st.subheader("🦠 Communicable disease (those who suffered)")
    sub = d[(comm != "not suffered") & d["b3c13"].notna()]
    if len(sub):
        bar_with_table_toggle(st, weighted_pct(sub, "b3c13", W), "b3c13", "pct",
                              "Which disease (% of persons who suffered)", key="comm", top_n=8)
    else:
        note("No communicable-disease cases in this selection.")
with c2:
    st.subheader("🚻 Gender")
    show(style_pie(px.pie(weighted_pct(d, "b3c4", W), names="b3c4", values="pct", title="Gender composition", hole=0.45,
                          color="b3c4", color_discrete_map=COLOR_GENDER)))

st.divider()
st.subheader("🛡️ Health insurance / scheme coverage")
c3, c4 = st.columns(2)
ins = weighted_pct(d, "b3c17", W)
with c3:
    bar_with_table_toggle(st, ins, "b3c17", "pct", "Scheme type (all persons)", key="ins_scheme", top_n=10, label_width=40)
with c4:
    cov = d[(d["b3c17"].astype(str) != "not covered") & d["b3c17"].notna()]
    if len(cov):
        bar_with_table_toggle(st, weighted_pct(cov, "b3c17", W), "b3c17", "pct",
                              "Scheme type (among covered persons)", key="ins_covered", top_n=10, label_width=40)
note("Only one scheme is recorded per person (NSS 'Note for data user'), so shares are not comparable with sources "
     "that count multiple enrolments.")

st.divider()
st.subheader("🎓 Education & marital status (composition of the sample)")
note("Shown to classify health indicators — NSS advises against using these variables for literacy or population estimates.")
c5, c6 = st.columns(2)
with c5:
    bar_with_table_toggle(st, weighted_pct(d, "b3c7", W), "b3c7", "pct", "Highest educational level attained",
                          key="edu", top_n=8, label_width=42)
with c6:
    m = d.dropna(subset=["b3c6"]).assign(band=age_band(d["b3c5"]))
    grp = m.groupby(["band", "b3c6"], observed=True)[W].sum().reset_index()
    grp["pct"] = grp[W] / grp.groupby("band", observed=True)[W].transform("sum") * 100
    grp["band"], grp["b3c6"] = grp["band"].astype(str), grp["b3c6"].astype(str)
    fig = px.bar(grp, x="band", y="pct", color="b3c6", barmode="stack", category_orders={"band": AGE_LABELS},
                 title="Marital status within each age group")
    fig.update_layout(height=470, xaxis_title="Age group (years)", yaxis_title="%", legend_title="Marital status")
    show(fig)

st.subheader("👪 Relation to head")
bar_with_table_toggle(st, weighted_pct(d, "b3c3", W), "b3c3", "pct", "Relation to head of household", key="rel_head")

st.divider()
st.subheader("🌞 Education × marital status × chronic ailment (joint view)")
if nested_sunburst(d, ["b3c7", "b3c6", "chronic_lbl"], W, "Population split: Education → Marital status → Chronic ailment"):
    note("Click a ring to drill in, e.g. what share of a given education / marital group reports a chronic ailment.")

st.caption("Source: person.csv — weighted with `wt`.")
