from __future__ import annotations

from .util import clean_text


VOTE_NORMALIZED_VALUES = [
    "Strongly Agree",
    "Agree",
    "Uncertain",
    "Disagree",
    "Strongly Disagree",
    "No Opinion",
    "Did Not Answer / Missing",
    "Other / Not Applicable",
]

AGREEMENT_ORDER = [
    "Strongly Agree",
    "Agree",
    "Uncertain",
    "Disagree",
    "Strongly Disagree",
    "No Opinion",
    "Did Not Answer / Missing",
    "Other / Not Applicable",
]


def normalize_vote(value: str) -> str:
    raw = clean_text(value)
    lowered = raw.lower()
    if not raw:
        return "Did Not Answer / Missing"
    mapping = {
        "strongly agree": "Strongly Agree",
        "agree": "Agree",
        "uncertain": "Uncertain",
        "disagree": "Disagree",
        "strongly disagree": "Strongly Disagree",
        "no opinion": "No Opinion",
        "did not answer": "Did Not Answer / Missing",
        "did not aswer": "Did Not Answer / Missing",
        "did not answer / missing": "Did Not Answer / Missing",
        "did not vote": "Did Not Answer / Missing",
        "missing": "Did Not Answer / Missing",
        "no opinion0": "No Opinion",
        "n/a": "Other / Not Applicable",
        "na": "Other / Not Applicable",
        "not applicable": "Other / Not Applicable",
    }
    if lowered in mapping:
        return mapping[lowered]
    if lowered in {"0", "1", "2", "3", "4", "5"}:
        return "Other / Not Applicable"
    return "Other / Not Applicable"


def parse_confidence(value: str) -> str:
    raw = clean_text(value)
    if not raw:
        return ""
    try:
        number = float(raw)
    except ValueError:
        return ""
    if number.is_integer():
        return str(int(number))
    return str(number)
