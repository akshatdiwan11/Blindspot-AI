"""Synthetic benchmark: invoice field extraction to JSON with planted weaknesses.

SYNTHETIC DATA generated with a fixed seed. Planted patterns:
  scanned        scanned invoices: total often missing or misread, sometimes invalid JSON
  foreign_ccy    non-INR invoices: currency often defaulted to "INR"
  multi_page     multi-page invoices: invoice number taken from the wrong page
"""
from __future__ import annotations

import json
import random

SEED = 4417
N_RECORDS = 500
VENDORS = ["Acme Supplies", "Northwind Traders", "Blue Ocean Logistics", "Sunrise Stationers", "Zenith Cloud Services", "Kaveri Foods"]


def generate(seed: int = SEED, n: int = N_RECORDS) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    records, truth = [], []
    for i in range(1, n + 1):
        vendor = rng.choice(VENDORS)
        inv = f"INV-{rng.randint(1000, 9999)}"
        ccy = rng.choices(["INR", "USD", "EUR"], [0.75, 0.15, 0.10])[0]
        total = round(rng.uniform(500, 90000), 2)
        day, month = rng.randint(1, 28), rng.randint(1, 12)
        date = f"2025-{month:02d}-{day:02d}"
        source = rng.choices(["Digital PDF", "Scan", "Email body"], [0.6, 0.25, 0.15])[0]
        pages = rng.choices([1, 2, 3], [0.7, 0.2, 0.1])[0]
        text = (f"{vendor}\nTax Invoice No: {inv}\nInvoice date: {day:02d}/{month:02d}/2025\n"
                + "".join(f"Page {p} of {pages} ... continued (ref INV-{rng.randint(1000, 9999)})\n" for p in range(2, pages + 1))
                + f"Amount due: {ccy} {total:,.2f}")
        expected = {"vendor": vendor, "invoice_number": inv, "date": date, "total": total, "currency": ccy}
        actual = dict(expected)
        active = {"scanned": source == "Scan", "foreign_ccy": ccy != "INR", "multi_page": pages > 1}
        mech = ""
        invalid = rng.random() < (0.08 if active["scanned"] else 0.01)
        if active["scanned"] and rng.random() < 0.30:
            mech = "scanned"
            if rng.random() < 0.5:
                actual.pop("total")
            else:
                actual["total"] = round(total / 10, 2)
        if active["foreign_ccy"] and rng.random() < 0.40:
            mech = mech or "foreign_ccy"
            actual["currency"] = "INR"
        if active["multi_page"] and rng.random() < 0.30:
            mech = mech or "multi_page"
            actual["invoice_number"] = f"INV-{rng.randint(1000, 9999)}"
        if not mech and rng.random() < 0.03:
            mech = "base"
            actual["date"] = f"2025-{day:02d}-{month:02d}" if day <= 12 else date[:-2] + f"{(day % 28) + 1:02d}"
        out = json.dumps(actual)
        if invalid:
            mech = mech or "scanned"
            out = out[:-8]  # truncated generation
        cid = f"INV-CASE-{i:04d}"
        records.append({"id": cid, "document_text": text, "expected_json": json.dumps(expected), "model_json": out,
                        "source": source, "pages": pages, "vendor_region": rng.choice(["North", "South", "West", "East"])})
        truth.append({"case_id": cid, **{k: int(v) for k, v in active.items()}, "error_injected": int(bool(mech)), "error_mechanism": mech})
    return records, truth


BENCHMARK = {
    "name": "Invoice JSON extraction benchmark (synthetic)", "synthetic": True, "seed": SEED, "records": N_RECORDS, "task": "json",
    "planted_patterns": [
        {"id": "scanned", "expected_detection": {"feature": "source", "op": "==", "value": "Scan"}},
        {"id": "foreign_ccy", "expected_detection": {"feature": "number_mentions", "op": "n/a", "value": "currency is only visible in text"}},
        {"id": "multi_page", "expected_detection": {"feature": "pages", "op": ">=", "value": 2}},
    ],
}
