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
