"""
Generate the figures used in the report from the CSV outputs.
Run AFTER spark_analysis.py and benchmark.py.  ->  python src/make_charts.py
"""
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = "output"
FIG = "output/figures"
os.makedirs(FIG, exist_ok=True)
plt.rcParams.update({"figure.dpi": 130, "font.size": 11,
                     "axes.grid": True, "grid.alpha": 0.3})
BLUE, ORANGE = "#2563eb", "#f59e0b"


def fig_demand():
    d = pd.read_csv(f"{OUT}/spark_by_hour.csv").sort_values("hour")
    fig, ax1 = plt.subplots(figsize=(9, 4.5))
    ax1.bar(d.hour, d.trips / 1e6, color=BLUE, alpha=0.85, label="Trips (millions)")
    ax1.set_xlabel("Hour of day"); ax1.set_ylabel("Trips (millions)", color=BLUE)
    ax1.set_xticks(range(0, 24))
    ax2 = ax1.twinx()
    ax2.plot(d.hour, d.avg_tip_pct, color=ORANGE, marker="o", lw=2, label="Avg tip %")
    ax2.set_ylabel("Average tip %", color=ORANGE)
    plt.title("NYC Yellow Taxi 2024 — Demand and Tipping by Hour of Day")
    fig.tight_layout(); fig.savefig(f"{FIG}/fig1_demand_by_hour.png"); plt.close()


def fig_zones():
    d = pd.read_csv(f"{OUT}/spark_top_zones.csv").head(10).iloc[::-1]
    labels = (d.Zone.astype(str) + " (" + d.Borough.astype(str) + ")").tolist()
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(labels, d.trips / 1e6, color=BLUE)
    ax.set_xlabel("Trips (millions)")
    plt.title("Top 10 Busiest Pickup Zones — 2024")
    fig.tight_layout(); fig.savefig(f"{FIG}/fig2_top_zones.png"); plt.close()


def fig_borough():
    d = pd.read_csv(f"{OUT}/spark_by_borough.csv")
    d = d[d.trips > 1000].sort_values("total_revenue")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(d.Borough.astype(str).tolist(), (d.total_revenue / 1e6).tolist(), color=ORANGE)
    ax.set_xlabel("Total revenue (US$ millions)")
    plt.title("Total Revenue by Pickup Borough — 2024")
    fig.tight_layout(); fig.savefig(f"{FIG}/fig3_revenue_by_borough.png"); plt.close()


def fig_benchmark():
    b = pd.read_csv(f"{OUT}/benchmark.csv")
    x = b.rows / 1e6
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))
    ax1.plot(x, b.pandas_sec, marker="o", color=ORANGE, lw=2, label="Pandas")
    ax1.plot(x, b.spark_sec, marker="s", color=BLUE, lw=2, label="PySpark")
    ax1.set_xlabel("Rows processed (millions)"); ax1.set_ylabel("Runtime (seconds)")
    ax1.set_title("Runtime vs data size"); ax1.legend()
    ax2.plot(x, b.pandas_peak_mb, marker="o", color=ORANGE, lw=2, label="Pandas")
    ax2.axhline(16000, color="red", ls="--", lw=1, label="16 GB RAM limit")
    ax2.set_xlabel("Rows processed (millions)")
    ax2.set_ylabel("Peak memory (MB)")
    ax2.set_title("Pandas memory grows linearly with data"); ax2.legend()
    plt.suptitle("PySpark vs Pandas — Scaling Benchmark", fontweight="bold")
    fig.tight_layout(); fig.savefig(f"{FIG}/fig4_benchmark.png"); plt.close()


if __name__ == "__main__":
    fig_demand(); fig_zones(); fig_borough(); fig_benchmark()
    print("Figures written to", FIG)
    for f in sorted(os.listdir(FIG)):
        print("  ", f)
