import json

import pytest

from app.core.errors import ValidationFailed
from app.services.profiling import build_profile, guess_mapping, infer_dtype
from app.utils.parsing import parse_upload


def test_csv_parses_and_keeps_strings(sample_csv):
    fmt, p = parse_upload(sample_csv, "data.csv", max_rows=100)
    assert fmt == "csv"
    assert p.columns[:3] == ["case_id", "input_text", "expected_output"]
    assert len(p.rows) == 4
    assert p.rows[0]["expected_output"] == "15 December"


def test_csv_reports_ragged_rows():
    raw = b"a,b\n1,2\n3\n4,5\n"
    _, p = parse_upload(raw, "x.csv", max_rows=100)
    assert len(p.rows) == 2
    assert p.invalid_rows == [{"line": 3, "reason": "expected 2 fields, found 1"}]


def test_jsonl_with_bad_line():
    raw = b'{"a": 1, "b": {"x": 2}}\nnot json\n{"a": 3}\n'
    fmt, p = parse_upload(raw, "x.jsonl", max_rows=100)
    assert fmt == "jsonl"
    assert len(p.rows) == 2
    assert p.rows[0]["b"] == json.dumps({"x": 2})
    assert p.rows[1]["b"] is None
    assert p.invalid_rows[0]["line"] == 2


def test_json_object_with_records_key():
    raw = json.dumps({"records": [{"q": "x", "a": "y"}]}).encode()
    _, p = parse_upload(raw, "x.json", max_rows=100)
    assert p.rows == [{"q": "x", "a": "y"}]


@pytest.mark.parametrize("raw,name,msg", [
    (b"", "x.csv", "empty"),
    (b"a,b\n1,2", "x.exe", "Unsupported file type"),
    (b"a,a\n1,2", "x.csv", "Duplicate column"),
    (b"\x00\x01\x02binary", "x.csv", "binary"),
    (b"[1, 2", "x.json", "Invalid JSON"),
    (b"\xff\xfe\xfa", "x.csv", "UTF-8"),
])
def test_invalid_uploads_have_clear_errors(raw, name, msg):
    with pytest.raises(ValidationFailed) as e:
        parse_upload(raw, name, max_rows=100)
    assert msg in e.value.message


def test_row_limit_enforced():
    raw = ("a\n" + "\n".join(str(i) for i in range(20))).encode()
    with pytest.raises(ValidationFailed, match="more than 10"):
        parse_upload(raw, "x.csv", max_rows=10)


def test_uploaded_text_is_never_executed():
    raw = b'a,b\n"__import__(\'os\').system(\'echo pwned\')","=cmd|\' /C calc\'!A0"\n'
    _, p = parse_upload(raw, "x.csv", max_rows=10)
    assert p.rows[0]["a"].startswith("__import__")  # kept as inert text


def test_profile_and_mapping_guess(sample_csv):
    _, p = parse_upload(sample_csv, "x.csv", max_rows=100)
    prof = build_profile(p.columns, p.rows, p.invalid_rows, [])
    assert prof["total_records"] == 4
    assert prof["missing_values"] == 0
    m = prof["suggested_mapping"]
    assert m["expected_column"] == "expected_output"
    assert m["actual_column"] == "actual_output"
    assert m["input_column"] == "input_text"
    assert m["case_id_column"] == "case_id"


def test_dtype_inference():
    assert infer_dtype(["1", "2.5", "-3"]) == "numeric"
    assert infer_dtype(["true", "false", "yes"]) == "boolean"
    assert infer_dtype(['{"a":1}', "[1]"]) == "json"
    assert infer_dtype(["a", "b", "a"]) == "categorical"
    assert guess_mapping([])["expected_column"] is None
