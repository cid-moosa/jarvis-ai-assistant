import os
import re
from typing import Dict, Any, Optional, List
from core import memory

SYSTEM_PROMPT = """You are an expert Prompt Engineer. Your task is to transform a raw, basic, or poorly structured user prompt into a highly effective, production-grade agent prompt. 

Follow these optimization strategies:
1. **Assign a Role/Archetype**: Establish a clear persona, expertise level, and tone. If a specific developer archetype is requested, align the persona and style instructions accordingly.
2. **Inject Context & System Boundaries**: Clearly separate background information from the main task.
3. **Structured Format**: Use markdown headings (like Role, Task, Constraints, Tools, Output Format) or XML tags to cleanly organize the instructions.
4. **Be Specific & Explicit (Incorporate Rules)**: Define what to do and what *not* to do. Incorporate standard development rules like minimal complexity (anti-bloat), output efficiency (conciseness), blast radius considerations (confirmation of risky operations), and strict verification (verifying logic before claiming done).
5. **Tool Integration**: If tools are provided, explain how to use them, emphasizing dedicated tools over generic ones, and detail execution controls (e.g. parallel/sequential calls, handling user denials).
6. **Output Constraints**: Request specific formatting (e.g., JSON, markdown tables, bullet points) and style constraints.

Your output should contain ONLY the enhanced prompt. Do not add intro/outro comments like "Here is your enhanced prompt:". Start directly with the prompt content."""

# Rules definitions derived from Claude Code
CLAUDE_CODE_RULES = {
    "minimal_complexity": (
        "Don't add features, refactor code, or make 'improvements' beyond what was asked. "
        "A bug fix doesn't need surrounding code cleaned up. A simple feature doesn't need extra configurability. "
        "Don't create helpers, utilities, or abstractions for one-time operations. Don't design for hypothetical future requirements. "
        "Three similar lines of code is better than a premature abstraction."
    ),
    "output_efficiency": (
        "Go straight to the point. Try the simplest approach first. Be extra concise. "
        "Keep text output brief and direct. Lead with the answer or action, not the reasoning. "
        "Skip filler words, preamble, and unnecessary transitions. If you can say it in one sentence, don't use three."
    ),
    "blast_radius": (
        "Carefully consider the reversibility and blast radius of actions. Pause to confirm before taking any "
        "risky, destructive, or hard-to-reverse operations (e.g., deleting files, force-pushing, removing/downgrading packages, "
        "modifying shared infrastructure). Match the scope of your actions to what was actually requested."
    ),
    "strict_verification": (
        "Before reporting a task complete, verify it actually works: run tests, execute scripts, and check the output. "
        "Report outcomes faithfully: if tests fail, say so; never claim 'all tests pass' when the output shows failures. "
        "If you cannot verify, say so explicitly rather than claiming success."
    )
}

class PromptEnhancer:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or memory.get_api_key("anthropic") or os.environ.get("ANTHROPIC_API_KEY")
        self.client = None
        if self.api_key:
            # We lazy-import to avoid overhead if not used
            from anthropic import Anthropic
            self.client = Anthropic(api_key=self.api_key)

    async def enhance(
        self,
        prompt: str,
        detail_level: str = "detailed",
        tone: str = "professional",
        use_llm: bool = True,
        archetype: str = "general",
        include_rules: Optional[List[str]] = None,
        tools_list: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Enhances a raw prompt using either Anthropic's LLM or local heuristics.
        """
        if not prompt.strip():
            return {
                "original": prompt,
                "enhanced": "",
                "method": "none",
                "message": "Prompt is empty."
            }

        # Determine method to use
        actual_use_llm = use_llm and self.client is not None

        if actual_use_llm:
            try:
                enhanced_text = await self._enhance_with_llm(
                    prompt, detail_level, tone, archetype, include_rules, tools_list
                )
                return {
                    "original": prompt,
                    "enhanced": enhanced_text.strip(),
                    "method": "llm",
                    "message": "Enhanced successfully using Anthropic Claude."
                }
            except Exception as e:
                # Fallback to local enhancement if API call fails
                local_enhanced = self._enhance_local(
                    prompt, detail_level, tone, archetype, include_rules, tools_list
                )
                return {
                    "original": prompt,
                    "enhanced": local_enhanced,
                    "method": "local_fallback",
                    "message": f"LLM enhancement failed ({str(e)}). Fell back to local structuring."
                }
        else:
            local_enhanced = self._enhance_local(
                prompt, detail_level, tone, archetype, include_rules, tools_list
            )
            method_msg = (
                "Enhanced using local structure heuristics."
                if not use_llm
                else "Enhanced using local structure heuristics (No API key configured)."
            )
            return {
                "original": prompt,
                "enhanced": local_enhanced,
                "method": "local",
                "message": method_msg
            }

    async def _enhance_with_llm(
        self,
        prompt: str,
        detail_level: str,
        tone: str,
        archetype: str,
        include_rules: Optional[List[str]],
        tools_list: Optional[List[str]]
    ) -> str:
        """
        Calls Anthropic Claude to optimize the prompt.
        """
        user_content = (
            f"Enhance this prompt.\n"
            f"Target Tone: {tone}\n"
            f"Detail Level: {detail_level}\n"
            f"Archetype: {archetype}\n"
        )
        
        if include_rules:
            user_content += "Incorporate the following specific behavioral rules:\n"
            for rule in include_rules:
                rule_desc = CLAUDE_CODE_RULES.get(rule)
                if rule_desc:
                    user_content += f"- **{rule.replace('_', ' ').title()}**: {rule_desc}\n"
            
        if tools_list:
            user_content += "Incorporate guidelines and instructions for using the following tools:\n"
            for tool in tools_list:
                user_content += f"- {tool}\n"
            user_content += (
                "Ensure to instruct the agent to use dedicated tools over bash, support parallel tool execution "
                "when appropriate, and adapt if a tool execution is denied.\n"
            )

        user_content += f"\nRaw Prompt:\n{prompt}"
        
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2048,
            temperature=0.3,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_content}
            ]
        )
        return response.content[0].text

    def _enhance_local(
        self,
        prompt: str,
        detail_level: str,
        tone: str,
        archetype: str,
        include_rules: Optional[List[str]],
        tools_list: Optional[List[str]]
    ) -> str:
        """
        Performs heuristic-based enhancement of the prompt locally.
        """
        # Determine role based on archetype or fallback to inference
        if archetype == "developer_agent":
            role = "Senior Software Engineering Agent"
        elif archetype == "tui_assistant":
            role = "Interactive Terminal UI Assistant"
        else:
            role = self._infer_role(prompt)
        
        enhanced = f"# Role: {role}\n"
        enhanced += f"Act as an expert {role} with a {tone} tone. Deliver highly professional, precise, and correct outcomes.\n\n"
        
        enhanced += "## Context\n"
        enhanced += "Understand the following task and execute it accurately based on the instructions provided.\n\n"
        
        enhanced += "## Task\n"
        clean_prompt = prompt.strip()
        if clean_prompt:
            clean_prompt = clean_prompt[0].upper() + clean_prompt[1:]
        enhanced += f"{clean_prompt}\n\n"
        
        if tools_list:
            enhanced += "## Tools & Execution\n"
            enhanced += "You have access to the following tools:\n"
            for tool in tools_list:
                enhanced += f"- `{tool}`\n"
            enhanced += (
                "- Do NOT run generic bash commands when a relevant dedicated tool is available.\n"
                "- Parallelize independent tool calls where possible to maximize efficiency.\n"
                "- If the user or system denies a tool execution, analyze the reason and adjust your approach.\n\n"
            )

        enhanced += "## Constraints\n"
        enhanced += "- Do not use placeholders or generic responses.\n"
        enhanced += "- Ensure factual accuracy and logical coherence.\n"
        enhanced += "- Refrain from conversational filler (e.g., 'Sure, here is...'); start directly with the results.\n"
        
        if include_rules:
            for rule in include_rules:
                rule_desc = CLAUDE_CODE_RULES.get(rule)
                if rule_desc:
                    enhanced += f"- {rule_desc}\n"

        if detail_level == "detailed":
            enhanced += "- Provide deep explanations, clear definitions, and step-by-step reasoning where applicable.\n"
            enhanced += "- Explore edge cases or potential pitfalls and address them proactively.\n"
        else:
            enhanced += "- Keep explanations brief, concise, and focused on the core answer.\n"
            
        enhanced += "\n## Output Format\n"
        enhanced += "- Present the final result formatted in clean Markdown.\n"
        if archetype == "tui_assistant":
            enhanced += "- Optimize formatting for a standard monospace terminal font.\n"
            enhanced += "- Use Github-flavored markdown, including tables for tabular data, and specify language tags for code blocks.\n"
        else:
            enhanced += "- Use tables, bullet points, or code blocks where appropriate to structure readability.\n"
        
        return enhanced

    def _infer_role(self, prompt: str) -> str:
        """
        Simple keyword-based helper to infer a reasonable persona/role from the prompt.
        """
        p_lower = prompt.lower()
        if any(w in p_lower for w in ["code", "python", "javascript", "program", "function", "bug", "develop", "script"]):
            return "Senior Software Engineer"
        elif any(w in p_lower for w in ["write a blog", "write an article", "blog", "article", "essay", "copywriter", "marketing copy"]):
            return "Professional Copywriter and Content Creator"
        elif any(w in p_lower for w in ["analyze", "data", "excel", "report", "statistics"]):
            return "Lead Data Analyst"
        elif any(w in p_lower for w in ["marketing", "seo", "campaign", "ad "]):
            return "Digital Marketing Strategist"
        elif any(w in p_lower for w in ["design", "ui", "ux", "css", "layout"]):
            return "Senior UI/UX Designer"
        else:
            return "Subject Matter Expert"
