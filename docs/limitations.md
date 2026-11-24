# Limitations

Blindspot AI is built to be honest about what it can and cannot tell you.

## What the statistics can and cannot say

- **Failure groups are associations, not causes.** "Hindi notices fail at 40%" does not prove the
  language is the reason; something correlated with it might be. Experiments are how a cause is
  confirmed.
- **Discovery only sees the features it is given.** It uses mapped metadata and a few features
  derived from the input text. A weakness that depends on something not described by any column
  (for example the currency inside an invoice) cannot become a failure group. It can still show
  up in clusters and in the evidence package.
- **Small groups are not tested.** Groups below the minimum size (default 20 records) are skipped,
  so rare but severe failure modes in small datasets can be missed.
- **False discoveries are controlled, not eliminated.** The target false discovery rate is 5%. On
  the bundled benchmarks a false alarm appeared in 1.3% of shuffled-label runs.
- **Rules are axis-aligned.** Groups are made of at most a few simple conditions. Complex
  interactions of many features will appear only partly.

## Scoring

- Text matching is lexical by default. Normalized exact match and token F1 do not understand
  paraphrases. Semantic similarity is optional (`ENABLE_EMBEDDINGS=true` plus
  `requirements-embeddings.txt`) and is still not a measure of factual correctness.
- JSON comparison flattens nested objects into dotted field paths and compares the values. A list
  is compared as one whole value, so one wrong item makes the whole list field wrong.
- The quality of every result depends on the quality of the expected outputs.

## The AI investigator

- It is optional and off by default for each project. Without a key everything except the
  AI-written hypotheses still works.
- Its hypotheses are plausible explanations, not findings. The validator removes made-up evidence
  ids and flags unverified numbers and overclaiming language, but it cannot verify the *reasoning*.
- It sees an evidence package of roughly 30 to 45 items, not the whole dataset.
- Calls cost money. A daily budget (`LLM_DAILY_BUDGET_USD`, default 2 USD) stops new
  investigations once reached. Cost is estimated from token counts and configured prices.

## Scale and operations

- Uploads are limited to 10 MB and 20,000 rows by default (configurable). Analysis runs inside
  the request. This is fine at that size (about 2.5 s for 20,000 rows) but is not a job queue.
- There are no user accounts. A deployment is a single shared workspace; put it behind your own
  access control if the data is sensitive.
- The free Render plan sleeps when idle (the first request can take about a minute). Without a
  `DATABASE_URL` the server keeps data in a temporary SQLite file that is wiped on restart.

## Synthetic demo data

The three demo datasets are synthetic, generated with planted failure patterns, and are labelled
as such everywhere in the app and in reports. They show how the engine behaves; they are not
evidence about any real model.
