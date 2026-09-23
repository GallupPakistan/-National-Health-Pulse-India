import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from utils import (branding, page_header, load, has, weighted_mean, weighted_pct,
                    sidebar_filters, apply_filters, style_bar, style_pie, no_data,
                    bar_with_table_toggle, COLOR_GENDER, dual_axis_combo, decode_state_code)

st.set_page_config(page_title="Hospitalization — National Health Pulse India", layout="wide", page_icon="🏥")
branding()

df = load("hospitalization_cases_full.csv")
if df.empty:
    st.error("`hospitalization_cases_full.csv` not found in the `data/` folder.")
    st.stop()

# key columns: b6i5 nature of ailment, b6i7 hospital type, b6i9 payment category,
# b6i12 duration of stay (days), childbirth flag,
# exp_total_hosp / exp_oop_hosp_total / exp_medical_hosp / exp_oop_hosp_medical,
# person_b3c4 gender, person_b3c5 age, st/sec via state text not present -> use sec
filters = sidebar_filters(df, kind="detail")
d = apply_filters(df, filters)
W = "wt"

page_header("🏥", "Hospitalization Deep-dive",
            "Nature of ailment, hospital type, duration of stay, expenditure breakdown, childbirth cases, age/gender pattern",
            crumb="Dashboard / Hospitalization", badge_label="Cases", badge_value=f"{len(d):,}")

# ---------------- NEW: Key takeaway + best/worst state ----------------
_national_avg_exp = weighted_mean(d, "exp_total_hosp", W) if has(d, "exp_total_hosp", W) else None

_best_state, _worst_state, _best_val, _worst_val = None, None, None, None
if has(d, "st", "exp_total_hosp", W):
    from utils import decode_state_code
    _sdf = d[["st", "exp_total_hosp", W]].dropna().copy()
    _sdf["state"] = decode_state_code(_sdf, "st")
    _sdf = _sdf.dropna(subset=["state"])
    _sdf[W] = pd.to_numeric(_sdf[W], errors="coerce")
    _sdf["exp_total_hosp"] = pd.to_numeric(_sdf["exp_total_hosp"], errors="coerce")
    _sdf["_wsum"] = _sdf["exp_total_hosp"] * _sdf[W]
    _grp = _sdf.groupby("state").agg(_wsum=("_wsum", "sum"), _wtot=(W, "sum"))
    _grp["avg_exp"] = _grp["_wsum"] / _grp["_wtot"]
    _grp = _grp.replace([float("inf"), float("-inf")], pd.NA).dropna(subset=["avg_exp"])
    if len(_grp) > 1:
        _best_state, _best_val = _grp["avg_exp"].idxmin(), _grp["avg_exp"].min()    # lowest cost = "best"
        _worst_state, _worst_val = _grp["avg_exp"].idxmax(), _grp["avg_exp"].max()  # highest cost = "worst"

if _national_avg_exp is not None:
    takeaway = f"📌 **Key takeaway:** The average hospitalization case costs **Rs. {_national_avg_exp:,.0f}** nationally."
    if _best_state and _worst_state:
        takeaway += (f" **{_worst_state}** has the highest average cost (**Rs. {_worst_val:,.0f}**) — "
                     f"**{_worst_val / _national_avg_exp:.1f}×** the national average — while **{_best_state}** "
                     f"has the lowest (**Rs. {_best_val:,.0f}**).")
    st.info(takeaway)

if _best_state and _worst_state:
    bcol1, bcol2 = st.columns(2)
    bcol1.success(f"🏆 **Lowest avg cost:** {_best_state} — Rs. {_best_val:,.0f}")
    bcol2.error(f"⚠️ **Highest avg cost:** {_worst_state} — Rs. {_worst_val:,.0f}")

k1, k2, k3, k4 = st.columns(4)
k1.metric("🏥 Hospitalization cases (weighted)", f"{pd.to_numeric(d[W], errors='coerce').sum():,.0f}" if has(d, W) else "N/A")
k2.metric("💰 Avg total expenditure", f"Rs. {weighted_mean(d, 'exp_total_hosp', W):,.0f}" if has(d, "exp_total_hosp", W) else "N/A")
k3.metric("💸 Avg out-of-pocket expenditure", f"Rs. {weighted_mean(d, 'exp_oop_hosp_total', W):,.0f}" if has(d, "exp_oop_hosp_total", W) else "N/A")
k4.metric("📆 Avg duration of stay", f"{weighted_mean(d, 'b6i12', W):.1f} days" if has(d, "b6i12", W) else "N/A")

st.divider()

st.subheader("🩺 Nature of ailment (top 10)")
if has(d, "b6i5"):
    n = weighted_pct(d, "b6i5", W)
    bar_with_table_toggle(st, n, "b6i5", "pct", "Nature of ailment leading to hospitalization", key="hosp_ailment", top_n=10)
else:
    no_data("Nature of ailment")

st.divider()

c1, c2 = st.columns(2)
with c1:
    st.subheader("🏨 Type of hospital")
    if has(d, "b6i7"):
        h = weighted_pct(d, "b6i7", W)
        fig = px.pie(h, names="b6i7", values="pct", title="Govt. vs Private vs Charitable", hole=0.45)
        st.plotly_chart(style_pie(fig), use_container_width=True)
    else:
        no_data("Hospital type")
with c2:
    st.subheader("💳 Payment category")
    if has(d, "b6i9"):
        p = weighted_pct(d, "b6i9", W)
        fig = px.pie(p, names="b6i9", values="pct", title="Free / Paying general / Paying special", hole=0.45)
        st.plotly_chart(style_pie(fig), use_container_width=True)
    else:
        no_data("Payment category")

st.divider()

st.subheader("💵 Expenditure breakdown — medical vs non-medical, OOP vs covered")
rows = []
for col, label in [("exp_medical_hosp", "Medical"),
                    ("exp_total_hosp", "Total (medical + non-medical)"),
                    ("exp_oop_hosp_medical", "Out-of-pocket — medical"),
                    ("exp_oop_hosp_total", "Out-of-pocket — total")]:
    if has(d, col, W):
        rows.append({"Component": label, "Avg expenditure (Rs.)": weighted_mean(d, col, W)})
if rows:
    exp_df = pd.DataFrame(rows)
    fig = px.bar(exp_df, x="Component", y="Avg expenditure (Rs.)", color="Component",
                 title="Average expenditure per hospitalization case")
    st.plotly_chart(style_bar(fig, n_categories=len(exp_df), unit="Rs.", decimals=0), use_container_width=True)
    non_medical_share = None
    if has(d, "exp_total_hosp", "exp_medical_hosp"):
        total = weighted_mean(d, "exp_total_hosp", W)
        med = weighted_mean(d, "exp_medical_hosp", W)
        if total:
            non_medical_share = 100 * (total - med) / total
    if non_medical_share is not None:
        st.caption(f"Non-medical costs (transport, lodging, etc.) account for roughly "
                   f"**{non_medical_share:.1f}%** of total hospitalization expenditure on average.")
else:
    no_data("Expenditure breakdown")

st.divider()

st.subheader("👶 Childbirth-related cases")
if has(d, "childbirth"):
    cb = d.copy()
    cb["Childbirth case"] = cb["childbirth"].map({1: "Yes", 0: "No"}).fillna(cb["childbirth"].astype(str))
    cb_pct = weighted_pct(cb, "Childbirth case", W)
    c3, c4 = st.columns(2)
    with c3:
        fig = px.pie(cb_pct, names="Childbirth case", values="pct", title="Share of hospitalizations that are childbirth", hole=0.45)
        st.plotly_chart(style_pie(fig), use_container_width=True)
    with c4:
        if has(d, "exp_total_hosp"):
            ce = cb[["Childbirth case", "exp_total_hosp", W]].copy()
            ce[W] = pd.to_numeric(ce[W], errors="coerce")
            ce["exp_total_hosp"] = pd.to_numeric(ce["exp_total_hosp"], errors="coerce")
            ce["_wsum"] = ce["exp_total_hosp"] * ce[W]
            grp = ce.groupby("Childbirth case").agg(_wsum=("_wsum", "sum"), _wtot=(W, "sum")).reset_index()
            grp["Avg total expenditure (Rs.)"] = grp["_wsum"] / grp["_wtot"]
            cb_exp = grp[["Childbirth case", "Avg total expenditure (Rs.)"]].replace(
                [float("inf"), float("-inf")], pd.NA).dropna()
            fig2 = px.bar(cb_exp, x="Childbirth case", y="Avg total expenditure (Rs.)", color="Childbirth case",
                          title="Avg expenditure: childbirth vs other hospitalizations")
            st.plotly_chart(style_bar(fig2, n_categories=2), use_container_width=True)
else:
    no_data("Childbirth flag")

st.divider()

st.subheader("👤 Age / gender-wise hospitalization pattern")
c5, c6 = st.columns(2)
with c5:
    if has(d, "person_b3c4"):
        g = weighted_pct(d, "person_b3c4", W)
        fig = px.pie(g, names="person_b3c4", values="pct", title="Gender of hospitalized person",
                     color="person_b3c4", color_discrete_map=COLOR_GENDER, hole=0.45)
        st.plotly_chart(style_pie(fig), use_container_width=True)
    else:
        no_data("Gender of hospitalized person")
with c6:
    if has(d, "person_b3c5"):
        age = d[["person_b3c5", W]].dropna().copy()
        age["person_b3c5"] = pd.to_numeric(age["person_b3c5"], errors="coerce")
        bins = [0, 5, 18, 30, 45, 60, 200]
        labels = ["0-5", "6-18", "19-30", "31-45", "46-60", "60+"]
        age["band"] = pd.cut(age["person_b3c5"], bins=bins, labels=labels, right=True)
        band = age.groupby("band", observed=True)[W].sum().reset_index()
        band["pct"] = (band[W] / band[W].sum() * 100).round(2)
        fig = px.bar(band, x="band", y="pct", title="Age-group of hospitalized persons", color="band")
        st.plotly_chart(style_bar(fig, n_categories=len(band)), use_container_width=True)
    else:
        no_data("Age of hospitalized person")

st.divider()

# ---------------- NEW: Volume vs cost per ailment — not shown above ----------------
st.subheader("📊💰 Case volume vs. average cost, per ailment — a combo not shown above")
drawn = dual_axis_combo(d, "b6i5", W, "exp_total_hosp",
                         "Top ailments: hospitalization volume (bars) vs. avg total expenditure (line)",
                         bar_name="Cases (weighted)", line_name="Avg expenditure (Rs.)")
if drawn:
    st.caption("The bar chart earlier showed only *how often* each ailment leads to hospitalization, and the "
                "expenditure chart showed only the *overall* average cost. This links the two per ailment — "
                "note that the most frequent ailments aren't always the most expensive ones.")
else:
    no_data("Volume vs cost combo chart")

st.divider()

# ---------------- NEW: Correlation analysis ----------------
st.subheader("🔬 Correlation — duration of stay vs. total expenditure")
if has(d, "b6i12", "exp_total_hosp"):
    corr_df = d[["b6i12", "exp_total_hosp"]].copy()
    corr_df["b6i12"] = pd.to_numeric(corr_df["b6i12"], errors="coerce")
    corr_df["exp_total_hosp"] = pd.to_numeric(corr_df["exp_total_hosp"], errors="coerce")
    corr_df = corr_df.replace([np.inf, -np.inf], np.nan).dropna()
    # cap extreme outliers just for a readable plot (analysis below still uses full data)
    if len(corr_df) > 5:
        r = corr_df["b6i12"].corr(corr_df["exp_total_hosp"])
        plot_df = corr_df.copy()
        hi = plot_df["exp_total_hosp"].quantile(0.99)
        plot_df = plot_df[plot_df["exp_total_hosp"] <= hi]
        slope, intercept = np.polyfit(plot_df["b6i12"], plot_df["exp_total_hosp"], 1)
        xs = np.linspace(plot_df["b6i12"].min(), plot_df["b6i12"].max(), 50)
        fig = px.scatter(plot_df, x="b6i12", y="exp_total_hosp", opacity=0.35,
                          title="Duration of hospital stay vs. total expenditure",
                          labels={"b6i12": "Duration of stay (days)", "exp_total_hosp": "Total expenditure (Rs.)"})
        fig.add_scatter(x=xs, y=slope * xs + intercept, mode="lines",
                         name="Trend line", line=dict(color="#EF553B", width=3))
        st.plotly_chart(fig, use_container_width=True)
        strength = ("very weak" if abs(r) < 0.2 else "weak" if abs(r) < 0.4 else
                    "moderate" if abs(r) < 0.6 else "strong" if abs(r) < 0.8 else "very strong")
        direction = "positive" if r > 0 else "negative"
        st.caption(f"Correlation coefficient (r) = **{r:.2f}** — a **{strength} {direction}** relationship: "
                   f"longer hospital stays tend to {'cost more' if r > 0 else 'not clearly cost more'}, "
                   f"on average. (Top 1% of expenditure values excluded from the plot for readability, "
                   f"but included in the correlation calculation.)")
    else:
        no_data("Duration vs expenditure correlation")
else:
    no_data("Duration vs expenditure correlation")

st.divider()

# ---------------- NEW: Anomaly highlighting ----------------
st.subheader("🚨 Anomaly highlighting — states with unusually high hospitalization expenditure")
if has(d, "st", "exp_total_hosp", W):
    an = d[["st", "exp_total_hosp", W]].dropna().copy()
    an["state"] = decode_state_code(an, "st")
    an = an.dropna(subset=["state"])
    an[W] = pd.to_numeric(an[W], errors="coerce")
    an["exp_total_hosp"] = pd.to_numeric(an["exp_total_hosp"], errors="coerce")
    an["_wsum"] = an["exp_total_hosp"] * an[W]
    grp = an.groupby("state").agg(_wsum=("_wsum", "sum"), _wtot=(W, "sum")).reset_index()
    grp["avg_exp"] = grp["_wsum"] / grp["_wtot"]
    grp = grp.replace([np.inf, -np.inf], np.nan).dropna(subset=["avg_exp"])
    if len(grp) > 3:
        mean_exp = grp["avg_exp"].mean()
        std_exp = grp["avg_exp"].std()
        grp["z_score"] = (grp["avg_exp"] - mean_exp) / std_exp if std_exp else 0
        grp["Status"] = np.where(grp["z_score"] > 1.5, "⚠️ Unusually high",
                          np.where(grp["z_score"] < -1.5, "🔽 Unusually low", "Normal range"))
        grp = grp.sort_values("avg_exp", ascending=False)
        fig = px.bar(grp, x="state", y="avg_exp", color="Status",
                     color_discrete_map={"⚠️ Unusually high": "#EF553B", "🔽 Unusually low": "#636EFA",
                                          "Normal range": "#B0B0B0"},
                     title="Avg hospitalization expenditure by state — anomalies flagged (>1.5 std dev from mean)")
        fig.add_hline(y=mean_exp, line_dash="dash", line_color="gray",
                       annotation_text=f"National avg: Rs. {mean_exp:,.0f}")
        fig.update_layout(xaxis=dict(tickangle=-45, automargin=True), margin=dict(b=140), height=520,
                           yaxis_title="Avg total expenditure (Rs.)")
        st.plotly_chart(fig, use_container_width=True)
        flagged = grp[grp["Status"] != "Normal range"]
        if not flagged.empty:
            st.caption("Flagged states: " + ", ".join(
                f"**{row['state']}** ({row['Status']})" for _, row in flagged.iterrows()))
        else:
            st.caption("No state deviates more than 1.5 standard deviations from the national average.")
    else:
        no_data("Anomaly highlighting")
else:
    no_data("Anomaly highlighting")

st.caption("Source: hospitalization_cases_full.csv — weighted using `wt`.")