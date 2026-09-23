# 🏥 National Health Pulse India — NSS Health Survey Dashboard (v2)

A 9-page, multi-tab **Streamlit** dashboard built **directly** on the raw NSS
80th Round survey files (Household Social Consumption: Health Survey,
Schedule 25.0). No merge / decode / `to_parquet` pre-processing step is
needed — every page reads its CSV straight from `data/` (files are already
fully decoded, human-readable text values).

It covers **out-of-pocket medical expenses** for both in-patient
(hospitalization) and out-patient (ailment) care, **morbidity prevalence**,
**vaccination coverage**, **antenatal care**, **household profiles**,
**person-level demographics**, **deaths**, and a **record-level search/lookup**
tool — broken down by state, sector (Rural/Urban), gender and age wherever the
underlying file allows it.

## Setup

1. Put these 8 files inside the `data/` folder (same names, next to `app.py`):
   - `nss_health_master_FULL.csv`
   - `household.csv`
   - `person.csv`
   - `hospitalization_cases_full.csv`
   - `ailment_spells_full.csv`
   - `vaccination_full.csv`
   - `antenatal_full.csv`
   - `deaths_full.csv`

   `data/india_states.geojson` is already bundled (used for the state-wise
   choropleth map on the Overview page).

2. Install dependencies:
   ```bash
   pip install streamlit pandas plotly
   ```

3. Run:
   ```bash
   streamlit run app.py
   ```

## Pages

| # | Page | Source file(s) | What it shows |
|---|------|-----------------|----------------|
| 1 | Overview | `nss_health_master_FULL.csv` | National KPIs, state-wise choropleth map, top-level survey summary |
| 2 | Household Profile | `household.csv` | Household demographics, expenditure breakdown, sector/state filters |
| 3 | Person Profile | `person.csv` | Person-level demographics (age, gender, education, etc.) |
| 4 | Hospitalization Deep-dive | `hospitalization_cases_full.csv` | In-patient care, hospitalization rate, out-of-pocket cost |
| 5 | Ailment Deep-dive | `ailment_spells_full.csv` | Out-patient care, morbidity prevalence, treatment cost |
| 6 | Vaccination Deep-dive | `vaccination_full.csv` | Vaccination coverage by state/age/gender |
| 7 | Antenatal Care Deep-dive | `antenatal_full.csv` | Antenatal care indicators |
| 8 | Deaths | `deaths_full.csv` | Mortality records, cause-wise breakdown |
| 9 | Search / Lookup | `nss_health_master_FULL.csv` | Find a specific household/person record by State → District code → Household ID |

Every page has its own sidebar filters (Sector / Gender / Age / State,
whichever columns exist in that file) and every stat is weighted using the
file's survey weight column (`wt` for detail tables, `final_weight` for the
master file).

## Project structure

```
Survey/
├── app.py                    # Home page (Overview KPIs + intro)
├── utils.py                  # Shared helpers: load(), weighted stats, branding, theming
├── .streamlit/config.toml    # Theme config
├── data/                     # Raw NSS survey CSVs + india_states.geojson
└── pages/
    ├── 1_📋_Overview.py
    ├── 2_🏠_Household_Profile.py
    ├── 3_🧑_Person_Profile.py
    ├── 4_🏥_Hospitalization.py
    ├── 5_🤒_Ailment.py
    ├── 6_💉_Vaccination.py
    ├── 7_🤰_Antenatal.py
    ├── 8_⚰️_Deaths.py
    └── 9_🔎_Search.py
```

## Notes
- Household Profile's 5-component expenditure breakdown (`b5i6`–`b5i10`)
  uses best-effort labels — check against the NSS Schedule 25.0 manual if
  you need the exact official item definitions.
- Vaccination/Antenatal state charts show state **codes** (`st`) since those
  two files don't carry a decoded state-name column; cross-reference with
  the Overview page.
- The `load()` helper in `utils.py` auto-drops rows where `state`/`State` is
  coded `99` (not-stated/invalid), since it breaks categorical charts and
  skews state-wise stats.
- Search page requires `state`, `district_code`, and `household_id` columns
  in the master file; it will show a "no data" message if these are missing.

## Tech stack
- [Streamlit](https://streamlit.io/) — UI framework
- [Pandas](https://pandas.pydata.org/) — data loading & aggregation
- [Plotly](https://plotly.com/python/) — interactive charts & choropleth map

## Data source
[NSS 80th Round — Household Social Consumption: Health, Schedule 25.0](https://mospi.gov.in/), Ministry of Statistics and Programme Implementation, Government of India.

## License
Add a license of your choice (e.g. MIT) here.
