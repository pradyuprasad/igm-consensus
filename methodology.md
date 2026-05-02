# Methodology

Primary source: https://kentclarkcenter.org/surveys/

The extractor discovers survey URLs from the Clark Center survey and survey-special sitemaps, checks robots.txt, downloads each poll page, and then prefers the official `Download Poll Data` CSV when present. HTML is still parsed for page metadata, statement text, panel type, source topics, profile URLs, affiliations, visible chart percentages, and fallback votes when no CSV is present.

Run command: `uv run main.py` from this directory. Raw pages and CSVs are cached under `data/raw/`; regenerated deliverables are written at the project root. Use `uv run main.py --refresh` to ignore the cache and redownload all sources.

Unweighted agreement metrics are computed only from the raw vote labels. Confidence-weighted chart values, when exposed by the page JavaScript, are stored in the `weighted_*` columns and are not mixed with the unweighted counts.

Survey-special crisis pages use 0-5 numeric importance ratings rather than agree/disagree votes. They are retained, with numeric ratings mapped to `Other / Not Applicable` and agreement shares left blank.

Allowed issue categories: Monetary policy; Fiscal policy; Taxation; Labor markets; Trade; Immigration; Education; Healthcare; Climate/environment; Financial regulation; Banking; Industrial policy; Antitrust/competition; Housing/urban policy; Growth/productivity; Inequality/redistribution; COVID/pandemic policy; Energy; International economics; Public finance; Political economy; Other

## Coverage Check

- total_poll_pages_discovered: 558
- total_poll_pages_successfully_processed: 558
- total_statements_extracted: 1146
- total_vote_rows_extracted: 50410
- csv_backed_pages: 553
- html_only_or_special_pages: 5
- failed_or_ambiguous_records: 0

## CSV vs Page Check

Sampled 20 CSV-backed poll pages; 20 passed the text/name/count comparison.

## Duplicate Check

- duplicate_poll_urls: 0
- duplicate_statement_ids: 0
- duplicate_votes_within_statement: 0

## Vote-Label Check

Distinct raw vote labels: 18
Ambiguous labels: 0

## Date Check

Missing or ambiguous publication dates: 0

## Panel Check

- Europe: 377 statements
- Finance: 125 statements
- US: 644 statements

## Reproducibility

1. `uv sync` to install the locked environment.
2. `uv run main.py` to reuse cached raw sources where available, fetch missing sources, rebuild CSV outputs, run quality checks, and rewrite the methodology and analysis summaries.
3. `uv run main.py --refresh` to force a fresh redownload of all source pages and official CSVs.
4. Inspect `source_log.csv` for every source URL used, whether it was fetched or reused from cache.
