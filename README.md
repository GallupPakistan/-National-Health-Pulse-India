# National Health Pulse India (corrected version)

Streamlit dashboard on the NSS 80th Round Household Social Consumption: Health survey (Schedule 25.0).

## Run
1. `pip install -r requirements.txt`
2. Unzip `nss_health_data_v3.zip` and copy the 8 CSV files into `data/`.
3. `streamlit run app.py`

Open the **Method & Checks** page first: it recomputes the headline numbers from your data and compares them with
NSS Report No. 596. If any row shows "differs", the data files are not the complete v3 set.

## Important
- Use the **v3 data files**. Older versions dropped 854 households (4,059 persons, 748 hospital cases, 977 vaccination records).
- GitHub's "Download ZIP" does not include Git-LFS files. If a CSV is a ~130-byte text stub, the app shows an error. Copy the real files or use `git lfs pull`.
- The 8 CSVs total ~880 MB. Each page loads only the columns it needs.

## Definitions (see the Method page for more)
- Hospitalization rate = admissions excluding childbirth per 100 persons (official basis).
- PPRA = persons with any ailment in the last 15 days (chronic or not).
- Monthly expenditure = A + B + C + (D + E)/12.
- Age groups: 0-4, 5-14, 15-29, 30-44, 45-59, 60+ (age 0 is inside 0-4).
- State code 99 (16 households) is assigned to Himachal Pradesh (`STATE_RECODE` in `utils.py`).
- State rankings need at least 100 sample records (`MIN_N` in `utils.py`).
- Map outlines (`data/india_states.geojson`) come from a dissolved third-party district file; illustrative only.

## Known limitations
- Childbirth average out-of-pocket cost is about 2.6% above Report 596 (Rs. ~15,150 vs 14,775); the report's exact case base is not stated.
- Hospitalization rate for age 60+ is 0.1 point above the report's chart (male 9.4 vs 9.3, female 7.0 vs 6.9).
- Rural institutional childbirth is 95.75% vs 95.6% in the report.
- Deaths: the pregnancy-timing question has only 41 sample cases.
- State code 99 (16 households) is assigned to Himachal Pradesh by inference.
- Charts without a published figure in the report (vaccination, deaths, education, household type) are built from the data only.
