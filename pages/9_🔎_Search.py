import pandas as pd
import streamlit as st

from utils import branding, page_header, require, note

st.set_page_config(page_title="Search — National Health Pulse India", layout="wide", page_icon="🔎")
branding()

MCOLS = ["state", "sector", "district_code", "household_id", "person_serial_no", "Relation to head", "Gender",
         "Age(in years)", "Marital status", "Whether hospitalised", "Whether received any vaccine", "Whether pregnant",
         "household_size", "household_monthly_consumer_expenditure_rs", "final_weight", "fsu_id", "sample_household_no"]
df = require("nss_health_master_FULL.csv", MCOLS)

page_header("🔎", "Search / Lookup",
            "Look up one sampled household: its members and every health event recorded for it",
            crumb="Dashboard / Search")
st.caption("Household ID is a unique identifier across the whole file. Pick State → District code → Household ID.")

c1, c2, c3 = st.columns(3)
with c1:
    states = sorted(df["state"].dropna().astype(str).unique().tolist())
    state_pick = st.selectbox("State", states, key="search_state")
in_state = df[df["state"].astype(str) == state_pick]
with c2:
    dist_opts = sorted(in_state["district_code"].dropna().unique().tolist())
    dist_pick = st.selectbox("District code", dist_opts, key="search_district")
in_dist = in_state[in_state["district_code"] == dist_pick]
with c3:
    hh_opts = sorted(in_dist["household_id"].dropna().unique().tolist())
    hh_pick = st.selectbox("Household ID", hh_opts, key="search_hhid") if hh_opts else None

st.divider()
if hh_pick is None:
    st.info("No households found for this state / district combination.")
    st.stop()

members = in_dist[in_dist["household_id"] == hh_pick].sort_values("person_serial_no")
first = members.iloc[0]
st.subheader(f"🏠 Household {int(hh_pick)} — {state_pick}, district {dist_pick} ({first['sector']})")

# Household-level event counts come from the event tables themselves, so they cover ALL members
# (including members who died during the year, who are not in the member roster).
ev = {
    "hosp": require("hospitalization_cases_full.csv", ["hhid", "b6i1", "b6i2", "b6i3", "b6i5", "b6i7", "b6i12", "exp_oop_hosp_medical", "childbirth"]),
    "ail": require("ailment_spells_full.csv", ["hhid", "b8i1", "b8i2", "b8i3", "b8i5", "b8i9", "exp_oop_spell_medical"]),
    "vac": require("vaccination_full.csv", ["hhid", "b10i1", "b10i2", "b10i3", "b10i4", "b10i5"]),
    "ante": require("antenatal_full.csv", ["hhid", "b11c1", "b11c2", "b11c7", "b11c8"]),
    "dth": require("deaths_full.csv", ["hhid", "b4c1", "b4c3", "b4c4", "b4c5", "b4c6"]),
}
mine = {k: v[pd.to_numeric(v["hhid"], errors="coerce") == hh_pick] for k, v in ev.items()}

k1, k2, k3 = st.columns(3)
k1.metric("👪 Household size", f"{first['household_size']:.0f}")
exp = pd.to_numeric(first["household_monthly_consumer_expenditure_rs"], errors="coerce")
k2.metric("💰 Monthly HH expenditure", f"Rs. {exp:,.0f}" if pd.notna(exp) else "N/A")
k3.metric("⚖️ Survey weight", f"{first['final_weight']:,.2f}")
k4, k5, k6, k7, k8 = st.columns(5)
k4.metric("🏥 Hospitalization cases", len(mine["hosp"]))
k5.metric("🤒 Ailment spells (15 days)", len(mine["ail"]))
k6.metric("💉 Vaccination records", len(mine["vac"]))
k7.metric("🤰 Pregnancy records", len(mine["ante"]))
k8.metric("⚰️ Deaths in last year", len(mine["dth"]))
note("Counts include every member the survey recorded for this household, including members who died during the year.")

st.markdown("##### 👤 Members of this household")
member_cols = [c for c in ["person_serial_no", "Relation to head", "Gender", "Age(in years)", "Marital status",
                           "Whether hospitalised", "Whether received any vaccine", "Whether pregnant"] if c in members.columns]
mem = members[member_cols].reset_index(drop=True).copy()
# per-member counts, aggregated over ALL events of that member (not just the first row)
def per_member(tbl, col, name):
    if tbl.empty:
        return pd.Series(0, index=mem["person_serial_no"], name=name)
    return tbl.groupby(col).size().reindex(mem["person_serial_no"]).fillna(0).astype(int).rename(name)
mem["Hospital cases"] = per_member(mine["hosp"], "b6i2", "n").values
mem["Ailment spells"] = per_member(mine["ail"], "b8i2", "n").values
mem["Vaccine records"] = per_member(mine["vac"], "b10i2", "n").values
st.dataframe(mem, width="stretch", hide_index=True)

for title, key, cols, ren in [
    ("🏥 Hospitalization cases", "hosp", ["b6i1", "b6i2", "b6i3", "b6i5", "b6i7", "b6i12", "exp_oop_hosp_medical"],
     {"b6i1": "Case", "b6i2": "Member", "b6i3": "Age", "b6i5": "Nature of ailment", "b6i7": "Institution",
      "b6i12": "Days", "exp_oop_hosp_medical": "OOP medical (Rs.)"}),
    ("🤒 Ailment spells", "ail", ["b8i1", "b8i2", "b8i3", "b8i5", "b8i9", "exp_oop_spell_medical"],
     {"b8i1": "Spell", "b8i2": "Member", "b8i3": "Age", "b8i5": "Nature of ailment", "b8i9": "Treatment",
      "exp_oop_spell_medical": "OOP medical (Rs.)"}),
    ("💉 Vaccination records", "vac", ["b10i1", "b10i2", "b10i3", "b10i4", "b10i5"],
     {"b10i1": "Record", "b10i2": "Member", "b10i3": "Age", "b10i4": "Vaccine", "b10i5": "Source"}),
    ("🤰 Pregnancy records", "ante", ["b11c1", "b11c2", "b11c7", "b11c8"],
     {"b11c1": "Member", "b11c2": "Age", "b11c7": "Outcome", "b11c8": "Place of delivery"}),
    ("⚰️ Deaths", "dth", ["b4c1", "b4c3", "b4c4", "b4c5", "b4c6"],
     {"b4c1": "Person no.", "b4c3": "Gender", "b4c4": "Age at death", "b4c5": "Medical attention (1=yes)",
      "b4c6": "Hospitalised (1=yes)"}),
]:
    if len(mine[key]):
        with st.expander(f"{title} ({len(mine[key])})"):
            st.dataframe(mine[key][cols].rename(columns=ren).reset_index(drop=True), width="stretch", hide_index=True)

with st.expander("Sampling identifiers for this household"):
    st.write({"FSU": first.get("fsu_id"), "Sample household no.": first.get("sample_household_no"),
              "State": state_pick, "District code": dist_pick, "Sector": first["sector"]})

st.caption("Source: master file (members) and the event tables (cases) — unweighted record view.")
