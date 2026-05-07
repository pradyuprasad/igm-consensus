# igm-consensus

Where do elite economists actually agree, and how strongly? This repo scrapes every IGM Forum poll from the [Kent A. Clark Center for Global Markets](https://kentclarkcenter.org/surveys/) (US, Europe, and Finance panels), normalizes the votes, and computes a direction-blind consensus metric for every question.

- **Blog post**: https://pradyuprasad.com/writings/economists-agree/
- **Interactive chart**: [`consensus.html`](consensus.html) — 629 US questions ranked by consensus strength
- **Dataset (Hugging Face)**: https://huggingface.co/datasets/pradyuprasad/igm-consensus

## What's in the repo

```
clark_center/             scraper + parser modules
main.py                   pipeline entry: discover → fetch → parse → emit
compute_consensus.py      statements.csv → statements_consensus.csv
generate_consensus.py     renders consensus.html
blog_post.py              prints every number cited in the blog post
methodology.md            data coverage and sourcing details
statements.csv            1,146 rows · one per question
votes.csv                 50,410 rows · one per economist-question pair
statements_consensus.csv  enriched with HHI and consensus_score
consensus.html            standalone chart (open in any browser)
```

## Reproducing the data

```bash
uv sync                                    # install locked env
uv run main.py                             # rebuild from cached raw sources
uv run main.py --refresh                   # force fresh fetch
uv run python compute_consensus.py         # produce statements_consensus.csv
uv run python generate_consensus.py        # produce consensus.html
uv run python blog_post.py                 # print blog-post numbers
```

The raw scraped HTML/CSV cache (`data/raw/`, ~211 MB) is gitignored. It will repopulate on first run.

## Consensus metric

The chart sorts questions by **HHI** (Herfindahl-Hirschman concentration) on the three vote shares:

```
HHI = share_agree² + share_uncertain² + share_disagree²
```

- `1.00` = unanimous; `0.33` = perfectly diffuse three-way split (the floor).
- Direction-blind, so it survives wording flips ("X is good" vs. "X is bad").
- Sensitive to dissent concentration: ranks 60/39/1 (settled) above 60/30/10 (real dissent), unlike top-share alone.

## Coverage

- **558** poll pages, **0** failures, **0** duplicate URLs
- **1,146** statements: US 644, Europe 377, Finance 125
- **50,410** vote rows from **193** distinct economists at top departments
- 553/558 pages source-of-truth from the official "Download Poll Data" CSV; 5 special crisis-rating pages use HTML chart shares

## License

Code: MIT. Data: same provenance as the IGM Forum surveys; consult the [Clark Center site](https://kentclarkcenter.org/) for terms.
