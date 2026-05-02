"""Render the consensus chart in three palette variants for side-by-side comparison."""
from pathlib import Path
from generate_consensus import load_statements, make_chart

ROOT = Path(__file__).parent

VARIANTS = [
    ("copper",   (("#fde68a", 0.0), ("#78350f", 1.0))),
    ("teal",     (("#99f6e4", 0.0), ("#134e4a", 1.0))),
    ("forest",   (("#bbf7d0", 0.0), ("#14532d", 1.0))),
    # diverging spectrum: red (low consensus) → amber → green (high consensus)
    ("spectrum", (("#dc2626", 0.0), ("#f59e0b", 0.5), ("#14532d", 1.0))),
    # magma: warm yellow → orange → red → purple → near-black
    ("magma",    (("#fde047", 0.0), ("#f97316", 0.35), ("#be123c", 0.65), ("#1e1b4b", 1.0))),
    # viridis: yellow → green → blue → purple (perceptually uniform feel)
    ("viridis",  (("#fde047", 0.0), ("#22c55e", 0.4), ("#0e7490", 0.7), ("#3b0764", 1.0))),
    # plum: pale lilac → deep violet
    ("plum",     (("#e9d5ff", 0.0), ("#4c1d95", 1.0))),
    # mono: ivory → near-black, high-contrast NYT feel
    ("mono",     (("#fafaf9", 0.0), ("#0a0a0a", 1.0))),
]


def main() -> None:
    stmts = load_statements()
    print(f"Loaded {len(stmts)} statements")
    for name, palette in VARIANTS:
        out = ROOT / f"consensus_{name}.html"
        out.write_text(make_chart(stmts, palette=palette), encoding="utf-8")
        print(f"wrote {out.name}")


if __name__ == "__main__":
    main()
