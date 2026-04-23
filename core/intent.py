"""
core/intent.py
==============
Fully LOCAL, zero-cost intent classifier.
No LLM, no API, no internet required.

Uses a 3-stage pipeline:
  1. Exact phrase match (fastest)
  2. Token overlap scoring (handles word order variation)
  3. RapidFuzz partial ratio (handles mispronunciation / typos)

Each skill registers its own intent patterns via register().
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, List, Tuple
from rapidfuzz import fuzz
import re

@dataclass
class IntentPattern:
    phrase:     str
    confidence: int          # base confidence (0-100)

@dataclass
class Skill:
    name:        str
    handler:     Callable
    patterns:    List[IntentPattern] = field(default_factory=list)
    keywords:    List[str]          = field(default_factory=list)
    description: str                = ""

_registry: List[Skill] = []


def register(skill: Skill):
    _registry.append(skill)


def _tokenize(text: str) -> set:
    return set(re.findall(r"\b\w+\b", text.lower()))


def _score(text: str, skill: Skill) -> Tuple[int, str]:
    """Return (best_score, matched_phrase) for this skill against the input text."""
    text_lc = text.lower()
    best = 0
    best_phrase = ""

    for pat in skill.patterns:
        phrase_lc = pat.phrase.lower()

        # Stage 1: Exact substring
        if phrase_lc in text_lc:
            score = pat.confidence
            if score > best:
                best, best_phrase = score, pat.phrase
            continue

        # Stage 2: Token overlap
        text_tokens   = _tokenize(text)
        phrase_tokens = _tokenize(phrase_lc)
        if phrase_tokens:
            overlap = len(text_tokens & phrase_tokens) / len(phrase_tokens)
            tok_score = int(overlap * pat.confidence * 0.85)
            if tok_score > best:
                best, best_phrase = tok_score, pat.phrase

        # Stage 3: Fuzzy (catches mispronounced words)
        fuzzy = fuzz.partial_ratio(phrase_lc, text_lc)
        fuzz_score = int(fuzzy * pat.confidence / 100)
        if fuzz_score > best:
            best, best_phrase = fuzz_score, pat.phrase

    # Bonus for keyword presence
    text_tokens = _tokenize(text)
    kw_hits = sum(1 for k in skill.keywords if k.lower() in text_tokens)
    best += kw_hits * 5

    return min(best, 100), best_phrase


def classify(text: str) -> Tuple[Skill | None, int, str]:
    """
    Classify text into the best matching skill.
    Returns (skill, score, matched_phrase).
    Returns (None, 0, '') if no skill scores >= 60.
    """
    if not text.strip():
        return None, 0, ""

    results = []
    for skill in _registry:
        score, phrase = _score(text, skill)
        results.append((score, skill, phrase))

    results.sort(key=lambda x: x[0], reverse=True)

    if results and results[0][0] >= 60:
        score, skill, phrase = results[0]
        return skill, score, phrase

    return None, 0, ""