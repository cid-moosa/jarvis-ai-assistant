"""
skills/calculator/skill.py
==========================
Math expression evaluator — fully local, zero dependencies beyond stdlib.
Handles percentages, basic arithmetic, square roots safely.
"""
import re
import math
from core import voice, intent, logger


_SAFE_NAMES = {
    "sqrt": math.sqrt, "pi": math.pi, "e": math.e,
    "abs": abs, "round": round, "pow": pow,
}


def _parse(cmd: str) -> str:
    c = cmd.lower()
    # Extract expression after trigger words
    for trigger in ["calculate", "what is", "what's", "how much is", "compute", "solve"]:
        idx = c.find(trigger)
        if idx != -1:
            c = c[idx + len(trigger):]
            break

    # Word-to-operator replacements
    replacements = {
        r"\btimes\b":     "*",
        r"\bmultiplied by\b": "*",
        r"\bdivided by\b": "/",
        r"\bplus\b":      "+",
        r"\bminus\b":     "-",
        r"\bto the power of\b": "**",
        r"\bsquare root of\b": "sqrt(",
        r"\bpercent of\b": "/100*",
    }
    for pattern, repl in replacements.items():
        c = re.sub(pattern, repl, c)

    # Fix dangling sqrt( 
    if "sqrt(" in c and ")" not in c[c.find("sqrt("):]:
        c += ")"

    # Keep only safe characters
    c = re.sub(r"[^0-9\+\-\*/\(\)\.\s]", "", c).strip()
    return c


def handle(cmd: str, config: dict):
    log = logger.get()
    expr = _parse(cmd)
    if not expr:
        voice.speak("I couldn't find a math expression to calculate.")
        return
    try:
        result = eval(expr, {"__builtins__": {}}, _SAFE_NAMES)  # sandboxed
        # Format result
        if isinstance(result, float):
            r_str = f"{result:.6g}"
        else:
            r_str = str(result)
        log.info(f"Calc: {expr} = {r_str}")
        voice.speak(f"The answer is {r_str}.")
    except ZeroDivisionError:
        voice.speak("You can't divide by zero.")
    except Exception as e:
        log.warning(f"Calc eval failed: {e} (expr: {expr})")
        voice.speak("I couldn't evaluate that expression.")


SKILL = intent.Skill(
    name        = "calculator",
    handler     = handle,
    description = "Local math evaluator. No API. Handles arithmetic, percentages, square roots.",
    keywords    = ["calculate", "compute", "math", "plus", "minus", "times", "divided", "percent", "square root"],
    patterns    = [
        intent.IntentPattern("calculate",           90),
        intent.IntentPattern("what is",             72),
        intent.IntentPattern("how much is",         85),
        intent.IntentPattern("compute",             88),
        intent.IntentPattern("times",               70),
        intent.IntentPattern("divided by",          75),
        intent.IntentPattern("square root",         88),
        intent.IntentPattern("percent of",          85),
    ],
)