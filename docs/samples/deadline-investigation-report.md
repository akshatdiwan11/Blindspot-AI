# Blindspot AI investigation report: Deadline extraction (synthetic demo)

- **Evaluation run:** #5 (Baseline (synthetic))
- **Run timestamp:** 2026-11-23T06:16:41.725370+00:00
- **Report generated:** 2026-11-23T06:16:46.192314+00:00
- **Dataset:** deadline_extraction_benchmark v1 (900 records, sha256 `5c04e5d93966`)
- **Data:** SYNTHETIC benchmark data with deliberately planted failure patterns.

> Metrics, failure groups and clusters are computed deterministically by the Blindspot AI engine. Failure groups are statistical associations, not proven causes. Root-cause statements from the AI investigator are untested hypotheses that cite evidence IDs; they become findings only when an experiment measures the effect.

## 1. Evaluation summary (verified by the engine)

Task: `text` · evaluated records: 900 · failures: 157 · error rate: 17.4%

| Metric | Value |
|---|---|
| accuracy | 0.8256 |
| exact_match | 0.8256 |
| normalized_exact_match | 0.8256 |
| token_precision | 0.8917 |
| token_recall | 0.8841 |
| token_f1 | 0.8871 |
| failure_rate | 0.1744 |
| lexical_similarity | 0.8738 |

## 2. Hidden failure groups (verified statistics)

### #1 date_mentions ≥ 3

- Rule: `date_mentions ≥ 3` (single)
- Records: 176 · failures: 90 · error rate: 51.1% vs overall 17.4% (+33.7 pp)
- 95% CI: 43.8% to 58.4% · q-value: 0.0000 · reliability: **reliable** · severity: critical

### #2 input_script ≠ latin AND input_length_words ≥ 43

- Rule: `input_script ≠ latin AND input_length_words ≥ 43` (tree)
- Records: 157 · failures: 59 · error rate: 37.6% vs overall 17.4% (+20.1 pp)
- 95% CI: 30.4% to 45.4% · q-value: 0.0082 · reliability: **reliable** · severity: high
- Note: Decision-tree rule validated on 60 held-out rows: error rate 33% vs 14% for other held-out rows.
- Note: Still elevated after removing higher-ranked groups: 16% vs 4% on the remaining rows.

### #3 language = Hindi

- Rule: `language = Hindi` (single)
- Records: 121 · failures: 48 · error rate: 39.7% vs overall 17.4% (+22.2 pp)
- 95% CI: 31.4% to 48.6% · q-value: 0.0000 · reliability: **reliable** · severity: high
- Note: Still elevated after removing higher-ranked groups: 35% vs 6% on the remaining rows.

### #4 page_count ≥ 5

- Rule: `page_count ≥ 5` (single)
- Records: 103 · failures: 32 · error rate: 31.1% vs overall 17.4% (+13.6 pp)
- 95% CI: 22.9% to 40.5% · q-value: 0.0033 · reliability: **reliable** · severity: high
- Note: Still elevated after removing higher-ranked groups: 14% vs 2% on the remaining rows.

### #5 input_format = mostly_uppercase

- Rule: `input_format = mostly_uppercase` (single)
- Records: 50 · failures: 17 · error rate: 34.0% vs overall 17.4% (+16.6 pp)
- 95% CI: 22.4% to 47.8% · q-value: 0.0286 · reliability: **reliable** · severity: high
- Note: Still elevated after removing higher-ranked groups: 25% vs 4% on the remaining rows.

### #6 input_format = table_like

- Rule: `input_format = table_like` (single)
- Records: 39 · failures: 12 · error rate: 30.8% vs overall 17.4% (+13.3 pp)
- 95% CI: 18.6% to 46.4% · q-value: 0.2028 · reliability: **tentative** · severity: low
- Note: Not significant after multiple-comparison correction (q = 0.20). Treat as a lead, not a finding.
- Note: Small subgroup (39 records): estimates are uncertain.
- Note: Still elevated after removing higher-ranked groups: 19% vs 1% on the remaining rows.

## 3. Failure clusters

- **'issued' before prediction, 'notice' before prediction · language = English · partial match**: 53 failures (33.8% of all failures)
- **prediction not found in the input, extra 'september' · partial match**: 47 failures (29.9% of all failures)
- **shorter than expected, prediction not found in the input · language = Hindi · partial match**: 27 failures (17.2% of all failures)
- **extra 'found', extra 'not' · mismatch**: 16 failures (10.2% of all failures)
- **'is' before prediction, 'submission' before prediction · language = English · partial match**: 14 failures (8.9% of all failures)

## 4. AI investigation (hypotheses, not facts)

Investigation #1 · status: `llm_disabled` · model: gpt-4o-mini · tokens: 0 · est. cost: $0.0000

_LLM investigation is turned off for this project, so no data was sent to an LLM. The evidence package below was built from the deterministic analysis. Turn on LLM investigation in the project settings to generate hypotheses._

## 5. Experiments

No experiments are linked to this run.
## Appendix: evidence items

- **EVIDENCE_001** (metrics): Overall evaluation metrics (computed by the evaluation engine)
- **EVIDENCE_002** (dataset): Dataset and analysis context
- **EVIDENCE_003** (subgroup_statistic): GROUP_1 statistics: date_mentions ≥ 3
- **EVIDENCE_004** (failed_case): Representative failure in GROUP_1 (DL-0028)
- **EVIDENCE_005** (failed_case): Representative failure in GROUP_1 (DL-0166)
- **EVIDENCE_006** (failed_case): Representative failure in GROUP_1 (DL-0472)
- **EVIDENCE_007** (successful_case): Correct case inside GROUP_1 (DL-0020): same rule, but the model succeeded
- **EVIDENCE_008** (successful_case): Correct case inside GROUP_1 (DL-0177): same rule, but the model succeeded
- **EVIDENCE_009** (similar_failure): Failure outside GROUP_1 that resembles its failures (DL-0783)
- **EVIDENCE_010** (similar_failure): Failure outside GROUP_1 that resembles its failures (DL-0667)
- **EVIDENCE_011** (subgroup_statistic): GROUP_2 statistics: input_script ≠ latin AND input_length_words ≥ 43
- **EVIDENCE_012** (failed_case): Representative failure in GROUP_2 (DL-0031)
- **EVIDENCE_013** (failed_case): Representative failure in GROUP_2 (DL-0255)
- **EVIDENCE_014** (failed_case): Representative failure in GROUP_2 (DL-0322)
- **EVIDENCE_015** (successful_case): Correct case inside GROUP_2 (DL-0369): same rule, but the model succeeded
- **EVIDENCE_016** (successful_case): Correct case inside GROUP_2 (DL-0578): same rule, but the model succeeded
- **EVIDENCE_017** (similar_failure): Failure outside GROUP_2 that resembles its failures (DL-0579)
- **EVIDENCE_018** (similar_failure): Failure outside GROUP_2 that resembles its failures (DL-0289)
- **EVIDENCE_019** (subgroup_statistic): GROUP_3 statistics: language = Hindi
- **EVIDENCE_020** (successful_case): Correct case inside GROUP_3 (DL-0766): same rule, but the model succeeded
- **EVIDENCE_021** (similar_failure): Failure outside GROUP_3 that resembles its failures (DL-0841)
- **EVIDENCE_022** (similar_failure): Failure outside GROUP_3 that resembles its failures (DL-0212)
- **EVIDENCE_023** (subgroup_statistic): GROUP_4 statistics: page_count ≥ 5
- **EVIDENCE_024** (failed_case): Representative failure in GROUP_4 (DL-0438)
- **EVIDENCE_025** (failed_case): Representative failure in GROUP_4 (DL-0648)
- **EVIDENCE_026** (successful_case): Correct case inside GROUP_4 (DL-0654): same rule, but the model succeeded
- **EVIDENCE_027** (successful_case): Correct case inside GROUP_4 (DL-0130): same rule, but the model succeeded
- **EVIDENCE_028** (similar_failure): Failure outside GROUP_4 that resembles its failures (DL-0811)
- **EVIDENCE_029** (similar_failure): Failure outside GROUP_4 that resembles its failures (DL-0407)
- **EVIDENCE_030** (cluster): Failure cluster: 'issued' before prediction, 'notice' before prediction · language = English · partial match
- **EVIDENCE_031** (failed_case): Representative failure of cluster 1 (DL-0097)
- **EVIDENCE_032** (cluster): Failure cluster: prediction not found in the input, extra 'september' · partial match
- **EVIDENCE_033** (failed_case): Representative failure of cluster 2 (DL-0153)
- **EVIDENCE_034** (cluster): Failure cluster: shorter than expected, prediction not found in the input · language = Hindi · partial match
- **EVIDENCE_035** (failed_case): Representative failure of cluster 3 (DL-0151)
- **EVIDENCE_036** (cluster): Failure cluster: extra 'found', extra 'not' · mismatch
- **EVIDENCE_037** (failed_case): Representative failure of cluster 4 (DL-0259)
