from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass


def normalize_text(value: str) -> str:
    text = (value or "").strip().lower()
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("\u0111", "d")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def name_similarity(a: str, b: str) -> float:
    left = normalize_text(a)
    right = normalize_text(b)
    if not left or not right:
        return 0.0

    left_compact = left.replace(" ", "")
    right_compact = right.replace(" ", "")
    char_ratio = difflib.SequenceMatcher(None, left_compact, right_compact).ratio()

    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return char_ratio

    token_overlap = len(left_tokens & right_tokens) / float(max(len(left_tokens), len(right_tokens), 1))
    return (char_ratio * 0.7) + (token_overlap * 0.3)


@dataclass(frozen=True)
class ResolvedStudentName:
    resolved_name: str
    ocr_name: str
    matched_name: str
    name_source: str
    similarity: float


def resolve_student_name(db_name: str | None, ocr_name: str | None, threshold: float = 0.72) -> ResolvedStudentName:
    db_name = (db_name or "").strip()
    ocr_name = (ocr_name or "").strip()

    if not db_name and not ocr_name:
        return ResolvedStudentName("", "", "", "ocr", 0.0)

    if not db_name:
        return ResolvedStudentName(ocr_name, ocr_name, "", "ocr", 0.0)

    if not ocr_name:
        return ResolvedStudentName(db_name, "", db_name, "database", 1.0)

    score = name_similarity(db_name, ocr_name)
    if score >= threshold:
        return ResolvedStudentName(db_name, ocr_name, db_name, "database", score)

    return ResolvedStudentName(ocr_name, ocr_name, db_name, "ocr", score)
