import streamlit as st
import pandas as pd
import plotly.express as px
from utils import (branding, page_header, load, has, weighted_pct,
                    sidebar_filters, apply_filters, style_bar, style_pie, no_data,
                    bar_with_table_toggle, COLOR_GENDER, nested_sunburst)

st.set_page_config(page_title="Person Profile — National Health Pulse India", layout="wide", page_icon="🧑")
branding()

df = load("person.csv")
if df.empty:
    st.error("`person.csv` not found in the `data/` folder.")
    st.stop()

# person.csv column map:
# b3c3 relation-to-head, b3c4 gender, b3c5 age, b3c6 marital status,
# b3c7 education, b3c13 chronic ailment, b3c17 insurance scheme type
filters = sidebar_filters(df, kind="detail")
d = apply_filters(df, filters)
W = "wt"

page_header("🧑", "Person Profile", "Extra columns beyond the master file — education, marital status, insurance scheme, chronic disease",
            crumb="Dashboard / Person Profile", badge_label="Persons", badge_value=f"{len(d):,}")

if has(d, "st", "b3c13", W):
    from utils import decode_state_code, render_insight_callout
    cd = d[["st", "b3c13", W]].dropna().copy()
    cd["state"] = decode_state_code(cd, "st")
    cd = cd.dropna(subset=["state"])
    cd[W] = pd.to_numeric(cd[W], errors="coerce")
    cd["is_chronic"] = ~cd["b3c13"].astype(str).str.lower().str.contains("not suffered")
    tot = cd.groupby("state")[W].sum()
    chronic_w = cd[cd["is_chronic"]].groupby("state")[W].sum()
    rate = (chronic_w / tot * 100).dropna()
    _nat = (cd.loc[cd["is_chronic"], W].sum() / cd[W].sum() * 100) if cd[W].sum() else None
    if len(rate) > 1:
        _bs, _bv, _ws, _wv = rate.idxmin(), rate.min(), rate.idxmax(), rate.max()
    else:
        _bs = _bv = _ws = _wv = None
    render_insight_callout(_nat, _bs, _bv, _ws, _wv, "Chronic disease prevalence",
                            fmt="{:.1f}", unit="", higher_is_worse=True)

k1, k2, k3, k4 = st.columns(4)
k1.metric("👤 Persons (weighted)", f"{pd.to_numeric(d[W], errors='coerce').sum():,.0f}" if has(d, W) else "N/A")

if has(d, "b3c13"):
    chr_ = weighted_pct(d, "b3c13", W)
    not_suf = chr_[chr_["b3c13"].astype(str).str.lower().str.contains("not suffered")]
    chronic_pct = 100 - (not_suf["pct"].iloc[0] if not not_suf.empty else 0)
    k2.metric("🩺 Chronic disease prevalence", f"{chronic_pct:.1f}%")
else:
    k2.metric("🩺 Chronic disease prevalence", "N/A")

if has(d, "b3c17"):
    ins = weighted_pct(d, "b3c17", W)
    not_cov = ins[ins["b3c17"].astype(str).str.lower() == "not covered"]
    covered_pct = 100 - (not_cov["pct"].iloc[0] if not not_cov.empty else 0)
    k3.metric("🛡️ Insurance coverage", f"{covered_pct:.1f}%")
else:
    k3.metric("🛡️ Insurance coverage", "N/A")

if has(d, "b3c7"):
    edu = weighted_pct(d, "b3c7", W)
    lit = edu[~edu["b3c7"].astype(str).str.lower().str.contains("not literate")]
    k4.metric("📚 Literacy rate", f"{lit['pct'].sum():.1f}%")
else:
    k4.metric("📚 Literacy rate", "N/A")

st.divider()

st.subheader("🎓 Education level breakdown")
if has(d, "b3c7"):
    edu = weighted_pct(d, "b3c7", W)
    bar_with_table_toggle(st, edu, "b3c7", "pct", "Highest educational level attained", key="edu")
else:
    no_data("Education")

st.divider()

st.subheader("💍 Marital status by age-group")
if has(d, "b3c6", "b3c5"):
    m = d[["b3c6", "b3c5", W]].dropna().copy()
    m["b3c5"] = pd.to_numeric(m["b3c5"], errors="coerce")
    m[W] = pd.to_numeric(m[W], errors="coerce")
    bins = [0, 18, 30, 45, 60, 200]
    labels = ["0-18", "19-30", "31-45", "46-60", "60+"]
    m["age_band"] = pd.cut(m["b3c5"], bins=bins, labels=labels, right=True)
    grp = m.groupby(["age_band", "b3c6"], observed=True)[W].sum().reset_index()
    tot = grp.groupby("age_band", observed=True)[W].transform("sum")
    grp["pct"] = (grp[W] / tot * 100).round(1)
    fig = px.bar(grp, x="age_band", y="pct", color="b3c6", barmode="stack",
                 title="Marital status share within each age-group")
    fig.update_layout(height=480, xaxis_title="Age group", yaxis_title="%",
                       legend_title="Marital status")
    st.plotly_chart(fig, use_container_width=True)
else:
    no_data("Marital status / age")

st.divider()

st.subheader("🩺 Chronic disease prevalence")
c1, c2 = st.columns(2)
with c1:
    if has(d, "b3c13"):
        chr_all = weighted_pct(d, "b3c13", W)
        bar_with_table_toggle(st, chr_all, "b3c13", "pct", "Chronic ailment breakdown", key="chronic")
    else:
        no_data("Chronic ailment")
with c2:
    if has(d, "b3c4"):
        g = weighted_pct(d, "b3c4", W)
        fig = px.pie(g, names="b3c4", values="pct", title="Gender split", color="b3c4",
                     color_discrete_map=COLOR_GENDER, hole=0.45)
        st.plotly_chart(style_pie(fig), use_container_width=True)
    else:
        no_data("Gender")

st.divider()

st.subheader("🛡️ Insurance scheme type-wise coverage")
if has(d, "b3c17"):
    ins = weighted_pct(d, "b3c17", W)
    bar_with_table_toggle(st, ins, "b3c17", "pct", "Insurance scheme type", key="ins_scheme")
else:
    no_data("Insurance scheme type")

st.subheader("👪 Relation to head")
if has(d, "b3c3"):
    rel = weighted_pct(d, "b3c3", W)
    bar_with_table_toggle(st, rel, "b3c3", "pct", "Relation to head of household", key="rel_head")
else:
    no_data("Relation to head")

st.divider()

# ---------------- NEW: Sunburst — a joint number not shown above ----------------
st.subheader("🌞 Education × Marital status × Chronic disease — a joint view not shown above")
drawn = nested_sunburst(d, ["b3c7", "b3c6", "b3c13"], W,
                         "Population split by Education → Marital status → Chronic ailment")
if drawn:
    st.caption("Education and marital status were shown earlier only as separate bar charts. Here they're "
               "combined with chronic-disease status into one weighted breakdown — click any ring to drill in "
               "and see, e.g., what share of educated, married persons report a chronic ailment.")
else:
    no_data("Education / Marital status / Chronic ailment sunburst")

st.caption("Source: person.csv — weighted using `wt`.")