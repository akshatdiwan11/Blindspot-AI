# Technical evaluation

This report measures how well Blindspot AI finds failure patterns that are known to exist, and
how often it reports patterns that do not. Every number below was produced by
`python scripts/run_benchmarks.py --shuffles 100` on the bundled synthetic benchmarks and can
be reproduced exactly (the generators are seeded).

## Method

Each benchmark is a seeded synthetic dataset in which a simulated model fails more often on
specific, planted kinds of input. The planted label of every case is known
(`datasets/benchmarks/*.labels.csv`).

- **Recovery.** For each planted pattern, the best-matching reported *reliable* group is found.
  Precision is the share of that group's records that carry the pattern; recall is the share of
  the pattern's records that the group covers. A pattern counts as recovered when a reliable
  group reaches precision ≥ 0.6 and recall ≥ 0.4.
- **Null control.** The same data is analysed 100 times with the failure labels randomly
  shuffled. Nothing real can be found in shuffled data, so any reliable group is a false alarm.
  The target is a false alarm in at most 5% of runs.

Synthetic data is cleaner than real data. These results show the engine behaves as designed; they
do not predict performance on every real dataset.

### Deadline extraction benchmark (synthetic)

- Records: 900, task: text, overall error rate: 17.4%
- Hypotheses tested: 171, reliable groups reported: 5, analysis time: 0.3 s

| Planted pattern | Cases | Best matching reported group | Precision | Recall | Recovered |
|---|---:|---|---:|---:|:---:|
| multi_date | 176 | date_mentions ≥ 3 (reliable) | 1.00 | 1.00 | yes |
| hindi | 121 | language = Hindi (reliable) | 1.00 | 1.00 | yes |
| unusual_format | 89 | input_format = mostly_uppercase (reliable) | 1.00 | 0.56 | yes |
| long_document | 117 | page_count ≥ 5 (reliable) | 1.00 | 0.88 | yes |
| mixed_language | 108 | input_script ≠ latin AND input_length_words ≥ 43 (reliable) | 0.31 | 0.44 | no |

Null control (100 runs with shuffled failure labels): 2 run(s) reported any reliable group (2 false groups in total).

### Support email triage benchmark (synthetic)

- Records: 700, task: classification, overall error rate: 16.1%
- Hypotheses tested: 49, reliable groups reported: 3, analysis time: 0.1 s

| Planted pattern | Cases | Best matching reported group | Precision | Recall | Recovered |
|---|---:|---|---:|---:|:---:|
| hinglish | 110 | language = Hinglish (reliable) | 0.91 | 1.00 | yes |
| very_short | 89 | expected_label ≠ Billing AND input_length_words < 6 (reliable) | 1.00 | 0.74 | yes |
| fraud_class | 71 | expected_label = Fraud (reliable) | 1.00 | 1.00 | yes |

Null control (100 runs with shuffled failure labels): 1 run(s) reported any reliable group (1 false groups in total).

### Invoice JSON extraction benchmark (synthetic)

- Records: 500, task: json, overall error rate: 29.6%
- Hypotheses tested: 78, reliable groups reported: 2, analysis time: 0.1 s

| Planted pattern | Cases | Best matching reported group | Precision | Recall | Recovered |
|---|---:|---|---:|---:|:---:|
| scanned | 124 | source = Scan (reliable) | 1.00 | 1.00 | yes |
| foreign_ccy | 133 | source = Scan (reliable) | 0.27 | 0.25 | no |
| multi_page | 129 | pages ≥ 2 (reliable) | 1.00 | 1.00 | yes |

Null control (100 runs with shuffled failure labels): 1 run(s) reported any reliable group (2 false groups in total).

**Planted patterns recovered: 9 of 11.**

## Summary

| | Result |
|---|---|
| Planted patterns recovered | **9 of 11** |
| Precision of the matching group, recovered patterns | 0.91 to 1.00 |
| Null control: runs with any false alarm | **4 of 300 (1.3%)** |
| Analysis time (scoring + discovery), 500 to 900 rows | 0.1 to 0.3 s |
| 20,000-row classification file, upload + full analysis (Docker, PostgreSQL) | about 2.5 s |

### Why two patterns are not recovered

- **`foreign_ccy` (invoice JSON).** The foreign currency only appears inside the invoice text, and
  no metadata column or derived feature describes currency. It was planted on purpose to show the
  limit of metadata-based discovery: the engine correctly does *not* invent a group for it. The
  failure clusters and the evidence package still surface these cases for a human or the AI
  investigator to read.
- **`mixed_language` (deadline extraction).** The engine reports
  `input_script ≠ latin AND input_length_words ≥ 43`, which overlaps mixed-language notices
  (precision 0.31, recall 0.44) but also catches long Hindi notices. Script detection on short
  mixed passages is the limiting factor.

### A finding the benchmarks forced us to fix

An earlier version corrected decision-tree rules separately from the other tests and counted only
the two-condition rules it actually tried. In the null control that produced a false alarm in
about 7% of runs, above the 5% target. Correcting everything in one family that includes the
full two-condition search space brought it to 1.3% with no loss of recovery. Both checks now run
in the test suite (`tests/evaluation/test_benchmark_recovery.py`).
