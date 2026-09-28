import pandas as pd
import streamlit as st

from utils import branding, page_header, require, weighted_mean, weighted_share, wsum, age_band, note

st.set_page_config(page_title="Method & Checks — National Health Pulse India", layout="wide", page_icon="📘")
branding()
page_header("📘", "Method & Checks",
            "Definitions, data handling, and a live check of this dashboard against the published NSS Report No. 596",
            crumb="Dashboard / Method & Checks")

W = "final_weight"
m = require("nss_health_master_FULL.csv", ["sector", "Gender", "Age(in years)", W, "n_ailment_spells_15d"])
h = require("hospitalization_cases_full.csv", ["sec", "wt", "childbirth", "exp_oop_hosp_medical"])
a = require("ailment_spells_full.csv", ["wt", "b8i10", "b8i11", "exp_oop_spell_medical"])
an = require("antenatal_full.csv", ["sec", "wt", "b11c4_code", "b11c7_code", "b11c8_code", "b11c11_code"])

rows = []


def add(name, official, value, tol, unit="%"):
    diff = value - official
    ok = abs(diff) <= tol
    rows.append({"Indicator": name, "Official (Report 596)": official, "This dashboard": round(value, 2),
                 "Difference": round(diff, 2), "Check": "✅ matches" if ok else "⚠️ differs"})


ppra = lambda d: weighted_share(d, d["n_ailment_spells_15d"] > 0, W)
add("PPRA — All India (%)", 13.1, ppra(m), 0.06)
add("PPRA — Rural (%)", 12.2, ppra(m[m["sector"] == "Rural"]), 0.06)
add("PPRA — Urban (%)", 14.9, ppra(m[m["sector"] == "Urban"]), 0.06)
add("PPRA — Male (%)", 11.8, ppra(m[m["Gender"] == "male"]), 0.06)
add("PPRA — Female (%)", 14.4, ppra(m[m["Gender"] == "female"]), 0.06)
band = age_band(m["Age(in years)"]).astype(str)
add("PPRA — age 0-4, persons (%)", 9.9, ppra(m[band == "0-4"]), 0.06)
add("PPRA — age 60+, persons (%)", 43.9, ppra(m[band == "60+"]), 0.06)

hn = h[h["childbirth"] == 0]
for label, off, sec in [("All India", 2.9, None), ("Rural", 2.7, "Rural"), ("Urban", 3.2, "Urban")]:
    num = wsum(hn if sec is None else hn[hn["sec"] == sec], "wt")
    den = wsum(m if sec is None else m[m["sector"] == sec], W)
    add(f"Hospitalization rate, excl. childbirth — {label} (%)", off, num / den * 100, 0.06)
add("Avg out-of-pocket medical expenditure per hospitalization case (Rs.)", 34064,
    weighted_mean(hn, "exp_oop_hosp_medical", "wt"), 100, "Rs.")

b10 = pd.to_numeric(a["b8i10"], errors="coerce")
b11 = pd.to_numeric(a["b8i11"], errors="coerce")
add("Avg out-of-pocket medical expenditure per treated out-patient spell (Rs.)", 861,
    weighted_mean(a[(b10 == 2) & (b11 == 1)], "exp_oop_spell_medical", "wt"), 5, "Rs.")

c7 = pd.to_numeric(an["b11c7_code"], errors="coerce")
c8 = pd.to_numeric(an["b11c8_code"], errors="coerce")
cb = c7.isin([2, 3, 5, 6])
for label, off, sec in [("All India", 96.2, None), ("Rural", 95.6, "Rural"), ("Urban", 97.8, "Urban")]:
    sel = pd.Series(True, index=an.index) if sec is None else (an["sec"].astype(str) == sec)
    add(f"Institutional childbirth — {label} (%)", off,
        weighted_share(an, c8.isin([1, 2, 3]), "wt", universe=cb & c8.notna() & sel), 0.2)

st.subheader("✅ Live reconciliation with the official report")
st.caption("Recomputed from the data files each time this page loads. Official figures are published rounded "
           "(one decimal for rates), so a difference within rounding counts as a match.")
tbl = pd.DataFrame(rows)
st.dataframe(tbl, width="stretch", hide_index=True)
st.caption("Institutional-childbirth figures are within about 0.15 percentage point of the report; the report does not spell "
           "out its exact base of births, so a small residual gap is expected. Rs. figures are treated as matching within "
           "Rs. 100 (in-patient) and Rs. 5 (out-patient).")
n_ok = int((tbl["Check"] == "✅ matches").sum())
if n_ok == len(tbl):
    st.success(f"All {len(tbl)} checked indicators agree with the published report.")
else:
    st.warning(f"{n_ok} of {len(tbl)} indicators agree. Check that the data files in `data/` are the complete v3 set.")

st.divider()
st.subheader("📐 How the main indicators are defined")
st.markdown("""
| Indicator | Definition used here |
|---|---|
| **PPRA** | Persons reporting any ailment (chronic or not) in the last 15 days ÷ persons, weighted. |
| **Hospitalization rate** | Hospital admissions in the last 365 days, **excluding childbirth**, ÷ persons × 100. Includes admissions of members who died during the year. |
| **Out-of-pocket (OOP) medical, in-patient** | Medical expenditure − amount reimbursed (never below 0), per admission excluding childbirth. |
| **Treated out-patient spell** | Ailment spell that was **not** hospitalised and was **treated on medical advice**; OOP medical = medical expenditure − reimbursement. |
| **Antenatal care** | Any source other than "no care was received" (Block 11, col. 4). |
| **Postnatal care** | Among childbirths (live birth or stillbirth), any source other than "no care was received" (col. 11). |
| **Institutional childbirth** | Place of delivery is a government, charitable/NGO or private hospital (col. 8 codes 1-3). |
| **Monthly consumer expenditure** | A + B + C + (D + E) ÷ 12 — clothing and durables are annual figures. |
| **Age groups** | Official NSS groups 0-4, 5-14, 15-29, 30-44, 45-59, 60+. Age 0 (infants) is inside 0-4. |
| **Weights** | `final_weight` (persons) / `wt` (households, cases) = survey multiplier ÷ 100. Household statistics use one row per household. |
""")

st.subheader("🧹 Data handling")
st.markdown("""
- **Complete data.** All 1,39,732 households, 6,51,732 persons and every hospitalization, ailment, vaccination,
  antenatal and death record in the raw files are included. In the released "clean" files, 854 households (mostly urban
  blocks) had a blank *Sample SU No.* in the household file but a value in the other files, so their rows could not be
  linked and were lost; the data here links them on the remaining sampling keys, which are unique.
- **State code 99.** 16 households (46 persons) carry an invalid state code but sit in NSS regions 021/022, which belong
  only to Himachal Pradesh, so they are assigned there (`STATE_RECODE` in `utils.py`).
- **Small samples.** State rankings only include states with at least 100 sample records; estimates below that are unstable.
- **Insurance** is a single-response question (one scheme per person).
- **Classification variables.** Per the NSS *Note for data user*, demographic and household variables are for classifying
  health indicators, not for independent estimates such as population size, sex ratio or literacy.
- **Deaths** are reported events, not a mortality rate; the pregnancy-related timing question has very few sample cases.
- **"No treatment"** (ailment, treatment system code 5) is documented in Schedule 25.0 but missing from the codebook
  workbook, so it is added when the data is built.
- **Maps.** State outlines were made by dissolving a third-party district GeoJSON (`data/india_states.geojson`) and are
  illustrative only — not an authoritative depiction of boundaries.
""")

st.caption("Official values: NSS Report No. 596, Household Social Consumption: Health (80th Round).")
