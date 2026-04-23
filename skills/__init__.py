"""
skills/__init__.py
==================
Skill registry: auto-discovers and registers all skills.
To add a new skill, just create skills/<name>/skill.py with a SKILL object.
No changes needed here.
"""
from __future__ import annotations
import importlib
import os
from typing import List
from core import intent

SKILL_REGISTRY: List[intent.Skill] = []


def load_all():
    """Auto-discover and register all skills in the skills/ directory."""
    skills_dir = os.path.dirname(__file__)
    for entry in sorted(os.listdir(skills_dir)):
        skill_path = os.path.join(skills_dir, entry, "skill.py")
        if not os.path.isfile(skill_path):
            continue
        module_name = f"skills.{entry}.skill"
        try:
            mod = importlib.import_module(module_name)
            if hasattr(mod, "SKILL"):
                sk = mod.SKILL
                intent.register(sk)
                SKILL_REGISTRY.append(sk)
        except Exception as e:
            print(f"[Skills] Failed to load '{entry}': {e}")

    return SKILL_REGISTRY