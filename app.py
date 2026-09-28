import streamlit as st

from utils import (branding, page_header, require, data_status, weighted_share, wsum, weighted_mean, has, note)

st.set_page_config(page_title="National Health Pulse India — NSS Health Survey", layout="wide", page_icon="🏥")
branding()

MASTER_COLS = ["state", "final_weight", "household_id", "household_monthly_consumer_expenditure_rs",
               "n_ailment_spells_15d", "Whether covered by any scheme for health financing scheme insurance"]
INS = "Whether covered by any scheme for health financing scheme insurance"

master = None
_ok, _msg = data_status("nss_health_master_FULL.csv")
if _ok:
    master = require("nss_health_master_FULL.csv", MASTER_COLS)

n_states = f"{master['state'].nunique():,}" if master is not None and has(master, "state") else "36"
n_persons = f"{len(master):,}" if master is not None else "6,47,673"

page_header("🏥", "National Health Pulse India",
            "Household Social Consumption: Health Survey — NSS 80th Round, Schedule 25.0",
            crumb="Dashboard / Home", badge_label="States & UTs", badge_value=n_states)

st.markdown("""
This dashboard reads the survey CSV files from the `data/` folder and reports the survey's headline
indicators — **morbidity (PPRA)**, **hospitalization rate**, **out-of-pocket medical expenses** for in-patient and
out-patient care, **antenatal / postnatal care & childbirth**, **vaccination**, **household profiles** and **deaths** —
by state, sector (Rural/Urban), gender and age group. All figures are **weighted** with the survey multiplier and use the
**official NSS definitions**; the *Method & Checks* page recomputes them live against the published report.
""")

if master is None:
    st.warning(_msg + " Live numbers appear here once the data files are in place.")
else:
    hh = master.drop_duplicates("household_id")          # one row per household -> household-weighted stats
    hosp = require("hospitalization_cases_full.csv", ["wt", "childbirth"])
    W = "final_weight"
    k1, k2, k3, k4 = st.columns(4)
    ppra = weighted_share(master, master["n_ailment_spells_15d"] > 0, W)
    k1.metric("🤒 Ailing persons, last 15 days (PPRA)", f"{ppra:.1f}%")
    non_cb = hosp[hosp["childbirth"] == 0]
    k2.metric("🏥 Hospitalization rate (excl. childbirth)", f"{non_cb['wt'].sum() / wsum(master, W) * 100:.1f}%")
    k3.metric("💰 Avg household monthly expenditure",
              f"Rs. {weighted_mean(hh, 'household_monthly_consumer_expenditure_rs', W):,.0f}")
    cov = weighted_share(master, master[INS].astype(str) != "not covered", W, universe=master[INS].notna())
    k4.metric("🛡️ Persons with health insurance / scheme", f"{cov:.1f}%")
    note("Hospitalization rate = hospital admissions (excluding childbirth) in the last 365 days per 100 persons. "
         "Insurance is a single-response question (one scheme per person), so it is not comparable with sources "
         "that count multiple schemes.")

st.divider()
st.subheader("📂 Explore the dashboard")

pages = [
    ("pages/1_📋_Overview.py", "📋", "Overview", "PPRA, hospitalization rate, expenditure, state comparison & maps."),
    ("pages/2_🏠_Household_Profile.py", "🏠", "Household Profile", "Household type, insurance premium, expenditure components, survey quality."),
    ("pages/3_🧑_Person_Profile.py", "🧑", "Person Profile", "Chronic ailment, communicable disease, insurance scheme, education, marital status."),
    ("pages/4_🏥_Hospitalization.py", "🏥", "Hospitalization", "Nature of ailment, hospital type, stay, expenditure, rate by age & gender."),
    ("pages/5_🤒_Ailment.py", "🤒", "Ailment (15-day)", "Prevalence by age/gender, ailment mix, treatment, level of care, out-patient cost."),
    ("pages/6_💉_Vaccination.py", "💉", "Vaccination", "Coverage by age/state, vaccine mix, source, expenditure."),
    ("pages/7_🤰_Antenatal.py", "🤰", "Antenatal & Childbirth", "ANC / PNC coverage, place of delivery, outcomes, expenditure."),
    ("pages/8_⚰️_Deaths.py", "⚰️", "Deaths", "Age & gender of deaths, medical attention, hospitalization before death."),
    ("pages/9_🔎_Search.py", "🔎", "Search / Lookup", "Find one household and see its members and health events."),
    ("pages/10_📘_Method_and_Checks.py", "📘", "Method & Checks", "Definitions, caveats and a live check against the official report."),
]

card_css = """
<style>
.nav-card { background: linear-gradient(135deg, #F0FDFA 0%, #FFFFFF 100%); border: 1px solid #D1FAE5;
    border-left: 5px solid #0F766E; border-radius: 12px; padding: 16px 18px; margin-bottom: 14px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.nav-card .nav-title { font-size: 17px; font-weight: 700; color: #111827; }
.nav-card .nav-desc { font-size: 13px; color: #6B7280; margin-top: 2px; }
</style>
"""
st.markdown(card_css, unsafe_allow_html=True)

cols = st.columns(3)
for i, (path, icon, title, desc) in enumerate(pages):
    with cols[i % 3]:
        st.markdown(f"""<div class="nav-card"><div class="nav-title">{icon} &nbsp;{title}</div>
        <div class="nav-desc">{desc}</div></div>""", unsafe_allow_html=True)
        st.page_link(path, label=f"Open {title}", icon="➡️")

st.divider()

glance_css = """
<style>
.glance-wrap { background: linear-gradient(135deg, #0B1F3A 0%, #132A4D 100%);
    border-radius: 16px; padding: 24px 28px; margin-top: 4px; }
.glance-title { color: #FFFFFF; font-size: 19px; font-weight: 800; margin-bottom: 4px; }
.glance-sub { color: #9CA3AF; font-size: 13px; margin-bottom: 18px; }
.glance-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; }
.glance-chip { background: #ffffff10; border: 1px solid #ffffff22; border-radius: 12px; padding: 14px 16px; }
.glance-chip .g-val { color: #FFFFFF; font-size: 22px; font-weight: 800; }
.glance-chip .g-lbl { color: #9CA3AF; font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.04em; margin-top: 2px; }
</style>
"""
st.markdown(glance_css, unsafe_allow_html=True)
st.markdown(f"""
<div class="glance-wrap">
  <div class="glance-title">📊 Survey at a glance</div>
  <div class="glance-sub">NSS 80th Round · Household Social Consumption: Health (Schedule 25.0) · January–December 2025 · 1,39,732 households.</div>
  <div class="glance-grid">
    <div class="glance-chip"><div class="g-val">{n_states}</div><div class="g-lbl">States &amp; UTs</div></div>
    <div class="glance-chip"><div class="g-val">{n_persons}</div><div class="g-lbl">Persons sampled (unweighted)</div></div>
    <div class="glance-chip"><div class="g-val">8</div><div class="g-lbl">Linked datasets</div></div>
    <div class="glance-chip"><div class="g-val">Rural / Urban</div><div class="g-lbl">Sector split</div></div>
    <div class="glance-chip"><div class="g-val">In &amp; Out-patient</div><div class="g-lbl">Care coverage</div></div>
    <div class="glance-chip"><div class="g-val">Weighted</div><div class="g-lbl">Population estimates</div></div>
  </div>
</div>
""", unsafe_allow_html=True)
st.caption("Data source: NSS 80th Round, Household Social Consumption: Health Survey (Schedule 25.0). "
           "Per the NSS 'Note for data user', demographic / household variables are for classifying health "
           "indicators — they are not meant for independent estimates such as population size or literacy.")
