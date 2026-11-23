# How the analysis works

This page describes exactly what the engine computes. All of it is deterministic Python: the
same file and settings always give the same numbers.

## 1. Scoring each case

| Task | A case is correct when | Metrics reported |
|---|---|---|
| Classification | the predicted label equals the expected label (case-insensitive by default) | accuracy, macro and weighted precision / recall / F1, per-class precision / recall / F1 / support, confusion matrix, top confusions, class balance, optional binary metrics for one positive label |
| Text / QA / extraction | the chosen rule passes: exact match, normalized exact match (case, punctuation and articles ignored), token F1 ≥ threshold, or similarity ≥ threshold | accuracy, exact match, normalized exact match, token precision / recall / F1, lexical similarity, optional semantic similarity |
| Structured JSON | every field matches, or the share of matching fields ≥ threshold | accuracy, invalid-JSON rate, schema errors (optional JSON Schema), per-field accuracy, missing and wrong fields |

Each failed case also gets an error type (for example `partial_match`, `mismatch`,
`empty_output`, `invalid_json`, `missing_fields`, `wrong_values`).

Records without a usable expected output are excluded and counted, never silently scored.

## 2. Features used for failure discovery

- **Metadata columns** the user mapped (categorical, numeric or boolean).
- **Derived from the input text:** word count, number of date mentions (English and Hindi month
  names and numeric formats), number of numbers, script (latin / devanagari / mixed), and layout
  (normal, mostly uppercase, table-like, list or multiline).
- **Expected output length** in words.
- For classification, the **expected class**, so class-specific weaknesses show up as groups.

Nothing is derived from the model's actual output, because that would leak the outcome into the
explanation. Identifier-like columns (named `id` or `*_id`, nearly unique values, or running
numbers) are excluded. A feature that separates failures from successes almost perfectly
(precision and recall ≥ 0.98) is dropped as probable leakage.

## 3. Searching for failure groups

1. **Single conditions.** Categorical values. Numeric thresholds: every distinct value when there
   are 12 or fewer, otherwise quantile bins plus both tails. "Is missing" for columns with gaps.
2. **Two-condition rules (pairs),** built from the 40 most promising single conditions on
   different features. A pair is kept only if each condition raises the error rate *within* the
   other (conditional one-sided Fisher test, p < 0.01 both ways) and the pair beats both parents
   by at least 5 percentage points.
3. **A shallow decision tree** (depth 3, balanced class weights), trained on 65% of the rows.
   Its leaves are pruned of conditions that do not matter, then tested **only on the other 35%**
   the tree never saw.

Each candidate is tested with a one-sided Fisher exact test (group vs. everyone else). Groups
smaller than the minimum group size (default 20) are never tested.

## 4. Statistical safeguards

- **One Benjamini–Hochberg correction over the full search.** Single conditions, held-out tree
  rules, and the whole space of possible two-condition rules are corrected together. Pairs that
  were screened out before testing still count toward the family size, so pre-selection cannot
  inflate significance.
- **Reliable** means q ≤ 0.05 (default), the 95% Wilson interval lies entirely above the overall
  error rate, and, for tree rules, the effect holds on held-out rows. Anything else is labelled
  **tentative** and explained.
- **Sequential covering.** Groups are picked one at a time by how many failures *beyond the
  baseline* they add that higher-ranked groups did not already explain. Simpler rules are
  preferred (a 30% discount per extra condition). Groups that mostly restate an earlier group are
  dropped, and remaining overlaps are noted.
- **Narrow explanations win.** If a broad rule's excess failures come almost entirely from one
  narrower rule inside it (the narrow rule covers at most 75% of the broad group and at least
  80% of its excess failures, and the remaining rows fail at about the normal rate), the
  narrow rule is reported instead and the reason is attached.

On the bundled benchmarks, with the failure labels randomly shuffled, at least one reliable group
was reported in 4 of 300 runs (1.3%). See [technical-evaluation.md](technical-evaluation.md).

## 5. Clustering failures

Failed cases are turned into short "mistake signature" documents: which tokens were dropped or
added relative to the expected output, whether the prediction appears in the input, the words
around it, and for JSON which fields were wrong or missing. These are embedded with TF-IDF and
LSA and clustered with k-means, with k chosen by cosine silhouette (minimum 0.05; the minimum
cluster size is max(3, 2% of failures)). Clustering is skipped, with a stated reason, when there
are fewer than 12 failures or no k gives a usable silhouette. Clusters help you read failures in
batches; they are not explanations.

## 6. The AI investigator

The investigator never sees the raw dataset. It receives an evidence package:

- `EVIDENCE_001`: overall metrics; `EVIDENCE_002`: dataset context.
- For each selected group: its verified statistics, up to 3 representative failures, up to 2
  correct cases with the same rule (counter-evidence), and up to 2 similar failures outside the
  group.
- Cluster summaries and one representative failure per cluster.

Dataset text inside the package is fenced and neutralised so instructions hidden in the data are
treated as data. The reply must match `InvestigationReport` (strict JSON schema). After parsing:

- references to evidence ids or group keys that do not exist are removed and logged;
- hypotheses with no remaining supporting evidence are flagged;
- numbers in the AI's text that do not appear in the package are flagged as unverified;
- words such as "proves" or "definitely" are flagged as overclaiming.

Statuses: `completed`, `completed_with_warnings`, `insufficient_evidence`, `llm_disabled`,
`llm_not_configured`, `llm_error`, `invalid_output`, `budget_exceeded`. In every status the
verified statistics and the evidence package are still shown.

## 7. Experiments

An experiment starts as `recommended` and moves through `planned`, `running`, `completed` or
`abandoned`. It can only be completed with a result. **Measure** re-applies the target group's
rule to a newer evaluation run, then compares the group's error rate before and after with a
two-proportion z-test. The outcome is one of: improved, improved but not significant,
regressed, regressed but not significant, no change, or not measured. Without a measured
result nothing is claimed.
