"""Generate a deterministic 50,000-row sales fixture.

The amounts vary widely across rows and the first few rows are deliberately
SMALL, so a 5-row sample sum differs OBSERVABLY from the full-data sum. This is
what proves the agent computed on ALL rows, not just the sampled preview.

Run:  uv run python tests/fixtures/make_sales_50k.py
"""
from __future__ import annotations

import csv
import random
from pathlib import Path

N_ROWS = 50_000
REGIONS = ["North", "South", "East", "West"]
PRODUCTS = ["Widget", "Gadget", "Gizmo", "Doohickey", "Sprocket"]
OUT = Path(__file__).parent / "sales_50k.csv"


def generate() -> Path:
    rng = random.Random(20240701)  # fixed seed → fully reproducible
    rows = []
    for i in range(N_ROWS):
        region = REGIONS[i % len(REGIONS)]
        product = PRODUCTS[(i * 7) % len(PRODUCTS)]
        # First 5 rows tiny; the rest range widely (10 .. 9,999) so the head
        # sample is nowhere near representative of the full-data total.
        if i < 5:
            amount = round(1.0 + i * 0.5, 2)
        else:
            amount = round(rng.uniform(10.0, 9999.0), 2)
        quantity = 1 if i < 5 else rng.randint(1, 50)
        day = (i % 28) + 1
        month = (i % 12) + 1
        date = f"2024-{month:02d}-{day:02d}"
        rows.append([region, product, amount, quantity, date])

    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["region", "product", "amount", "quantity", "date"])
        w.writerows(rows)
    return OUT


if __name__ == "__main__":
    path = generate()
    print(f"Wrote {path} ({path.stat().st_size} bytes)")
