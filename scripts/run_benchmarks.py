"""Measure Blindspot AI's failure discovery on the bundled synthetic benchmarks.

For each benchmark this script:
  1. scores every case and runs failure discovery exactly as the app does;
  2. checks how well the reported reliable groups match each planted failure pattern
     (precision = share of group members that carry the pattern, recall = share of the
     pattern's cases the group covers);
  3. runs a null control: the same data with the failure labels randomly shuffled, many
     times, and counts how often any "reliable" group is reported. On shuffled labels there
     is nothing real to find, so every reliable group there is a false alarm.

Usage (from the repository root):
    python scripts/run_benchmarks.py            # 30 null shuffles per benchmark
    python scripts/run_benchmarks.py --shuffles 100
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.demo.catalog import DEMOS  # noqa: E402
from app.demo.scoring import score_recovery  # noqa: E402
from app.evaluation.config import EvaluationConfig  # noqa: E402
from app.evaluation.runner import evaluate_records  # noqa: E402
from app.failure_discovery.engine import discover_failures  # noqa: E402
from app.failure_discovery.features import build_feature_frame  # noqa: E402


def analyse(spec):
    records, truth = spec.generate()
    config = EvaluationConfig.model_validate({"task_type": spec.task})
    t0 = time.perf_counter()
    outcome, _ = evaluate_records(records, spec.mapping, config)
    cases = outcome.cases
    failures = np.array([not c.correct for c in cases])
    extra = {"expected_label": [c.details.get("expected_label", "") for c in cases]} if spec.task == "classification" else None
    ff = build_feature_frame(records, [c.index for c in cases], spec.mapping, derive=config.discovery.derive_text_features, extra_categorical=extra)
    result = discover_failures(ff, failures, config.discovery, task_type=spec.task, class_balance=outcome.extras.get("class_balance"))
    seconds = time.perf_counter() - t0
    return records, truth, config, cases, failures, ff, result, outcome, seconds


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shuffles", type=int, default=30)
    args = ap.parse_args()

    print("# Benchmark results\n")
    total_found = total_planted = 0
    for key, spec in DEMOS.items():
        records, truth, config, cases, failures, ff, result, outcome, seconds = analyse(spec)
        ids = [c.case_id for c in cases]
        groups = [{"name": g.name, "reliability": g.reliability, "member_case_ids": {ids[i] for i in np.where(g.mask)[0]}} for g in result.groups]
        patterns = [p["id"] for p in spec.benchmark["planted_patterns"]]
        scored = score_recovery(groups, truth, patterns)
        total_found += scored["recovered"]
        total_planted += scored["total"]

        print(f"## {spec.benchmark['name']}\n")
        print(f"- Records: {len(records)}, task: {spec.task}, overall error rate: {failures.mean():.1%}")
        print(f"- Hypotheses tested: {result.summary.get('hypotheses_tested')}, reliable groups reported: "
              f"{sum(g.reliability == 'reliable' for g in result.groups)}, analysis time: {seconds:.1f} s\n")
        print("| Planted pattern | Cases | Best matching reported group | Precision | Recall | Recovered |")
        print("|---|---:|---|---:|---:|:---:|")
        for pid, v in scored["patterns"].items():
            b = v["best_match"] or {}
            name = (b.get("group") or "none").replace("|", "/")
            print(f"| {pid} | {v['planted_cases']} | {name} ({b.get('reliability', '-')}) | {b.get('precision', 0):.2f} | {b.get('recall', 0):.2f} | {'yes' if v['recovered'] else 'no'} |")

        rng = np.random.default_rng(2024)
        false_alarm_runs = 0
        false_groups = 0
        for _ in range(args.shuffles):
            shuffled = rng.permutation(failures)
            null = discover_failures(ff, shuffled, config.discovery, task_type=spec.task, class_balance=outcome.extras.get("class_balance"))
            n_rel = sum(g.reliability == "reliable" for g in null.groups)
            false_groups += n_rel
            false_alarm_runs += n_rel > 0
        print(f"\nNull control ({args.shuffles} runs with shuffled failure labels): {false_alarm_runs} run(s) reported any reliable group "
              f"({false_groups} false groups in total).\n")

    print(f"**Planted patterns recovered: {total_found} of {total_planted}.**")


if __name__ == "__main__":
    main()
