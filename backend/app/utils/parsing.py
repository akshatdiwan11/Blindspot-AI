"""Safe parsing of uploaded CSV / JSON / JSONL files into string records.

Uploaded content is untrusted data: it is parsed, never executed or evaluated, and
values are kept as strings (nested JSON values are serialised canonically).
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from typing import Any

from app.core.errors import ValidationFailed

SUPPORTED_FORMATS = ("csv", "json", "jsonl")
MAX_COLUMNS = 200
MAX_CELL_CHARS = 20000


@dataclass
class ParsedFile:
    columns: list[str]
    rows: list[dict[str, str | None]]
    invalid_rows: list[dict[str, Any]] = field(default_factory=list)  # {"line": n, "reason": "..."}
    warnings: list[str] = field(default_factory=list)


def detect_format(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "ndjson":
        ext = "jsonl"
    if ext not in SUPPORTED_FORMATS:
        raise ValidationFailed(f"Unsupported file type '.{ext or '?'}'. Upload a CSV, JSON or JSONL file.")
    return ext


def _decode(raw: bytes) -> str:
    if not raw.strip():
        raise ValidationFailed("The uploaded file is empty.")
    if b"\x00" in raw[:4096]:
        raise ValidationFailed("The file looks binary. Upload a UTF-8 text file (CSV, JSON or JSONL).")
    for enc in ("utf-8-sig", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValidationFailed("The file is not valid UTF-8 text. Re-save it with UTF-8 encoding.")


def _cell(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, bool):
        return "true" if value else "false"
    s = str(value)
    if not s.strip():
        return None
    return s[:MAX_CELL_CHARS]


def _check_columns(columns: list[str]) -> list[str]:
    cleaned = [c.strip() for c in columns]
    if not cleaned or all(not c for c in cleaned):
        raise ValidationFailed("No column headers were found.")
    if any(not c for c in cleaned):
        raise ValidationFailed("Every column needs a header name. At least one header is blank.")
    dupes = sorted({c for c in cleaned if cleaned.count(c) > 1})
    if dupes:
        raise ValidationFailed(f"Duplicate column names: {', '.join(dupes)}. Column names must be unique.")
    if len(cleaned) > MAX_COLUMNS:
        raise ValidationFailed(f"Too many columns ({len(cleaned)}). The limit is {MAX_COLUMNS}.")
    return cleaned


def _parse_csv(text: str, max_rows: int) -> ParsedFile:
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration as e:
        raise ValidationFailed("The CSV file has no header row.") from e
    except csv.Error as e:
        raise ValidationFailed(f"Could not read the CSV header: {e}") from e
    columns = _check_columns(header)
    rows: list[dict[str, str | None]] = []
    invalid: list[dict[str, Any]] = []
    line = 1
    try:
        for values in reader:
            line += 1
            if not values or all(not v.strip() for v in values):
                continue
            if len(values) != len(columns):
                invalid.append({"line": line, "reason": f"expected {len(columns)} fields, found {len(values)}"})
                continue
            rows.append({c: _cell(v) for c, v in zip(columns, values)})
            if len(rows) > max_rows:
                raise ValidationFailed(f"The file has more than {max_rows:,} rows, which is the current limit.")
    except csv.Error as e:
        raise ValidationFailed(f"The CSV is malformed near line {line}: {e}") from e
    return ParsedFile(columns, rows, invalid)


def _records_from_objects(objs: list[Any], max_rows: int, line_offset: int = 1) -> ParsedFile:
    columns: list[str] = []
    seen: set[str] = set()
    rows: list[dict[str, str | None]] = []
    invalid: list[dict[str, Any]] = []
    for i, obj in enumerate(objs):
        if not isinstance(obj, dict):
            invalid.append({"line": i + line_offset, "reason": "record is not a JSON object"})
            continue
        for k in obj:
            key = str(k).strip()
            if key not in seen:
                seen.add(key)
                columns.append(key)
        rows.append({str(k).strip(): _cell(v) for k, v in obj.items()})
        if len(rows) > max_rows:
            raise ValidationFailed(f"The file has more than {max_rows:,} records, which is the current limit.")
    if not columns:
        raise ValidationFailed("No records with fields were found in the file.")
    _check_columns(columns)
    for r in rows:
        for c in columns:
            r.setdefault(c, None)
    return ParsedFile(columns, rows, invalid)


def _parse_json(text: str, max_rows: int) -> ParsedFile:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValidationFailed(f"Invalid JSON at line {e.lineno}, column {e.colno}: {e.msg}. If each line is a separate record, use the .jsonl extension.") from e
    if isinstance(data, dict):
        for key in ("records", "data", "rows", "items", "examples"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            raise ValidationFailed("The JSON file must be a list of records, or an object with a 'records' or 'data' list.")
    if not isinstance(data, list):
        raise ValidationFailed("The JSON file must contain a list of records.")
    return _records_from_objects(data, max_rows, line_offset=0)


def _parse_jsonl(text: str, max_rows: int) -> ParsedFile:
    objs: list[Any] = []
    invalid: list[dict[str, Any]] = []
    line_map: list[int] = []
    for n, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            objs.append(json.loads(line))
            line_map.append(n)
        except json.JSONDecodeError as e:
            invalid.append({"line": n, "reason": f"invalid JSON: {e.msg}"})
        if len(objs) > max_rows:
            raise ValidationFailed(f"The file has more than {max_rows:,} records, which is the current limit.")
    parsed = _records_from_objects(objs, max_rows)
    for item in parsed.invalid_rows:  # map object index back to the file line
        idx = item["line"] - 1
        item["line"] = line_map[idx] if 0 <= idx < len(line_map) else item["line"]
    parsed.invalid_rows = invalid + parsed.invalid_rows
    return parsed


def parse_upload(raw: bytes, filename: str, *, max_rows: int) -> tuple[str, ParsedFile]:
    fmt = detect_format(filename)
    text = _decode(raw)
    parser = {"csv": _parse_csv, "json": _parse_json, "jsonl": _parse_jsonl}[fmt]
    parsed = parser(text, max_rows)
    if not parsed.rows:
        raise ValidationFailed("The file contains no valid records.", details={"invalid_rows": parsed.invalid_rows[:50]})
    return fmt, parsed
