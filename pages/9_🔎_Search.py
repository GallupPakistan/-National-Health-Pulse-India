import streamlit as st
import pandas as pd
from utils import branding, page_header, load, has, no_data

st.set_page_config(page_title="Search — National Health Pulse India", layout="wide", page_icon="🔎")
branding()

df = load("nss_health_master_FULL.csv")
if df.empty:
    st.error("`nss_health_master_FULL.csv` not found in the `data/` folder.")
    st.stop()

page_header("🔎", "Search / Lookup",
            "Find a specific household or person record by State, District code and Household ID",
            crumb="Dashboard / Search")

st.caption("Household IDs repeat across districts (they're sequential within each state+district), "
           "so pick all three fields below to find the exact household.")

if not has(df, "state", "district_code", "household_id"):
    no_data("Search")
    st.stop()

c1, c2, c3 = st.columns(3)
with c1:
    states = sorted(df["state"].dropna().astype(str).unique().tolist())
    state_pick = st.selectbox("State", states, key="search_state")
with c2:
    dist_opts = sorted(df.loc[df["state"].astype(str) == state_pick, "district_code"].dropna().unique().tolist())
    dist_pick = st.selectbox("District code", dist_opts, key="search_district")
with c3:
    hh_opts = sorted(df.loc[
        (df["state"].astype(str) == state_pick) & (df["district_code"] == dist_pick), "household_id"
    ].dropna().unique().tolist())
    hh_pick = st.selectbox("Household ID", hh_opts, key="search_hhid") if hh_opts else None

st.divider()

if hh_pick is not None:
    match = df[
        (df["state"].astype(str) == state_pick) &
        (df["district_code"] == dist_pick) &
        (df["household_id"] == hh_pick)
    ]
    if match.empty:
        st.warning("No matching record found.")
    else:
        hh_row = match.iloc[0]
        st.subheader(f"🏠 Household {hh_pick} — {state_pick}, district {dist_pick}")

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("👪 Household size", f"{hh_row.get('household_size', 'N/A')}")
        k2.metric("💰 Monthly HH expenditure",
                   f"Rs. {pd.to_numeric(hh_row.get('household_monthly_consumer_expenditure_rs'), errors='coerce'):,.0f}"
                   if pd.notna(hh_row.get('household_monthly_consumer_expenditure_rs')) else "N/A")
        k3.metric("🏥 Hospitalizations", f"{hh_row.get('n_hospitalizations', 'N/A')}")
        k4.metric("💉 Vaccination records", f"{hh_row.get('n_vaccination_records', 'N/A')}")

        st.markdown("##### 👤 Members of this household")
        member_cols = [c for c in ["person_serial_no", "Relation to head", "Gender", "Age(in years)",
                                    "Marital status", "Whether hospitalised", "Whether received any vaccine",
                                    "Whether pregnant"] if c in match.columns]
        st.dataframe(match[member_cols].reset_index(drop=True), use_container_width=True)

        with st.expander("See all fields for this household (first member row)"):
            st.dataframe(hh_row.to_frame(name="Value"), use_container_width=True)
else:
    st.info("No households found for this state/district combination.")

st.caption("Source: nss_health_master_FULL.csv")
