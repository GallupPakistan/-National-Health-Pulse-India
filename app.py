import streamlit as st
from utils import branding, page_header, load, weighted_mean, weighted_pct, has

st.set_page_config(page_title="National Health Pulse India — NSS Health Survey", layout="wide", page_icon="🏥")
branding()
page_header("🏥", "National Health Pulse India",
            "Household Social Consumption: Health Survey — NSS 80th Round, Schedule 25.0",
            crumb="Dashboard / Home", badge_label="States & UTs", badge_value="36")

st.markdown("""
This dashboard is built directly on India's **Household Social Consumption: Health Survey**
(NSS 80th Round) source files — no merge/decode/parquet pre-processing needed, every
page reads its CSV straight from the `data/` folder. It covers **out-of-pocket medical
expenses** for both in-patient (hospitalization) and out-patient (ailment) care,
**morbidity prevalence**, **vaccination coverage**, **antenatal care**, **household
profiles**, **person-level demographics**, and **deaths** — broken down by state,
sector (Rural/Urban), gender and age wherever the underlying file allows it.
""")

n_states_display = "36"
n_persons_display = "6.5L+"

try:
    master = load("nss_health_master_FULL.csv")
    if master.empty:
        raise FileNotFoundError

    if has(master, "state"):
        n_states_display = f"{master['state'].nunique():,}"
    n_persons_display = f"{len(master) / 100000:.1f}L+"  # raw respondents, not weighted population

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("👤 Persons covered (weighted)",
              f"{master['final_weight'].sum():,.0f}" if has(master, "final_weight") else "N/A")

    if has(master, "Whether hospitalised", "final_weight"):
        hosp_rate = weighted_pct(master, "Whether hospitalised", "final_weight")
        yes_row = hosp_rate[hosp_rate["Whether hospitalised"].astype(str).str.strip().isin(["1", "1.0", "yes"])]
        k2.metric("📈 Hospitalization rate", f"{yes_row['pct'].iloc[0]:.1f}%" if not yes_row.empty else "N/A")
    else:
        k2.metric("📈 Hospitalization rate", "N/A")

    if has(master, "household_monthly_consumer_expenditure_rs", "final_weight"):
        avg_mce = weighted_mean(master, "household_monthly_consumer_expenditure_rs", "final_weight")
        k3.metric("💰 Avg household monthly expenditure", f"Rs. {avg_mce:,.0f}")
    else:
        k3.metric("💰 Avg household monthly expenditure", "N/A")

    if has(master, "Whether covered by any scheme for health financing scheme insurance", "final_weight"):
        cov = weighted_pct(master, "Whether covered by any scheme for health financing scheme insurance", "final_weight")
        not_cov = cov[cov.iloc[:, 0].astype(str).str.lower().str.contains("not")]
        covered_pct = 100 - (not_cov["pct"].iloc[0] if not not_cov.empty else 0)
        k4.metric("🛡️ Insurance coverage", f"{covered_pct:.1f}%")
    else:
        k4.metric("🛡️ Insurance coverage", "N/A")
except Exception:
    st.info("Place `nss_health_master_FULL.csv` and the other survey files inside the "
            "`data/` folder next to `app.py` to see live numbers here and on every page.")

st.divider()
st.subheader("📂 Explore the dashboard")

pages = [
    ("pages/1_📋_Overview.py", "📋", "Overview", "Population, ailment & hospitalization snapshot — nss_health_master."),
    ("pages/2_🏠_Household_Profile.py", "🏠", "Household Profile", "Household type, insurance, expenditure breakdown, outbreak flag."),
    ("pages/3_🧑_Person_Profile.py", "🧑", "Person Profile", "Education, marital status, chronic ailments, insurance scheme type."),
    ("pages/4_🏥_Hospitalization.py", "🏥", "Hospitalization Deep-dive", "Nature of ailment, hospital type, stay duration, expenditure."),
    ("pages/5_🤒_Ailment.py", "🤒", "Ailment Deep-dive", "Top ailments, treatment source, duration, chronic vs acute split."),
    ("pages/6_💉_Vaccination.py", "💉", "Vaccination Deep-dive", "Vaccine-type coverage, age-wise completion, state/sector comparison."),
    ("pages/7_🤰_Antenatal.py", "🤰", "Antenatal Care Deep-dive", "ANC visits, source of care, birth outcomes, state/sector coverage."),
    ("pages/8_⚰️_Deaths.py", "⚰️", "Deaths", "Mortality context — age, gender, place & cause."),
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

# ---------------- Survey at a glance ----------------
glance_css = """
<style>
.glance-wrap { background: linear-gradient(135deg, #0B1F3A 0%, #132A4D 100%);
    border-radius: 16px; padding: 24px 28px; margin-top: 4px; }
.glance-title { color: #FFFFFF; font-size: 19px; font-weight: 800; margin-bottom: 4px; }
.glance-sub { color: #9CA3AF; font-size: 13px; margin-bottom: 18px; }
.glance-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; }
.glance-chip { background: #ffffff10; border: 1px solid #ffffff22; border-radius: 12px;
    padding: 14px 16px; }
.glance-chip .g-val { color: #FFFFFF; font-size: 22px; font-weight: 800; }
.glance-chip .g-lbl { color: #9CA3AF; font-size: 11.5px; text-transform: uppercase;
    letter-spacing: 0.04em; margin-top: 2px; }
</style>
"""
st.markdown(glance_css, unsafe_allow_html=True)
st.markdown(f"""
<div class="glance-wrap">
  <div class="glance-title">📊 Survey at a glance</div>
  <div class="glance-sub">NSS 80th Round · Household Social Consumption: Health Survey (Schedule 25.0) — a single cross-sectional round covering India's rural and urban households.</div>
  <div class="glance-grid">
    <div class="glance-chip"><div class="g-val">{n_states_display}</div><div class="g-lbl">States &amp; UTs</div></div>
    <div class="glance-chip"><div class="g-val">{n_persons_display}</div><div class="g-lbl">Persons surveyed</div></div>
    <div class="glance-chip"><div class="g-val">8</div><div class="g-lbl">Linked datasets</div></div>
    <div class="glance-chip"><div class="g-val">Rural / Urban</div><div class="g-lbl">Sector split</div></div>
    <div class="glance-chip"><div class="g-val">In &amp; Out-patient</div><div class="g-lbl">Care coverage</div></div>
    <div class="glance-chip"><div class="g-val">Weighted</div><div class="g-lbl">Population estimates</div></div>
  </div>
</div>
""", unsafe_allow_html=True)
st.caption("Data source: NSS 80th Round, Household Social Consumption: Health Survey (Schedule 25.0).")