"""
Scaling benchmark: PySpark vs Pandas as the dataset grows
=========================================================
Runs the SAME "trips + avg tip% per pickup zone" aggregation on an
increasing number of months (1 -> 3 -> 6 -> 12) with each engine, and
records wall-clock time and peak memory.

This is the evidence for the report's core comparison: where does the
distributed engine start to win, and what does single-machine Pandas
cost in memory as data grows?

Run:  python src/benchmark.py
"""
import time
import glob
import os
import tracemalloc
import pandas as pd

DATA_DIR = "data"
OUT_DIR = "output"
os.makedirs(OUT_DIR, exist_ok=True)
ALL_FILES = sorted(glob.glob(f"{DATA_DIR}/yellow_tripdata_2024-*.parquet"))
STEPS = [1, 3, 6, 12]                       # number of months to include
USE_COLS = ["PULocationID", "fare_amount", "tip_amount",
            "trip_distance", "total_amount", "passenger_count"]


# ---------------------------- Pandas ------------------------------------------
def run_pandas(files):
    tracemalloc.start()
    t0 = time.time()
    frames = [pd.read_parquet(f, columns=USE_COLS) for f in files]
    df = pd.concat(frames, ignore_index=True)
    df = df[(df.fare_amount > 0) & (df.trip_distance > 0)
            & (df.passenger_count > 0)]
    df["tip_pct"] = df.tip_amount / df.fare_amount * 100
    _ = df.groupby("PULocationID").agg(
        trips=("PULocationID", "size"), avg_tip=("tip_pct", "mean"))
    peak = tracemalloc.get_traced_memory()[1] / 1e6      # MB
    tracemalloc.stop()
    return time.time() - t0, peak, len(df)


# ---------------------------- Spark -------------------------------------------
def run_spark(files, spark):
    from pyspark.sql import functions as F
    t0 = time.time()
    df = spark.read.parquet(*files)
    df = df.filter((F.col("fare_amount") > 0) & (F.col("trip_distance") > 0)
                   & (F.col("passenger_count") > 0))
    df = df.withColumn("tip_pct", F.col("tip_amount") / F.col("fare_amount") * 100)
    res = df.groupBy("PULocationID").agg(
        F.count("*").alias("trips"), F.avg("tip_pct").alias("avg_tip"))
    n = df.count()
    res.collect()
    return time.time() - t0, n


def main():
    from pyspark.sql import SparkSession
    spark = (SparkSession.builder.appName("bench").master("local[*]")
             .config("spark.driver.memory", "6g")
             .config("spark.sql.shuffle.partitions", "64").getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")

    rows = []
    for k in STEPS:
        files = ALL_FILES[:k]
        p_time, p_mem, n = run_pandas(files)
        s_time, _ = run_spark(files, spark)
        rows.append({"months": k, "rows": n,
                     "pandas_sec": round(p_time, 1),
                     "pandas_peak_mb": round(p_mem, 0),
                     "spark_sec": round(s_time, 1)})
        print(f"{k:2d} month(s) | {n:>10,} rows | "
              f"Pandas {p_time:5.1f}s (peak {p_mem:6.0f} MB) | "
              f"Spark {s_time:5.1f}s")

    spark.stop()
    bench = pd.DataFrame(rows)
    bench.to_csv(f"{OUT_DIR}/benchmark.csv", index=False)
    print("\nSaved -> output/benchmark.csv")
    print(bench.to_string(index=False))


if __name__ == "__main__":
    main()
