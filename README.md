# NYC Yellow Taxi 2024 — Big Data Analytics with PySpark

**IST3134 Big Data Analytics — Group Assignment (May Semester 2026)**

Analysing **41.2 million** NYC Yellow Taxi trips from 2024 to answer:
**when and where is demand highest, and how does tipping behaviour vary by
time of day and pickup location?**

The same analysis is implemented **twice** — with **Apache Spark (PySpark)**
as the distributed big-data solution and with **Pandas** as a single-machine
baseline — so we can compare the two approaches on speed, memory and
scalability.

---

## Dataset

- **Source:** NYC Taxi & Limousine Commission (TLC) Trip Record Data
  <https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page>
- **Files used:** `yellow_tripdata_2024-01.parquet` … `yellow_tripdata_2024-12.parquet`
  (12 monthly Parquet files, ~660 MB, 41,169,720 rows)
- **Direct download:** `https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-MM.parquet`
  (replace `MM` with `01`–`12`)
- **Zone lookup:** `data/taxi_zone_lookup.csv` (included) maps `LocationID` → borough/zone
  <https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv>

> The Parquet files are **not** committed (too large for GitHub — see `.gitignore`).
> Download them into `data/` before running. A helper is below.

```bash
mkdir -p data && cd data
for m in 01 02 03 04 05 06 07 08 09 10 11 12; do
  curl -O "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-$m.parquet"
done
curl -O "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
```

---

## Project layout

```
.
├── data/                      # Parquet files (download) + taxi_zone_lookup.csv
├── src/
│   ├── spark_analysis.py      # PySpark — the big-data solution
│   ├── pandas_baseline.py     # Pandas — single-machine comparison
│   ├── benchmark.py           # scaling benchmark: Spark vs Pandas
│   └── make_charts.py         # builds the report figures
├── output/                    # CSV results, timings, and figures/
├── report/                    # the assignment report
├── requirements.txt
└── run_all.sh                 # runs the whole pipeline
```

## Setup

```bash
pip install -r requirements.txt
# Spark needs Java 17. With conda:
conda install -c conda-forge openjdk=17
```

## Run

```bash
bash run_all.sh          # everything, or individually:
python src/spark_analysis.py
python src/pandas_baseline.py
python src/benchmark.py
python src/make_charts.py
```

---

## Key results

| Finding | Value |
|---|---|
| Total trips (2024) | 41,169,720 (35.6M after cleaning, 86.5% kept) |
| Peak demand | **6 pm** (2.56M trips); trough at **4–5 am** |
| Busiest zone | **JFK Airport** (1.86M pickups, avg fare **$64**) |
| Highest-revenue borough | **Manhattan** ($757M, 89% of total) |
| Tipping | Highest in the **evening** (~23%); airports tip lowest |

### Spark vs Pandas (scaling benchmark)

| Rows | Pandas time | Pandas peak RAM | Spark time |
|---|---|---|---|
| 2.7M (1 mo) | 0.2 s | 212 MB | 3.4 s |
| 8.5M (3 mo) | 0.4 s | 939 MB | 0.5 s |
| 17.7M (6 mo) | 1.1 s | 1,975 MB | 0.7 s |
| 35.6M (12 mo) | 3.0 s | **3,990 MB** | **1.0 s** |

Pandas is faster on small data but its **memory grows linearly** and would
exceed a 16 GB machine at ~5× this size, while Spark's runtime stays roughly
flat — the core big-data advantage.

## Authors

- *Member 1 — Brandon Pek Sun Yun / 22024525*
- *Member 2 — Bryan Chin Lien Zheng / 22032122*
