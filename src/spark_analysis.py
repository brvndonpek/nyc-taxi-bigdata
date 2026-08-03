"""
NYC Yellow Taxi 2024 -- Big Data Analytics with Apache Spark (PySpark)
=====================================================================
Problem : When and where is NYC taxi demand highest, and how does
          tipping behaviour vary by time of day and pickup location?

Approach: A group-by aggregation (the MapReduce pattern).
          MAP    -> for every trip, emit a key (pickup_zone, hour) with
                    its fare/tip/distance as the value.
          REDUCE -> for every key, aggregate: count trips, sum revenue,
                    average tip %, etc.

Spark executes this as a distributed shuffle: the 41M trips are split
across partitions, mapped in parallel, then reduced per key -- which is
exactly why it scales where a single-machine tool struggles.

Run:  python src/spark_analysis.py
"""
import time
import os
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

DATA_DIR = "data"
OUT_DIR = "output"
os.makedirs(OUT_DIR, exist_ok=True)


def build_spark():
    return (
        SparkSession.builder
        .appName("NYC-Taxi-2024-Analysis")
        # use all local cores; [*] = distribute across every available core
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", "64")
        .config("spark.driver.memory", "6g")
        .getOrCreate()
    )


def main():
    t0 = time.time()
    spark = build_spark()
    spark.sparkContext.setLogLevel("ERROR")

    # ---- READ: Spark reads all 12 Parquet files as one distributed DataFrame ----
    df = spark.read.parquet(f"{DATA_DIR}/yellow_tripdata_2024-*.parquet")
    zones = (
        spark.read.option("header", True)
        .csv(f"{DATA_DIR}/taxi_zone_lookup.csv")
        .select(
            F.col("LocationID").cast("int").alias("PULocationID"),
            F.col("Borough"),
            F.col("Zone"),
        )
    )

    raw_count = df.count()

    # ---- CLEAN: drop invalid / outlier rows so the analysis is trustworthy ----
    clean = df.filter(
        (F.col("fare_amount") > 0)
        & (F.col("trip_distance") > 0)
        & (F.col("trip_distance") < 100)          # >100 miles = data error
        & (F.col("total_amount") > 0)
        & (F.col("passenger_count") > 0)
        & (F.col("tpep_pickup_datetime").isNotNull())
        # keep only trips that actually fall in 2024
        & (F.year("tpep_pickup_datetime") == 2024)
    )

    # derived columns used by the analysis
    clean = (
        clean
        .withColumn("hour", F.hour("tpep_pickup_datetime"))
        .withColumn(
            "trip_minutes",
            (F.unix_timestamp("tpep_dropoff_datetime")
             - F.unix_timestamp("tpep_pickup_datetime")) / 60.0,
        )
        .withColumn(
            "tip_pct",
            F.when(F.col("fare_amount") > 0,
                   F.col("tip_amount") / F.col("fare_amount") * 100)
            .otherwise(0.0),
        )
    )
    clean = clean.join(F.broadcast(zones), on="PULocationID", how="left")
    clean.cache()
    clean_count = clean.count()

    print(f"\nRaw trips   : {raw_count:,}")
    print(f"Clean trips : {clean_count:,} "
          f"({100 * clean_count / raw_count:.1f}% kept)\n")

    # ---- ANALYSIS 1: demand by hour of day -----------------------------------
    by_hour = (
        clean.groupBy("hour")
        .agg(
            F.count("*").alias("trips"),
            F.round(F.avg("trip_distance"), 2).alias("avg_distance_mi"),
            F.round(F.avg("fare_amount"), 2).alias("avg_fare"),
            F.round(F.avg("tip_pct"), 2).alias("avg_tip_pct"),
        )
        .orderBy("hour")
    )
    by_hour.toPandas().to_csv(f"{OUT_DIR}/spark_by_hour.csv", index=False)

    # ---- ANALYSIS 2: top 15 busiest pickup zones -----------------------------
    by_zone = (
        clean.groupBy("Borough", "Zone")
        .agg(
            F.count("*").alias("trips"),
            F.round(F.avg("fare_amount"), 2).alias("avg_fare"),
            F.round(F.avg("tip_pct"), 2).alias("avg_tip_pct"),
            F.round(F.sum("total_amount"), 2).alias("total_revenue"),
        )
        .orderBy(F.desc("trips"))
    )
    by_zone.limit(15).toPandas().to_csv(
        f"{OUT_DIR}/spark_top_zones.csv", index=False)

    # ---- ANALYSIS 3: revenue & tipping by borough ----------------------------
    by_borough = (
        clean.groupBy("Borough")
        .agg(
            F.count("*").alias("trips"),
            F.round(F.sum("total_amount"), 2).alias("total_revenue"),
            F.round(F.avg("tip_pct"), 2).alias("avg_tip_pct"),
        )
        .orderBy(F.desc("total_revenue"))
    )
    by_borough.toPandas().to_csv(f"{OUT_DIR}/spark_by_borough.csv", index=False)

    # ---- ANALYSIS 4: tipping by payment type ---------------------------------
    by_pay = (
        clean.groupBy("payment_type")
        .agg(
            F.count("*").alias("trips"),
            F.round(F.avg("tip_pct"), 2).alias("avg_tip_pct"),
        )
        .orderBy("payment_type")
    )
    by_pay.toPandas().to_csv(f"{OUT_DIR}/spark_by_payment.csv", index=False)

    elapsed = time.time() - t0
    print("=== SPARK RESULTS ===")
    print("\n-- Demand by hour of day --")
    by_hour.show(24, truncate=False)
    print("-- Top 15 busiest pickup zones --")
    by_zone.show(15, truncate=False)
    print("-- Revenue & tipping by borough --")
    by_borough.show(truncate=False)

    with open(f"{OUT_DIR}/spark_timing.txt", "w") as fh:
        fh.write(f"Engine: PySpark (local[*])\n")
        fh.write(f"Raw trips: {raw_count}\nClean trips: {clean_count}\n")
        fh.write(f"Total runtime: {elapsed:.1f} s\n")
    print(f"\n>>> Spark total runtime: {elapsed:.1f} s")
    print(f">>> Output written to {OUT_DIR}/spark_*.csv")

    spark.stop()


if __name__ == "__main__":
    main()
