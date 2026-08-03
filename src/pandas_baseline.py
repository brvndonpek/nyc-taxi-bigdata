"""
NYC Yellow Taxi 2024 -- Single-machine baseline with Pandas
===========================================================
This is the NON-Big-Data comparison for the assignment. It performs the
EXACT same analysis as src/spark_analysis.py, but on one machine with
Pandas instead of a distributed engine.

Purpose of the comparison:
  * Show that the same group-by logic is easy to express in Pandas.
  * Expose where the single-machine approach hurts: it must load the
    data into RAM. To even finish on 41M rows on a 16 GB laptop we are
    forced to (a) read only the columns we need and (b) process the 12
    files one-by-one and combine partial aggregates -- extra engineering
    that Spark handled for us automatically.

Run:  python src/pandas_baseline.py
"""
import time
import glob
import os
import pandas as pd

DATA_DIR = "data"
OUT_DIR = "output"
os.makedirs(OUT_DIR, exist_ok=True)

# Only the columns the analysis needs -- loading all 19 would blow up RAM.
USE_COLS = [
    "tpep_pickup_datetime",
    "trip_distance",
    "PULocationID",
    "payment_type",
    "passenger_count",
    "fare_amount",
    "tip_amount",
    "total_amount",
]


def clean(df):
    """Same filtering rules as the Spark job."""
    df = df[
        (df.fare_amount > 0)
        & (df.trip_distance > 0)
        & (df.trip_distance < 100)
        & (df.total_amount > 0)
        & (df.passenger_count > 0)
        & (df.tpep_pickup_datetime.notna())
        & (df.tpep_pickup_datetime.dt.year == 2024)
    ].copy()
    df["hour"] = df.tpep_pickup_datetime.dt.hour
    df["tip_pct"] = (df.tip_amount / df.fare_amount * 100).where(df.fare_amount > 0, 0.0)
    return df


def main():
    t0 = time.time()
    zones = pd.read_csv(f"{DATA_DIR}/taxi_zone_lookup.csv").rename(
        columns={"LocationID": "PULocationID"}
    )[["PULocationID", "Borough", "Zone"]]

    files = sorted(glob.glob(f"{DATA_DIR}/yellow_tripdata_2024-*.parquet"))

    # We can't safely hold 41M rows + derived columns for a groupby in 16 GB,
    # so we aggregate each month and keep only the small partial results,
    # then combine. (Spark did this transparently.)
    hour_parts, zone_parts, boro_parts, pay_parts = [], [], [], []
    raw_count = clean_count = 0

    for f in files:
        m = pd.read_parquet(f, columns=USE_COLS)
        raw_count += len(m)
        m = clean(m)
        clean_count += len(m)
        m = m.merge(zones, on="PULocationID", how="left")

        # partial sums/counts per key (so we can combine across months)
        hour_parts.append(
            m.groupby("hour").agg(
                trips=("hour", "size"),
                dist_sum=("trip_distance", "sum"),
                fare_sum=("fare_amount", "sum"),
                tip_pct_sum=("tip_pct", "sum"),
            )
        )
        zone_parts.append(
            m.groupby(["Borough", "Zone"]).agg(
                trips=("hour", "size"),
                fare_sum=("fare_amount", "sum"),
                tip_pct_sum=("tip_pct", "sum"),
                total_revenue=("total_amount", "sum"),
            )
        )
        boro_parts.append(
            m.groupby("Borough").agg(
                trips=("hour", "size"),
                total_revenue=("total_amount", "sum"),
                tip_pct_sum=("tip_pct", "sum"),
            )
        )
        pay_parts.append(
            m.groupby("payment_type").agg(
                trips=("hour", "size"),
                tip_pct_sum=("tip_pct", "sum"),
            )
        )
        del m

    # ---- combine partial aggregates into final results -----------------------
    by_hour = pd.concat(hour_parts).groupby(level=0).sum()
    by_hour["avg_distance_mi"] = (by_hour.dist_sum / by_hour.trips).round(2)
    by_hour["avg_fare"] = (by_hour.fare_sum / by_hour.trips).round(2)
    by_hour["avg_tip_pct"] = (by_hour.tip_pct_sum / by_hour.trips).round(2)
    by_hour = by_hour[["trips", "avg_distance_mi", "avg_fare", "avg_tip_pct"]]
    by_hour.reset_index().to_csv(f"{OUT_DIR}/pandas_by_hour.csv", index=False)

    by_zone = pd.concat(zone_parts).groupby(level=[0, 1]).sum()
    by_zone["avg_fare"] = (by_zone.fare_sum / by_zone.trips).round(2)
    by_zone["avg_tip_pct"] = (by_zone.tip_pct_sum / by_zone.trips).round(2)
    by_zone["total_revenue"] = by_zone.total_revenue.round(2)
    by_zone = (by_zone[["trips", "avg_fare", "avg_tip_pct", "total_revenue"]]
               .sort_values("trips", ascending=False).head(15))
    by_zone.reset_index().to_csv(f"{OUT_DIR}/pandas_top_zones.csv", index=False)

    by_boro = pd.concat(boro_parts).groupby(level=0).sum()
    by_boro["avg_tip_pct"] = (by_boro.tip_pct_sum / by_boro.trips).round(2)
    by_boro["total_revenue"] = by_boro.total_revenue.round(2)
    by_boro = (by_boro[["trips", "total_revenue", "avg_tip_pct"]]
               .sort_values("total_revenue", ascending=False))
    by_boro.reset_index().to_csv(f"{OUT_DIR}/pandas_by_borough.csv", index=False)

    by_pay = pd.concat(pay_parts).groupby(level=0).sum()
    by_pay["avg_tip_pct"] = (by_pay.tip_pct_sum / by_pay.trips).round(2)
    by_pay = by_pay[["trips", "avg_tip_pct"]]
    by_pay.reset_index().to_csv(f"{OUT_DIR}/pandas_by_payment.csv", index=False)

    elapsed = time.time() - t0
    print(f"\nRaw trips   : {raw_count:,}")
    print(f"Clean trips : {clean_count:,} "
          f"({100 * clean_count / raw_count:.1f}% kept)\n")
    print("=== PANDAS RESULTS ===")
    print("\n-- Demand by hour of day --")
    print(by_hour.to_string())
    print("\n-- Top 15 busiest pickup zones --")
    print(by_zone.to_string())
    print("\n-- Revenue & tipping by borough --")
    print(by_boro.to_string())

    with open(f"{OUT_DIR}/pandas_timing.txt", "w") as fh:
        fh.write("Engine: Pandas (single machine)\n")
        fh.write(f"Raw trips: {raw_count}\nClean trips: {clean_count}\n")
        fh.write(f"Total runtime: {elapsed:.1f} s\n")
    print(f"\n>>> Pandas total runtime: {elapsed:.1f} s")
    print(f">>> Output written to {OUT_DIR}/pandas_*.csv")


if __name__ == "__main__":
    main()
