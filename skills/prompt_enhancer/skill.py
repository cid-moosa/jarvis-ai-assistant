"""
skills/prompt_enhancer/skill.py
===============================
Prompt Enhancer skill — structures and refines raw prompts using Claude Code rules.
Copies result to clipboard and prints it to the console.
"""
import re
import asyncio
import os
from core import voice, intent, logger, memory
from core.enhancer import PromptEnhancer

def _copy_to_clipboard(text: str) -> bool:
    """Zero-dependency Windows clipboard writer with cross-platform fallback."""
    try:
        import platform
        if platform.system() == "Windows":
            import ctypes
            # Open clipboard
            if not ctypes.windll.user32.OpenClipboard(None):
                return False
            ctypes.windll.user32.EmptyClipboard()
            # Allocate global memory (GMEM_MOVEABLE = 0x0002)
            h_cd = ctypes.windll.kernel32.GlobalAlloc(0x0002, len(text.encode('utf-16-le')) + 2)
            p_cd = ctypes.windll.kernel32.GlobalLock(h_cd)
            ctypes.cdll.msvcrt.wcscpy(ctypes.c_wchar_p(p_cd), text)
            ctypes.windll.kernel32.GlobalUnlock(h_cd)
            # Set clipboard data (CF_UNICODETEXT = 13)
            ctypes.windll.user32.SetClipboardData(13, h_cd)
            ctypes.windll.user32.CloseClipboard()
            return True
        else:
            import pyperclip
            pyperclip.copy(text)
            return True
    except Exception:
        try:
            import pyperclip
            pyperclip.copy(text)
            return True
        except Exception:
            return False

def _parse(cmd: str) -> str:
    c = cmd.lower().strip()
    
    # Check if user wants to enhance the last command
    if c in ["enhance that", "enhance last command", "optimize that", "improve that", "enhance the last command"]:
        return memory.get("last_command", "")
        
    for trigger in ["enhance prompt", "optimize prompt", "improve prompt", "enhance", "optimize", "improve"]:
        idx = c.find(trigger)
        if idx != -1:
            return cmd[idx + len(trigger):].strip()
            
    return ""

def handle(cmd: str, config: dict):
    log = logger.get()
    raw_prompt = _parse(cmd)
    
    if not raw_prompt:
        voice.speak("I couldn't find a prompt to enhance.")
        return
        
    voice.speak("Enhancing your prompt...")
    
    enhancer = PromptEnhancer()
    
    # Run the async enhance method synchronously
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(enhancer.enhance(
            prompt=raw_prompt,
            detail_level="detailed",
            tone="professional",
            use_llm=True,
            archetype="developer_agent",
            include_rules=["minimal_complexity", "output_efficiency", "blast_radius", "strict_verification"]
        ))
    except Exception as e:
        log.error(f"Prompt Enhancer skill error: {e}")
        voice.speak("I encountered an error enhancing your prompt.")
        return
    finally:
        loop.close()
        
    enhanced_text = result.get("enhanced", "")
    if not enhanced_text:
        voice.speak("I was unable to generate an enhanced prompt.")
        return
        
    # Copy to clipboard
    copied = _copy_to_clipboard(enhanced_text)
        
    # Log and broadcast to WebUI if server is running
    log.info(f"Enhanced prompt for: {raw_prompt[:30]}...")
    
    # Print to console and output log
    try:
        from core import server as srv
        srv.broadcast({
            "event": "llm_chunk", 
            "text": f"\n\n[ENHANCED PROMPT (Copied to Clipboard)]:\n\n{enhanced_text}\n"
        })
    except Exception:
        pass
        
    if copied:
        voice.speak("Enhanced prompt has been copied to your clipboard.")
    else:
        voice.speak("I have enhanced your prompt. You can see it in the console.")

SKILL = intent.Skill(
    name        = "prompt_enhancer",
    handler     = handle,
    description = "Enhance prompts using Claude Code structure. Copies result to clipboard.",
    keywords    = ["enhance", "optimize", "improve prompt", "enhance prompt"],
    patterns    = [
        intent.IntentPattern("enhance",             85),
        intent.IntentPattern("enhance prompt",      95),
        intent.IntentPattern("optimize prompt",     95),
        intent.IntentPattern("improve prompt",      95),
        intent.IntentPattern("enhance that",        90),
    ],
)
