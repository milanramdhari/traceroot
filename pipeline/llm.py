"""
Central LLM calls via LiteLLM.

Set LLM_MODEL in the environment to switch providers without code changes, for example:
  gemini/gemini-2.5-flash          (GEMINI_API_KEY or GOOGLE_API_KEY)
  gpt-4o                          (OPENAI_API_KEY)
  claude-sonnet-4-5-20250929      (ANTHROPIC_API_KEY)

Use current model ids from each provider; old snapshots (e.g. claude-3-5-sonnet-20241022)
return 404 when retired. See https://docs.litellm.ai/docs/providers and Anthropic model docs.
"""
import json
import os
from typing import Sequence

from dotenv import load_dotenv
from litellm import completion

load_dotenv()

# google-genai often used GOOGLE_API_KEY; LiteLLM Gemini expects GEMINI_API_KEY.
if os.environ.get("GOOGLE_API_KEY") and not os.environ.get("GEMINI_API_KEY"):
    os.environ.setdefault("GEMINI_API_KEY", os.environ["GOOGLE_API_KEY"])

_DEFAULT_MODEL = "anthropic/claude-sonnet-4-6"


def get_model() -> str:
    return os.environ.get("LLM_MODEL", _DEFAULT_MODEL).strip()


def complete_json(system: str, user_parts: Sequence[str]) -> dict:
    """Run a chat completion and parse the reply as JSON."""
    user_content = "\n\n---\n\n".join(user_parts)
    response = completion(
        model=get_model(),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
    )
    text = response.choices[0].message.content
    if not text:
        raise ValueError("Empty LLM response")
    # Strip markdown code fences Claude sometimes wraps around JSON
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    return json.loads(text)
