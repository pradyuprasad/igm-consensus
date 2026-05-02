from __future__ import annotations

import argparse
import csv
from pathlib import Path


POSITION_FIELDS = {
    "Agree": "share_agree",
    "Disagree": "share_disagree",
    "Uncertain": "share_uncertain",
}

WEIGHTED_POSITION_FIELDS = {
    "Agree": "weighted_share_agree",
    "Disagree": "weighted_share_disagree",
    "Uncertain": "weighted_share_uncertain",
}

NEW_FIELDS = [
    "consensus_direction",
    "consensus_score",
    "consensus_bucket",
    "consensus_percentile",
    "share_agree_percentile",
    "confidence_weighted_direction",
    "confidence_weighted_score",
    "confidence_weighted_bucket",
    "confidence_weighted_consensus_percentile",
    "confidence_weighted_share_agree_percentile",
    "confidence_weighted_shift",
]

PERCENTILE_FIELDS = [
    ("consensus_score", "consensus_percentile"),
    ("share_agree", "share_agree_percentile"),
    ("confidence_weighted_score", "confidence_weighted_consensus_percentile"),
    ("weighted_share_agree", "confidence_weighted_share_agree_percentile"),
]


def main() -> None:
    args = parse_args()
    rows = read_csv(args.input)
    enriched = [add_consensus_fields(row) for row in rows]
    add_percentile_fields(enriched)
    write_csv(args.output, enriched)
    print(f"Wrote {len(enriched)} rows to {args.output}")


def add_consensus_fields(row: dict[str, str]) -> dict[str, str]:
    unweighted = consensus_from_fields(row, POSITION_FIELDS)
    weighted = consensus_from_fields(row, WEIGHTED_POSITION_FIELDS)

    direction = unweighted["direction"]
    weighted_direction = weighted["direction"]
    shift = ""
    if direction and weighted_direction:
        shift = "yes" if direction != weighted_direction else "no"

    return {
        **row,
        "consensus_direction": direction,
        "consensus_score": unweighted["score"],
        "consensus_bucket": unweighted["bucket"],
        "confidence_weighted_direction": weighted_direction,
        "confidence_weighted_score": weighted["score"],
        "confidence_weighted_bucket": weighted["bucket"],
        "confidence_weighted_shift": shift,
    }


def consensus_from_fields(row: dict[str, str], fields: dict[str, str]) -> dict[str, str]:
    shares: list[tuple[str, float]] = []
    for position, field in fields.items():
        value = parse_float(row.get(field, ""))
        if value is None:
            return {"direction": "", "score": "", "bucket": ""}
        shares.append((position, value))

    shares.sort(key=lambda item: item[1], reverse=True)
    top_position, top_share = shares[0]
    _, second_share = shares[1]
    score = max(0.0, top_share - second_share)
    return {
        "direction": top_position,
        "score": f"{score:.6f}",
        "bucket": bucket_for_score(score),
    }


def bucket_for_score(score: float) -> str:
    if score < 0.15:
        return "No clear consensus"
    if score < 0.35:
        return "Weak consensus"
    if score < 0.60:
        return "Moderate consensus"
    return "Strong consensus"


def add_percentile_fields(rows: list[dict[str, str]]) -> None:
    for source_field, output_field in PERCENTILE_FIELDS:
        percentile_ranks = percentile_ranks_for_field(rows, source_field)
        for row, percentile_rank in zip(rows, percentile_ranks, strict=True):
            row[output_field] = "" if percentile_rank is None else f"{percentile_rank:.2f}"


def percentile_ranks_for_field(
    rows: list[dict[str, str]], field: str
) -> list[float | None]:
    values: list[tuple[int, float]] = []
    for index, row in enumerate(rows):
        value = parse_float(row.get(field, ""))
        if value is not None:
            values.append((index, value))

    ranks: list[float | None] = [None] * len(rows)
    if not values:
        return ranks

    values.sort(key=lambda item: item[1])
    start = 0
    n = len(values)
    while start < n:
        end = start + 1
        while end < n and values[end][1] == values[start][1]:
            end += 1

        below = start
        tied = end - start
        percentile_rank = 100 * (below + 0.5 * tied) / n
        for index, _ in values[start:end]:
            ranks[index] = percentile_rank
        start = end

    return ranks


def parse_float(value: str) -> float | None:
    if value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = list(rows[0].keys()) if rows else NEW_FIELDS
    for field in NEW_FIELDS:
        if field not in fieldnames:
            fieldnames.append(field)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add simple consensus direction/score/bucket fields to statements.csv."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("statements.csv"),
        help="Input statements CSV.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("statements_consensus.csv"),
        help="Output CSV with added consensus fields.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
