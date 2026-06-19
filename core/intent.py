"""
core/intent.py
==============
Hybrid intent classifier: LOCAL-first (RapidFuzz 3-stage pipeline),
then LLM fallback (Gemini) if no local skill scores >= 60.

Existing logic (exact match, token overlap, fuzzy ratio, keyword bonus)
is 100% preserved. The LLM layer only fires on a miss.
"""
from __future__ import annotations
import threading
import warnings
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
_config: dict = {}
_config_lock = threading.Lock()


def setup(config: dict):
    global _config
    with _config_lock:
        _config = config


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
    The caller should route (None, ...) to llm_fallback().
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


def llm_fallback(text: str, config: dict | None = None) -> str:
    """
    Route an unmatched query to the Gemini generative AI API.
    Streams response chunks into the WebSocket broadcast queue.
    Returns the full response text (or an error string on failure).

    Graceful degradation:
      - Missing API key  -> returns instructions string without crashing.
      - Network failure  -> returns error string without crashing.
      - Library missing  -> returns error string without crashing.
    """
    from core import memory, logger as log_mod

    cfg = config or {}
    log = log_mod.get()

    api_key = memory.get_api_key("gemini")
    if not api_key:
        msg = ("I don't have a Gemini API key configured yet. "
               "Open the settings panel in the web interface to add one.")
        log.warning("LLM fallback: no Gemini API key in memory.")
        return msg

    model_name = cfg.get("llm_model", "gemini-1.5-flash")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=FutureWarning)
            import google.generativeai as genai
    except ImportError:
        msg = "The google-generativeai package is not installed. Run: pip install google-generativeai"
        log.error(msg)
        return msg

    try:
        # Stream the response
        response_chunks: List[str] = []
        try:
            from core import server as _srv
            broadcast = _srv.broadcast
        except Exception:
            broadcast = None  # server not yet started -- stream silently

        system_ctx = (
            "You are Jarvis, a sharp and helpful AI assistant. "
            "Give concise, direct answers. Avoid markdown in spoken responses."
        )
        full_prompt = f"{system_ctx}\n\nUser: {text}\nJarvis:"

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=FutureWarning)
            genai.configure(api_key=api_key)
            model_obj = genai.GenerativeModel(model_name)
            response = model_obj.generate_content(full_prompt, stream=True)
            for chunk in response:
                chunk_text = getattr(chunk, "text", "") or ""
                if chunk_text:
                    response_chunks.append(chunk_text)
                    if broadcast:
                        try:
                            broadcast({"event": "llm_chunk", "text": chunk_text})
                        except Exception:
                            pass

        full_response = "".join(response_chunks).strip()
        if not full_response:
            full_response = "I wasn't able to generate a response. Please try again."
        return full_response

    except Exception as exc:
        log.error(f"LLM fallback error: {exc}")
        return f"I encountered an error reaching the AI: {exc}"