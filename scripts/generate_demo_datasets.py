#!/usr/bin/env python3
"""Regenerate the synthetic demo datasets and their ground-truth benchmark files.

    python scripts/generate_demo_datasets.py

Writes:
  datasets/sample/<name>.csv                     the dataset you upload (no ground-truth columns)
  datasets/benchmarks/<name>.benchmark.json      planted patterns and generation settings
  datasets/benchmarks/<name>.labels.csv          per-case planted-pattern flags (ground truth)

Everything is generated with fixed seeds, so the files are reproducible byte for byte.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.demo.catalog import DEMOS, to_csv_bytes  # noqa: E402


def main() -> None:
    sample, bench = ROOT / "datasets" / "sample", ROOT / "datasets" / "benchmarks"
    sample.mkdir(parents=True, exist_ok=True)
    bench.mkdir(parents=True, exist_ok=True)
    for key, spec in DEMOS.items():
        records, labels = spec.generate()
        stem = spec.filename.rsplit(".", 1)[0]
        (sample / spec.filename).write_bytes(to_csv_bytes(records))
        with open(bench / f"{stem}.labels.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(labels[0].keys()))
            w.writeheader()
            w.writerows(labels)
        meta = {**spec.benchmark, "dataset_file": f"datasets/sample/{spec.filename}", "labels_file": f"datasets/benchmarks/{stem}.labels.csv",
                "suggested_mapping": spec.mapping, "observed_error_rate": round(sum(l["error_injected"] for l in labels) / len(labels), 4)}
        (bench / f"{stem}.benchmark.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{key}: {len(records)} records -> {spec.filename}")


if __name__ == "__main__":
    main()
