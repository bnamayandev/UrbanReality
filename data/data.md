# Data Guide — Toronto Construction Impact Analyzer

This document is the single source of truth for every dataset the project needs.
Datasets are split into four buckets: training data, spatial context layers, coefficient lookup tables, and live runtime APIs.

---

## Bucket 1 — Training Data

*Row-by-row historical datasets used to train or calibrate ML models.*

### EWRB — Toronto Energy and Water Reporting & Benchmarking

- **Used by:** Model 1 (Energy / Utility Cost)
- **What it is:** Every Toronto building over 10,000 sq ft must report annual electricity (kWh), gas (m³), and water (m³) consumption plus basic building characteristics (type, floor area, year built, floors, heating type).
- **Why it's ideal:** The dataset is already in exactly the shape you need for regression — features on the left, consumption targets on the right. Multiple years are available so you can also model trends.
- **Where to get it:** Toronto Open Data portal → search "Energy and Water Reporting and Benchmarking". Direct CSV download, free.
- **Feature columns:** `building_type`, `floor_area_sqft`, `year_built`, `num_floors`, `neighbourhood`, `heating_type`
- **Target columns:** `annual_electricity_kwh`, `annual_gas_m3`, `annual_water_m3`

---

### Toronto Building Permits (Cleared)

- **Used by:** Model 2 (Construction Jobs), Model 4 (Property Tax), Model 8 (Community Impact)
- **What it is:** Every building permit issued by the City of Toronto — includes declared construction value, building type, address, square footage, number of storeys.
- **Why it's useful:** Lets you derive cost-per-sqft distributions by building type (needed to estimate construction value from height + footprint in the model). Also the backbone for training the community impact model (neighborhood building stock changes over time).
- **Where to get it:** Toronto Open Data → "Building Permits — Active Permits" and "Building Permits — Cleared Permits". CSV or API, free.
- **Key columns:** `permit_type`, `declared_valuation`, `work_type`, `address`, `no_of_storeys`, `floor_area_m2`, `issued_date`

---

### Toronto Employment Survey

- **Used by:** Model 3 (Operational Jobs)
- **What it is:** City of Toronto surveys every business with location and employee count. You can aggregate to building-level and get jobs-per-sqft by building type.
- **Why it's useful:** Training set for "how many permanent jobs does a 50,000 sqft office building in the Annex produce?"
- **Where to get it:** Toronto Open Data → "Toronto Employment Survey". CSV, free.
- **Key columns:** `address`, `industry`, `employees`, `gfa_sqm` (if available)
- **Fallback:** If this dataset is too coarse, use ITE employment generation rates (Bucket 3) as a lookup table instead of training a model.

---

### Transportation Tomorrow Survey (TTS)

- **Used by:** Model 6 (Traffic Generation)
- **What it is:** Household travel survey covering the Greater Toronto Area. Origin-destination pairs by mode, aggregated to traffic zones with land-use info. Considered the gold standard for GTA travel demand modeling.
- **Why it's useful:** Training data for trip generation rates by building type and transit access.
- **Where to get it:** Data Management Group, University of Toronto (dmg.utoronto.ca). Free for academic/research use — request access.
- **Key columns (zone-level aggregate):** `zone_id`, `building_type_mix`, `residential_units`, `commercial_gfa`, `transit_access_score`, `daily_trips_generated`

---

### Traffic Volumes at Intersections (all modes)

- **Used by:** Model 6 (Traffic), also as Bucket 2 spatial context
- **What it is:** 30+ years of vehicle, pedestrian, and cycling counts at major Toronto intersections.
- **Why it's useful:** Ground-truth for calibrating trip generation predictions. Cross-reference pre/post building construction to measure actual traffic delta.
- **Where to get it:** Toronto Open Data → "Traffic Volumes at Intersections for All Modes". CSV, free.
- **Key columns:** `count_id`, `location`, `latitude`, `longitude`, `year`, `8hr_vehicle_volume`

---

### Air Quality Ontario — Hourly Monitoring Data

- **Used by:** Model 5 (Air Quality)
- **What it is:** Hourly PM2.5 and NO₂ readings from all air quality monitoring stations across Ontario. Multi-decade history available.
- **Why it's useful:** Training target for predicting how land-use changes (more traffic, less canopy) affect local air quality.
- **Where to get it:** Ontario Ministry of Environment → Air Quality Ontario data downloads (airqualityontario.com). Free CSV downloads by year/station.
- **Feature engineering:** Join station readings with surrounding land-use features (traffic volume within 500 m, % tree canopy within 500 m, building density, distance to highway) to build the training feature matrix.

---

### 311 Service Requests (2014–present)

- **Used by:** Model 8 (Community Impact)
- **What it is:** Every 311 complaint/service request filed by Toronto residents, with category, address, and date. Over 10 years of history.
- **Why it's useful:** Proxy for neighbourhood service strain. Train a model: "as building density increases, which complaint categories increase?"
- **Where to get it:** Toronto Open Data → "311 Service Requests". CSV/API, free.
- **Key columns:** `service_request_id`, `type`, `ward`, `neighbourhood`, `opened_date`, `latitude`, `longitude`

---

### MPAC Property Assessment Data

- **Used by:** Model 4 (Property Tax Revenue)
- **What it is:** Municipal Property Assessment Corporation — assessed values for all Ontario properties. Full parcel-level data is licensed, but Toronto Open Data provides aggregated property tax collection statistics.
- **Where to get it:** Toronto Open Data → "Property Tax Collection". For parcel-level, request through MPAC directly or use the publicly available Assessment Roll summaries.
- **Key columns:** `roll_number`, `property_class`, `assessed_value`, `gfa_sqm`, `ward`, `neighbourhood`

---

## Bucket 2 — Spatial Context Layers

*Load once at startup, query at a given lat/lng at demo time.*


| Dataset                                 | Use at Runtime                                        | Source                                                          |
| --------------------------------------- | ----------------------------------------------------- | --------------------------------------------------------------- |
| **Zoning By-law (GeoJSON)**             | Zoning class (e.g., CR 3.0) at pin location           | Toronto Open Data                                               |
| **Property Boundaries (parcels)**       | Lot size and shape at pin                             | Toronto Open Data → "Toronto Parcel Data"                       |
| **Street Tree Inventory**               | Count trees within 500 m of pin; estimate canopy loss | Toronto Open Data → "Street Tree Data"                          |
| **Forest & Land Cover raster**          | % canopy cover in 500 m buffer                        | Toronto Open Data → "Forest & Land Cover"                       |
| **TTC Stops (subway + LRT + bus)**      | Transit access score = distance to nearest stop       | Toronto Open Data → "TTC Ridership" / GTFS                      |
| **Neighbourhood Boundaries + Profiles** | Neighbourhood name, median income, population density | Toronto Open Data → "Neighbourhoods" + "Neighbourhood Profiles" |
| **TRCA Flood Plain**                    | Flag if pin is in flood zone                          | TRCA GIS Open Data                                              |
| **Schools / Childcare / Libraries**     | Amenity count within 1 km                             | Toronto Open Data                                               |
| **Sewer Mains / Water Mains**           | Utility capacity proximity                            | Toronto Open Data → "Sewer Shed"                                |


All spatial layers should be saved as **GeoParquet** files (`data/*.parquet`) after the first download. The backend loads them into memory at startup for sub-10 ms spatial lookups.

---

## Bucket 3 — Coefficient Lookup Tables

*Small CSVs or PDFs — no training needed, just multiply.*

### Statistics Canada Input-Output Multipliers

- **Used by:** Model 2 (Construction Jobs)
- **What it is:** "$1M residential construction in Ontario → X person-years of employment, $Y GDP contribution." Pre-computed by StatsCan economists.
- **How to use:** Look up building type + province → multiply by estimated construction value.
- **Where to get it:** StatsCan → "Supply and Use Tables / Input-Output Multipliers" (free download). Also summarized in CMHC Economic Impact of Homebuilding reports.

### ITE Trip Generation Rates

- **Used by:** Model 6 (Traffic) as fallback
- **What it is:** Land use code → trips/day/unit or trips/day/1000 sqft. Industry standard used by traffic engineers worldwide.
- **How to use:** `daily_trips = ite_rate[building_type] × (sqft / 1000)` adjusted by transit access modifier.
- **Where to get it:** ITE Trip Generation Manual (licensed, but rates for common codes are widely republished). Also in Toronto's own transportation studies.

### Toronto Property Tax Rates (Annual)

- **Used by:** Model 4 (Property Tax Revenue)
- **What it is:** City of Toronto publishes residential, commercial, and industrial tax rates each year (% of assessed value). Small table, static.
- **How to use:** `annual_tax = assessed_value × tax_rate[property_class]`
- **Where to get it:** toronto.ca → "Property Tax Rates and Assessment". Free PDF/HTML, updated annually.

### OEB Electricity & Gas Rates

- **Used by:** Model 1 (Utility Cost in dollars)
- **What it is:** Ontario Energy Board regulated rates for residential and commercial customers. Lets you convert kWh/m³ predictions → CAD cost.
- **How to use:** `utility_cost_cad = predicted_kwh × rate_kwh + predicted_gas_m3 × rate_m3`
- **Where to get it:** oeb.ca → "Electricity Rates" and "Natural Gas Rates". Free PDFs, updated quarterly. Cache locally.

### ASHRAE / NRCan Energy Intensity Benchmarks

- **Used by:** Model 1 as a sanity check / baseline
- **What it is:** Expected kWh/sqft/year by building type (office, residential, retail, etc.). Useful for validating EWRB-trained model predictions.
- **Where to get it:** NRCan Commercial and Institutional Building Energy Use survey (free download).

---

## Bucket 4 — Live APIs (called at demo runtime)


| Purpose                                                 | API                            | Cost                 | Notes                                                         |
| ------------------------------------------------------- | ------------------------------ | -------------------- | ------------------------------------------------------------- |
| **Geocoding** (address → lat/lng)                       | Mapbox Geocoding API           | Free tier sufficient | More reliable than Nominatim for Toronto addresses            |
| **Reverse geocoding** (lat/lng → address/neighbourhood) | Mapbox Geocoding API           | Free tier            | Fires on pin drop                                             |
| **Live air quality baseline**                           | WAQI / AQICN (`api.waqi.info`) | Free with key        | One call per analysis; returns current AQI at nearest station |
| **LLM narrative generation**                            | Ollama (local, llama3.1:8b)    | Free (local GPU)     | Running on Blackwell; no API cost                             |
| **IESO real-time electricity prices**                   | IESO Adequacy API              | Free                 | Optional; only needed for hourly cost modeling                |
| **TTC transit info**                                    | Toronto GTFS static feed       | Free file            | Download once, query locally for transit access score         |


---

## Priority Order for the Hackathon

**Train these 3 models** (clean data, clear dollar outputs, construction companies care most):

1. **Model 1 — Energy/Utility Cost** (EWRB dataset, XGBoost regression, ready in ~2 hours)
2. **Model 6 — Traffic Generation** (TTS + intersection counts, or ITE lookup table as fallback)
3. **Model 4 — Property Tax Revenue** (MPAC assessments + tax rate table, simple regression)

**Use lookup tables for these** (no training needed):

- Construction jobs → StatsCan I-O multipliers × construction value
- Tree/canopy loss → geometric overlay (no model, just PostGIS intersection)
- Air quality → CANUE land-use regression coefficients as a shortcut

**Use rule-based scoring for:**

- Community benefit score (transit proximity + housing type + green space ratio)
- 311 complaint risk (density delta lookup)

---

## File Naming Convention

All processed data is saved to `data/` as GeoParquet:

```
data/
├── building_permits.parquet        # ~50k rows, training backbone
├── neighbourhoods.parquet          # 158 polygons + income/density
├── street_trees.parquet            # ~500k point geometries
├── traffic_volumes.parquet         # ~5k intersection count points
├── ttc_stops.parquet               # ~11k stop locations
├── zoning.parquet                  # polygon layer (large)
├── ewrb_energy.parquet             # energy benchmarking training data
├── employment_survey.parquet       # jobs training data
└── coefficients/
    ├── ite_trip_rates.csv
    ├── statscan_io_multipliers.csv
    └── tax_rates.csv
```

