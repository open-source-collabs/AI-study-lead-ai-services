import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from app.services.errors import InvalidModelOutput
from app.services.providers import Provider

T = TypeVar("T")
OUTPUT_ATTEMPTS = 2


@dataclass(frozen=True)
class ProviderInfo:
    provider: str
    model: str


class LLMClient:
    def __init__(self, provider: Provider) -> None:
        self.provider = provider
        self.info = ProviderInfo(provider.name, provider.model)

    async def generate(self, prompt: str, parse: Callable[[Any], T]) -> T:
        # one retry if the answer is not valid JSON or parse() rejects it
        for attempt in range(OUTPUT_ATTEMPTS):
            text = await self.provider.generate(prompt)
            try:
                return parse(parse_json_response(text))
            except (InvalidModelOutput, ValueError, TypeError, LookupError):
                if attempt == OUTPUT_ATTEMPTS - 1:
                    break
        raise InvalidModelOutput("The AI response did not match the expected format. Please retry.")


def parse_json_response(text: str) -> Any:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try the bracket that appears first, so a list is not mistaken for its first object.
        pairs = sorted((cleaned.find(o), o, c) for o, c in (("{", "}"), ("[", "]")))
        for start, _opening, closing in pairs:
            end = cleaned.rfind(closing)
            if 0 <= start < end:
                try:
                    return json.loads(cleaned[start : end + 1])
                except json.JSONDecodeError:
                    continue
    raise InvalidModelOutput("The AI model did not return valid JSON.")
