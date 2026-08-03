#!/usr/bin/env bash
# One-shot pipeline: runs the Spark analysis, the Pandas baseline,
# the scaling benchmark, and regenerates all figures.
set -e

# Spark needs a JVM. Adjust JAVA_HOME if your Java lives elsewhere.
export JAVA_HOME="${JAVA_HOME:-/opt/anaconda3/lib/jvm}"
export PATH="$JAVA_HOME/bin:$PATH"

echo "==> 1/4  PySpark analysis (big data solution)"
python src/spark_analysis.py

echo "==> 2/4  Pandas baseline (single-machine comparison)"
python src/pandas_baseline.py

echo "==> 3/4  Scaling benchmark (Spark vs Pandas)"
python src/benchmark.py

echo "==> 4/4  Charts"
python src/make_charts.py

echo "Done. See output/ for CSVs, timings, and output/figures/ for charts."
