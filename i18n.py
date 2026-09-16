"""Language packs for the Netcare chatbot.

Content for English, Afrikaans, isiZulu and Sesotho lives in ``i18n.json``. The
non-English translations are a first draft and must be reviewed by native
speakers before production use; nothing here infers meaning at runtime.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
I18N_FILE = BASE_DIR / "i18n.json"


def spoken_digits(number: str) -> str:
    """Return a phone number spaced out so speech synthesis reads each digit."""
    return " ".join(character for character in str(number) if character.isdigit())


class Translations:
    """Provide per-language strings, keywords and topic answers."""

    def __init__(self, path: Path = I18N_FILE) -> None:
        """Load all language packs into memory."""
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            data = {}
        self.default: str = data.get("default", "en")
        self.languages: dict[str, Any] = data.get("languages", {})
        self.link_labels: dict[str, Any] = data.get("link_labels", {})
        self.translation_status: str = data.get("translation_status", "")
        self.specialty_aliases: dict[str, str] = data.get("specialty_aliases", {})

    def specialty_for(self, text: str) -> str | None:
        """Return the canonical speciality label matched in free text, if any.

        Matches against the labels used in ``knowledge.json``'s verified doctor
        records (e.g. "gynae", "ginekoloog" and "obgyn" all resolve to
        "Gynaecologist and obstetrician"). Returns None rather than guessing
        when nothing matches, so an unrecognised discipline falls through to the
        general specialist-search response instead of a wrong label.
        """
        normalized = normalize_for_match(text)
        best: tuple[int, str] | None = None
        for alias, canonical in self.specialty_aliases.items():
            if alias in normalized and (best is None or len(alias) > best[0]):
                best = (len(alias), canonical)
        return best[1] if best else None

    def resolve(self, code: str | None) -> str:
        """Return a supported language code, falling back to the default."""
        candidate = str(code or "").lower().split("-")[0]
        return candidate if candidate in self.languages else self.default

    def pack(self, code: str | None) -> dict[str, Any]:
        """Return the full language pack for a language code."""
        return self.languages.get(self.resolve(code), {})

    def ui(self, code: str | None) -> dict[str, Any]:
        """Return the interface strings for a language code."""
        return self.pack(code).get("ui", {})

    def phrase(self, code: str | None, key: str, **values: Any) -> str:
        """Return a formatted phrase, falling back to English when missing."""
        phrases = self.pack(code).get("phrases", {})
        template = phrases.get(key) or self.pack("en").get("phrases", {}).get(key, "")
        try:
            return template.format(**values)
        except (KeyError, IndexError):
            return template

    def topic(self, code: str | None, name: str) -> dict[str, Any] | None:
        """Return a topic answer, falling back to English when untranslated."""
        topics = self.pack(code).get("topics", {})
        return topics.get(name) or self.pack("en").get("topics", {}).get(name)

    def keywords(self, code: str | None, group: str) -> list[str]:
        """Return the keywords for a group, merged with English.

        English terms are always included because South African users routinely
        code-switch mid-sentence; a Zulu question often carries English medical
        nouns, and the reverse happens too.
        """
        english = self.pack("en").get("keywords", {}).get(group, [])
        local = self.pack(code).get("keywords", {}).get(group, [])
        merged = list(dict.fromkeys(list(english) + list(local)))
        return merged

    def matches(self, code: str | None, group: str, normalized_text: str) -> bool:
        """Return whether any keyword in the group appears in the text."""
        return any(keyword in normalized_text for keyword in self.keywords(code, group))

    def wake_words(self, code: str | None) -> list[str]:
        """Return the wake phrases that start a voice conversation."""
        return self.pack(code).get("wake_words", [])

    def stop_words(self, code: str | None) -> list[str]:
        """Return the phrases that end a voice conversation."""
        return self.pack(code).get("stop_words", [])

    def link(self, code: str | None, key: str, url: str) -> dict[str, str]:
        """Return a labelled link for a language, falling back to English."""
        language = self.resolve(code)
        labels = self.link_labels.get(language, {})
        label = labels.get(key) or self.link_labels.get("en", {}).get(key) or key
        return {"label": label, "url": url}

    def catalogue(self) -> list[dict[str, str]]:
        """Return the list of supported languages for the language picker."""
        return [
            {
                "code": code,
                "label": pack.get("label", code),
                "html_lang": pack.get("html_lang", "en-ZA"),
                "stt": pack.get("stt", "en-ZA"),
                "tts_prefix": pack.get("tts_prefix", "en"),
            }
            for code, pack in self.languages.items()
        ]


def normalize_for_match(text: str) -> str:
    """Normalize text the same way the chatbot's matcher does."""
    cleaned = str(text or "").lower()
    cleaned = re.sub(r"[^\w\s'-]", " ", cleaned, flags=re.UNICODE)
    return re.sub(r"\s+", " ", cleaned).strip()
