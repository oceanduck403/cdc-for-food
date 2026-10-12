"""Canonical digital forms transcribed from the two supplied Word documents.

The JSON retains the original wording/options and source fingerprints. Blank
paper columns are represented by one dated submission, not invented questions.
No source document specifies a numeric score or clinical interpretation.
"""
import json
from pathlib import Path


CATALOG_REVISION = 1
DEMO_LIFESTYLE_TYPE = "healthy_lifestyle_self_check"
ORIGINAL_SURVEY_CATALOG = json.loads(
    Path(__file__).with_suffix(".json").read_text(encoding="utf-8")
)
ORIGINAL_SURVEY_TYPES = frozenset(t["type"] for t in ORIGINAL_SURVEY_CATALOG)
_QUESTIONS_BY_TYPE = {t["type"]: t["questions"] for t in ORIGINAL_SURVEY_CATALOG}
REGISTRATION_QUESTIONS = _QUESTIONS_BY_TYPE["weight_visit_registration"]
BASIC_INFO_QUESTIONS = _QUESTIONS_BY_TYPE["weight_basic_info"]
FIRST_VISIT_QUESTIONS = _QUESTIONS_BY_TYPE["weight_clinic_first"]
ANTI_OBESITY_QUESTIONS = _QUESTIONS_BY_TYPE["weight_anti_obesity"]
FOLLOW_UP_QUESTIONS = _QUESTIONS_BY_TYPE["weight_clinic_follow"]
