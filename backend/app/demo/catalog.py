"""Registry of the bundled synthetic demo datasets."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any, Callable

from app.demo import deadline_extraction, email_triage, invoice_json


@dataclass(frozen=True)
class DemoSpec:
    key: str
    project_name: str
    description: str
    model_category: str
    task: str
    filename: str
    generate: Callable[[], tuple[list[dict], list[dict]]]
    mapping: dict[str, Any]
    benchmark: dict[str, Any]


DEMOS = {
    "deadline_extraction": DemoSpec(
        "deadline_extraction", "Deadline extraction (synthetic demo)",
        "SYNTHETIC BENCHMARK DATA. A simulated model extracts application deadlines from scholarship, admission and exam notices. "
        "Failure patterns were planted on purpose so you can see Blindspot AI find them.",
        "structured_extraction", "text", "deadline_extraction_benchmark.csv", deadline_extraction.generate,
        {"input_column": "input_text", "expected_column": "expected_output", "actual_column": "actual_output", "case_id_column": "case_id",
         "metadata_columns": ["language", "document_type", "source", "page_count"]},
        deadline_extraction.BENCHMARK),
    "email_triage": DemoSpec(
        "email_triage", "Support email triage (synthetic demo)",
        "SYNTHETIC BENCHMARK DATA. A simulated classifier routes support emails into five queues, with planted weaknesses.",
        "classification", "classification", "email_triage_benchmark.csv", email_triage.generate,
        {"input_column": "message", "expected_column": "true_label", "actual_column": "predicted_label", "case_id_column": "ticket_id",
         "metadata_columns": ["channel", "customer_tier", "language"]},
        email_triage.BENCHMARK),
    "invoice_json": DemoSpec(
        "invoice_json", "Invoice JSON extraction (synthetic demo)",
        "SYNTHETIC BENCHMARK DATA. A simulated model extracts invoice fields to JSON, with planted weaknesses.",
        "structured_extraction", "json", "invoice_json_benchmark.csv", invoice_json.generate,
        {"input_column": "document_text", "expected_column": "expected_json", "actual_column": "model_json", "case_id_column": "id",
         "metadata_columns": ["source", "pages", "vendor_region"]},
        invoice_json.BENCHMARK),
}


def to_csv_bytes(records: list[dict]) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(records[0].keys()))
    w.writeheader()
    w.writerows(records)
    return buf.getvalue().encode("utf-8")
