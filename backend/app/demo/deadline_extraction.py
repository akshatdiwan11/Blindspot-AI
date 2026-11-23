"""Synthetic benchmark: application-deadline extraction with planted failure patterns.

SYNTHETIC DATA. Every record is generated from templates with a fixed random seed, and
the "actual output" is produced by a simulated model whose error probability depends on
planted conditions. The planted conditions are recorded per case so that discovery results
can be scored against ground truth.

Planted patterns (error probability added on top of a small base rate):
  multi_date      document mentions a publication date and an event date besides the deadline;
                  the simulated model often returns the first date in the text
  hindi           document written in Hindi; the simulated model often swaps day and month
  unusual_format  table-like or all-caps layout; the simulated model often drops the year
  long_document   very long notice; the simulated model sometimes returns "Not found"
  mixed_language  Hindi-English mix; small effect, included as a hard-to-detect pattern
"""
from __future__ import annotations

import random
from datetime import date, timedelta

SEED = 20251123
N_RECORDS = 900

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
HINDI_MONTHS = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]

DOC_TYPES = {
    "Scholarship": ("Merit Scholarship {year}", "scholarship applications", "छात्रवृत्ति"),
    "Admission": ("Postgraduate Admissions {year}", "admission forms", "प्रवेश"),
    "Internship": ("Summer Research Internship {year}", "internship applications", "इंटर्नशिप"),
    "Fellowship": ("Doctoral Fellowship {year}", "fellowship nominations", "फ़ेलोशिप"),
    "Exam Notice": ("Entrance Examination {year}", "exam registrations", "परीक्षा पंजीकरण"),
}
ORGS = ["National Institute of Sciences", "State Education Board", "Riverside University", "Institute of Technology, Pune",
        "Central Research Council", "Lakeview College", "Department of Higher Education", "Eastern Arts Foundation"]
SOURCES = ["PDF", "Web", "Email", "Scan"]
FILLER = [
    "Candidates must upload scanned copies of all certificates in PDF format.",
    "Incomplete applications will not be considered under any circumstances.",
    "The selection committee's decision will be final and binding.",
    "Applicants are advised to keep a printout of the submitted form for future reference.",
    "Eligibility criteria include a minimum aggregate score as specified in the prospectus.",
    "Reserved category candidates must attach a valid category certificate.",
    "For technical issues, write to the helpdesk with your registration number.",
    "Shortlisted candidates will be informed by email and through the official portal.",
    "The institute reserves the right to modify the schedule without prior notice.",
    "Stipend and other benefits will be disbursed as per institutional norms.",
]
HINDI_FILLER = [
    "सभी प्रमाणपत्रों की स्कैन की गई प्रतियाँ अपलोड करना अनिवार्य है।",
    "अपूर्ण आवेदनों पर विचार नहीं किया जाएगा।",
    "चयन समिति का निर्णय अंतिम होगा।",
    "आवेदक भविष्य के संदर्भ के लिए फ़ॉर्म की प्रति सुरक्षित रखें।",
]

ERROR_RATES = {"base": 0.015, "multi_date": 0.40, "hindi": 0.30, "unusual_format": 0.26, "long_document": 0.15, "mixed_language": 0.07}
PREVALENCE = {"multi_date": 0.18, "hindi": 0.13, "mixed_language": 0.12, "unusual_format": 0.11, "long_document": 0.16}


def fmt_en(d: date) -> str:
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def fmt_hi(d: date) -> str:
    return f"{d.day} {HINDI_MONTHS[d.month - 1]} {d.year}"


def _english_doc(rng, title, org, what, deadline, pub, exam, multi, long_doc, unusual):
    lines = [f"{org}", f"{title}", ""]
    if multi:
        lines.append(f"Notice issued on {fmt_en(pub)}.")
    lines.append(f"Online {what} are invited from eligible candidates.")
    if multi:
        lines.append(f"The written test will be held on {fmt_en(exam)} at designated centres.")
    lines.append(f"The last date for submission of {what} is {fmt_en(deadline)}.")
    k = rng.randint(14, 22) if long_doc else rng.randint(1, 3)
    body = rng.sample(FILLER, k) if k <= len(FILLER) else rng.sample(FILLER, len(FILLER)) + [rng.choice(FILLER) for _ in range(k - len(FILLER))]
    lines.extend(body)
    if unusual:
        if rng.random() < 0.5:
            rows = [f"| Item | Detail |", f"| Organisation | {org} |", f"| Programme | {title} |"]
            if multi:
                rows.append(f"| Issued | {fmt_en(pub)} |")
                rows.append(f"| Test date | {fmt_en(exam)} |")
            rows.append(f"| Closing date | {fmt_en(deadline)} |")
            rows.append(f"| Notes | {body[0]} |")
            return "\n".join(rows)
        return "\n".join(lines).upper()
    return "\n".join(lines)


def _hindi_doc(rng, title, org, what_hi, deadline, pub, exam, multi, long_doc, mixed):
    lines = [org, title, ""]
    if multi:
        lines.append(f"सूचना जारी करने की तिथि: {fmt_hi(pub)}।")
    if mixed:
        lines.append(f"Eligible candidates से {what_hi} के लिए online applications आमंत्रित हैं।")
        if multi:
            lines.append(f"Written test {fmt_en(exam)} को होगा।")
        lines.append(f"Last date for submission: {fmt_en(deadline)}।")
    else:
        lines.append(f"योग्य उम्मीदवारों से {what_hi} हेतु ऑनलाइन आवेदन आमंत्रित किए जाते हैं।")
        if multi:
            lines.append(f"लिखित परीक्षा {fmt_hi(exam)} को आयोजित की जाएगी।")
        lines.append(f"आवेदन जमा करने की अंतिम तिथि {fmt_hi(deadline)} है।")
    k = rng.randint(14, 22) if long_doc else rng.randint(1, 3)
    pool = FILLER + HINDI_FILLER if mixed else HINDI_FILLER
    lines.extend(rng.choice(pool) for _ in range(k))
    return "\n".join(lines)


def generate(seed: int = SEED, n: int = N_RECORDS) -> tuple[list[dict], list[dict]]:
    """Returns (records, ground_truth_labels)."""
    rng = random.Random(seed)
    records, labels = [], []
    for i in range(1, n + 1):
        doc_type = rng.choice(list(DOC_TYPES))
        title_t, what, what_hi = DOC_TYPES[doc_type]
        year = rng.choice([2024, 2025])
        title = title_t.format(year=year)
        org = rng.choice(ORGS)
        pub = date(year, rng.randint(1, 9), rng.randint(1, 28))
        deadline = pub + timedelta(days=rng.randint(20, 75))
        exam = deadline + timedelta(days=rng.randint(10, 40))

        lang_roll = rng.random()
        hindi = lang_roll < PREVALENCE["hindi"]
        mixed = (not hindi) and lang_roll < PREVALENCE["hindi"] + PREVALENCE["mixed_language"]
        language = "Hindi" if hindi else ("Mixed" if mixed else "English")
        multi = rng.random() < PREVALENCE["multi_date"]
        long_doc = rng.random() < PREVALENCE["long_document"]
        unusual = (language == "English") and rng.random() < PREVALENCE["unusual_format"] / 0.75
        source = "Scan" if unusual and rng.random() < 0.5 else rng.choice(SOURCES)

        if language == "English":
            text = _english_doc(rng, title, org, what, deadline, pub, exam, multi, long_doc, unusual)
        else:
            text = _hindi_doc(rng, title, org, what_hi, deadline, pub, exam, multi, long_doc, mixed)
        pages = (rng.randint(4, 9) if long_doc else rng.randint(1, 2))

        active = {"multi_date": multi, "hindi": hindi, "unusual_format": unusual, "long_document": long_doc, "mixed_language": mixed}
        p_ok = 1 - ERROR_RATES["base"]
        for name, on in active.items():
            if on:
                p_ok *= 1 - ERROR_RATES[name]
        expected = fmt_en(deadline)
        mechanism = ""
        actual = expected
        if rng.random() > p_ok:
            # Attribute the error to one of the active mechanisms, weighted by their strength.
            causes = [k for k, on in active.items() if on] or ["base"]
            weights = [ERROR_RATES[c] for c in causes]
            mechanism = rng.choices(causes, weights=weights)[0]
            if mechanism == "multi_date":
                actual = fmt_en(pub)  # picked the first date in the document
            elif mechanism == "hindi":
                if deadline.day <= 12 and deadline.day != deadline.month:
                    actual = fmt_en(date(deadline.year, deadline.day, min(deadline.month, 28)))
                else:
                    actual = f"{deadline.day}/{deadline.month}"
            elif mechanism == "unusual_format":
                actual = f"{deadline.day} {MONTHS[deadline.month - 1][:3]}"
            elif mechanism == "long_document":
                actual = "Not found"
            elif mechanism == "mixed_language":
                actual = fmt_en(deadline - timedelta(days=1))
            else:
                actual = fmt_en(deadline + timedelta(days=rng.choice([-7, 1, 30])))

        case_id = f"DL-{i:04d}"
        records.append({
            "case_id": case_id,
            "input_text": f"Extract the application deadline from this notice.\n\n{text}",
            "expected_output": expected,
            "actual_output": actual,
            "language": language,
            "document_type": doc_type,
            "source": source,
            "page_count": pages,
        })
        labels.append({"case_id": case_id, **{k: int(v) for k, v in active.items()}, "error_injected": int(bool(mechanism)), "error_mechanism": mechanism or ""})
    return records, labels


BENCHMARK = {
    "name": "Deadline extraction benchmark (synthetic)",
    "synthetic": True,
    "seed": SEED,
    "records": N_RECORDS,
    "task": "text",
    "description": "A simulated extraction model reads scholarship, admission and exam notices and returns the application deadline. "
                   "Errors were injected with known probabilities under the planted conditions below.",
    "planted_patterns": [
        {"id": "multi_date", "description": "Document contains a publication date and an exam date besides the deadline", "injected_error_rate": ERROR_RATES["multi_date"],
         "mechanism": "returns the first date in the text (publication date)", "expected_detection": {"feature": "date_mentions", "op": ">=", "value": 2}},
        {"id": "hindi", "description": "Document is written in Hindi", "injected_error_rate": ERROR_RATES["hindi"],
         "mechanism": "swaps day and month, or returns a bare day/month", "expected_detection": {"feature": "language", "op": "==", "value": "Hindi"}},
        {"id": "unusual_format", "description": "Table-like or all-caps layout", "injected_error_rate": ERROR_RATES["unusual_format"],
         "mechanism": "drops the year and abbreviates the month", "expected_detection": {"feature": "input_format", "op": "in", "value": ["table_like", "mostly_uppercase"]}},
        {"id": "long_document", "description": "Long notice (many paragraphs, 4+ pages)", "injected_error_rate": ERROR_RATES["long_document"],
         "mechanism": "returns 'Not found'", "expected_detection": {"feature": "page_count", "op": ">=", "value": 4}},
        {"id": "mixed_language", "description": "Hindi-English mixed document", "injected_error_rate": ERROR_RATES["mixed_language"],
         "mechanism": "off-by-one-day deadline", "expected_detection": {"feature": "language", "op": "==", "value": "Mixed"}, "note": "weak effect; may legitimately be reported as tentative or not at all"},
    ],
    "base_error_rate": ERROR_RATES["base"],
}
