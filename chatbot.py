"""Deterministic Netcare service-navigation chatbot logic.

The bot is multilingual (English, Afrikaans, isiZulu, Sesotho) and answers from
verified local JSON only. Facility lookups, including proximity search, are
served from ``directory.json`` through :mod:`directory`; all user-facing wording
comes from ``i18n.json`` through :mod:`i18n`. Nothing is generated or inferred.
"""

from __future__ import annotations

import json
import re
import secrets
import time
from pathlib import Path
from typing import Any

from directory import FacilityDirectory
from i18n import Translations, spoken_digits

BASE_DIR = Path(__file__).resolve().parent
SESSION_FILE = BASE_DIR / "sessions.json"
UNANSWERED_FILE = BASE_DIR / "unanswered.json"
INTENTS_FILE = BASE_DIR / "intents.json"
FALLBACK_FILE = BASE_DIR / "fallback.json"
FAQ_FILE = BASE_DIR / "faqs.json"
KNOWLEDGE_FILE = BASE_DIR / "knowledge.json"
SESSION_TTL_SECONDS = 30 * 60
MAX_INPUT_LENGTH = 2000
FACILITIES_PER_ANSWER = 8
SPOKEN_FACILITIES = 5


def load_json(path: Path, default: Any) -> Any:
    """Load JSON from a file and return a default value when it is unavailable."""
    try:
        with path.open("r", encoding="utf-8") as file_handle:
            return json.load(file_handle)
    except (OSError, json.JSONDecodeError):
        return default


def atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON atomically to reduce corruption risk."""
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as file_handle:
        json.dump(data, file_handle, indent=2, ensure_ascii=False)
    temp_path.replace(path)


def normalize_text(text: str) -> str:
    """Normalize user text for deterministic matching."""
    cleaned = str(text or "").lower()
    cleaned = re.sub(r"[^\w\s'-]", " ", cleaned, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:MAX_INPUT_LENGTH]


def create_session_id() -> str:
    """Create a cryptographically strong session identifier."""
    return secrets.token_urlsafe(18)


class NetcareChatbot:
    """Provide deterministic intent matching, FAQ support and simple session state."""

    def __init__(self) -> None:
        """Load all static chatbot content into memory."""
        self.intents = load_json(INTENTS_FILE, {})
        self.fallback = load_json(FALLBACK_FILE, {})
        self.faqs = load_json(FAQ_FILE, {"faqs": []})
        self.knowledge = load_json(KNOWLEDGE_FILE, {})
        self.sessions = load_json(SESSION_FILE, {})
        self.translations = Translations()
        self.directory = FacilityDirectory()

    # ------------------------------------------------------------------ links

    def link_url(self, key: str, default: str = "https://www.netcare.co.za/") -> str:
        """Return an official Netcare URL from the knowledge base."""
        return self.knowledge.get("links", {}).get(key, default)

    def phone(self, key: str, default: str = "") -> str:
        """Return an official Netcare phone number from the knowledge base."""
        return self.knowledge.get("phone_numbers", {}).get(key, default)

    def build_links(self, lang: str, keys: list[str]) -> list[dict[str, str]]:
        """Return labelled links for the given knowledge-base link keys."""
        links = []
        for key in keys:
            url = self.link_url(key)
            if url:
                links.append(self.translations.link(lang, key, url))
        return links

    # --------------------------------------------------------------- sessions

    def save_sessions(self) -> None:
        """Persist the current session dictionary."""
        atomic_write_json(SESSION_FILE, self.sessions)

    def create_session(self) -> str:
        """Create and persist a new empty chatbot session."""
        session_id = create_session_id()
        self.sessions[session_id] = {
            "current_flow": None,
            "current_step": None,
            "pending_facilities": [],
            "timestamp": time.time(),
        }
        self.save_sessions()
        return session_id

    def get_session(self, session_id: str | None) -> tuple[str, dict[str, Any]]:
        """Return a valid session, creating one when necessary or expired."""
        now = time.time()
        if not session_id or session_id not in self.sessions:
            new_id = self.create_session()
            return new_id, self.sessions[new_id]

        session = self.sessions[session_id]
        if now - float(session.get("timestamp", 0)) > SESSION_TTL_SECONDS:
            del self.sessions[session_id]
            new_id = self.create_session()
            return new_id, self.sessions[new_id]

        session["timestamp"] = now
        return session_id, session

    def reset_session(self, session_id: str) -> None:
        """Reset the active flow state while keeping the same session identifier."""
        session = self.sessions.setdefault(session_id, {})
        session["current_flow"] = None
        session["current_step"] = None
        session["pending_facilities"] = []
        session["timestamp"] = time.time()
        self.save_sessions()

    # --------------------------------------------------------------- matching

    def score_intent(self, text: str) -> list[tuple[str, int]]:
        """Score each intent by exact phrase, token and partial keyword matches."""
        normalized = normalize_text(text)
        if not normalized:
            return []

        scored: list[tuple[str, int]] = []
        for intent_name, intent_data in self.intents.items():
            score = 0
            for keyword in intent_data.get("keywords", []):
                phrase = normalize_text(keyword)
                if not phrase:
                    continue
                if phrase in normalized:
                    score += 3 if " " in phrase else 2
                else:
                    keyword_parts = phrase.split()
                    if len(keyword_parts) == 1 and any(
                        token.startswith(keyword_parts[0]) for token in normalized.split()
                    ):
                        score += 1
            if score > 0:
                scored.append((intent_name, score))
        scored.sort(key=lambda item: (-item[1], list(self.intents).index(item[0])))
        return scored

    def best_intent(self, text: str) -> str | None:
        """Return the highest-scoring deterministic intent name."""
        scores = self.score_intent(text)
        return scores[0][0] if scores else None

    def find_faq(self, text: str) -> dict[str, Any] | None:
        """Find the closest FAQ using deterministic token overlap."""
        normalized = normalize_text(text)
        if not normalized:
            return None
        query_tokens = set(normalized.split())
        best_match = None
        best_score = 0
        for item in self.faqs.get("faqs", []):
            tokens = set(normalize_text(item.get("question", "")).split())
            score = len(query_tokens & tokens)
            if score > best_score:
                best_score = score
                best_match = item
        return best_match if best_score >= 2 else None

    def log_unanswered(self, session_id: str, question: str) -> None:
        """Record an unanswered question for later content review."""
        records = load_json(UNANSWERED_FILE, [])
        records.append(
            {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "session_id": session_id,
                "question": question[:MAX_INPUT_LENGTH],
            }
        )
        atomic_write_json(UNANSWERED_FILE, records[-1000:])

    # -------------------------------------------------------------- responses

    def response(self, message: str, quick_replies: list | None = None,
                 links: list | None = None, session_id: str | None = None,
                 auto_open_url: str | None = None, speech: str | None = None,
                 facilities: list | None = None, lang: str = "en") -> dict[str, Any]:
        """Build the standard chatbot response object.

        ``speech`` is a separate spoken rendering of the same answer: phone
        numbers are spaced into digits and bullet markup is dropped, so a person
        listening hears something sensible rather than punctuation.
        """
        return {
            "message": message or "I am here to help. Please tell me what you need.",
            "speech": speech if speech is not None else strip_for_speech(message),
            "quick_replies": quick_replies or [],
            "links": links or [],
            "facilities": facilities or [],
            "session_id": session_id,
            "auto_open_url": auto_open_url,
            "lang": lang,
        }

    def topic_response(self, lang: str, name: str, session_id: str) -> dict[str, Any]:
        """Return a translated topic answer with its official Netcare links."""
        topic = self.translations.topic(lang, name) or {}
        message = topic.get("message", "")
        title = topic.get("title", "")
        body = f"{title}\n\n{message}" if title else message
        return self.response(
            body,
            [],
            self.build_links(lang, topic.get("links", [])),
            session_id,
            speech=topic.get("speech"),
            lang=lang,
        )

    # ------------------------------------------------------------- facilities

    def facility_cards(self, facilities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return facility records as front-end card payloads."""
        return [self.directory.to_card(facility) for facility in facilities]

    def facility_speech(self, lang: str, facility: dict[str, Any]) -> str:
        """Return one facility rendered for speech synthesis."""
        parts = [facility.get("name", ""), facility.get("address", "")]
        distance = facility.get("distance_km")
        if distance is not None:
            parts.append(self.translations.phrase(lang, "away_speech", km=round(distance)))
        parts.append(spoken_digits(facility.get("phone", "")))
        return ". ".join(part for part in parts if part) + "."

    def facility_list_response(self, lang: str, session_id: str, facilities: list[dict[str, Any]],
                               heading: str, lead_speech: str) -> dict[str, Any]:
        """Return a facility list as text, cards and a spoken summary."""
        shown = facilities[:FACILITIES_PER_ANSWER]
        remainder = facilities[FACILITIES_PER_ANSWER:]

        lines = [heading, ""]
        for facility in shown:
            line = f"{facility.get('name')} — {facility.get('address')}"
            distance = facility.get("distance_km")
            if distance is not None:
                line += f" ({self.translations.phrase(lang, 'away', km=distance)})"
            lines.append(line)
            lines.append(facility.get("phone", ""))
            lines.append("")
        lines.append(self.translations.phrase(lang, "stale"))

        speech_parts = [lead_speech]
        speech_parts += [self.facility_speech(lang, item) for item in shown[:SPOKEN_FACILITIES]]
        heard = len(shown[:SPOKEN_FACILITIES])
        if len(facilities) > heard:
            speech_parts.append(
                self.translations.phrase(lang, "and_more", n=len(facilities) - heard)
            )

        session = self.sessions.setdefault(session_id, {})
        session["pending_facilities"] = remainder
        session["timestamp"] = time.time()
        self.save_sessions()

        return self.response(
            "\n".join(lines).strip(),
            [],
            self.build_links(lang, ["hospital_search", "appointmed"]),
            session_id,
            speech=" ".join(part for part in speech_parts if part),
            facilities=self.facility_cards(shown),
            lang=lang,
        )

    def nearest_response(self, lang: str, session_id: str,
                         location: dict[str, float]) -> dict[str, Any]:
        """Return the facilities closest to the caller's coordinates."""
        nearest = self.directory.nearest(location["lat"], location["lng"])
        if not nearest:
            return self.no_match_response(lang, session_id)
        count = len(nearest)
        return self.facility_list_response(
            lang,
            session_id,
            nearest,
            self.translations.phrase(lang, "near_head", n=count),
            self.translations.phrase(lang, "near_speak", n=count),
        )

    def area_response(self, lang: str, session_id: str, text: str) -> dict[str, Any] | None:
        """Return facilities for a named province, city or single facility."""
        normalized = normalize_text(text)
        province = self.directory.find_province(text)
        city = self.directory.find_city(text)

        named = self.directory.find_by_name(text)
        if named and not province:
            card_lines = [
                named.get("name", ""),
                named.get("address", ""),
                f"{named.get('kind')} — {named.get('phone')}",
                "",
                self.translations.phrase(lang, "stale"),
            ]
            return self.response(
                "\n".join(card_lines),
                [],
                self.build_links(lang, ["hospital_search", "appointmed"]),
                session_id,
                speech=self.facility_speech(lang, named),
                facilities=self.facility_cards([named]),
                lang=lang,
            )

        wants_list = self.translations.matches(lang, "facility", normalized)
        if not province and not (city and wants_list):
            return None

        matches = self.directory.in_area(
            province=province,
            city=city if city else None,
            medicross_only=self.translations.matches(lang, "medicross", normalized),
            hospitals_only=(
                self.translations.matches(lang, "hospital_only", normalized)
                and not self.translations.matches(lang, "medicross", normalized)
            ),
        )
        if not matches:
            return None

        where = province or city
        count = len(matches)
        return self.facility_list_response(
            lang,
            session_id,
            matches,
            self.translations.phrase(lang, "province_head", n=count, where=where),
            self.translations.phrase(lang, "province_speak", n=count, where=where),
        )

    def remainder_response(self, lang: str, session_id: str) -> dict[str, Any] | None:
        """Return the facilities held back from the previous list, if any."""
        session = self.sessions.get(session_id, {})
        pending = session.get("pending_facilities") or []
        if not pending:
            return None
        count = len(pending)
        return self.facility_list_response(
            lang,
            session_id,
            pending,
            self.translations.phrase(lang, "province_head", n=count, where=""),
            "",
        )

    def specialist_response(self, lang: str, session_id: str, text: str) -> dict[str, Any]:
        """Return specialist-search guidance for a discipline and/or area.

        Netcare's own specialist finder (linked below) is a client-side search
        widget with no data this application can read or deep-link into — it
        does not accept a discipline or province in its URL, and there is no
        underlying feed to query. So this checks the small set of doctors
        verified in ``knowledge.json`` first; if one matches the discipline and
        area, it is shown with a "verified" label. Otherwise the answer is
        honest about not having a name to give, lists the real Netcare
        hospitals in the area that carry that kind of care, and hands over the
        live search link plus appointmed rather than guessing a doctor's name.
        """
        topic = self.translations.topic(lang, "specialist") or {}
        province = self.directory.find_province(text)
        city = self.directory.find_city(text)
        speciality = self.translations.specialty_for(text)
        where = province or city

        verified = []
        if speciality:
            for doctor in self.knowledge.get("doctors", []):
                if doctor.get("speciality") != speciality:
                    continue
                if province and self.directory.province_of(doctor.get("hospital", "")) != province:
                    continue
                if city and not province and self.directory.city_of(doctor.get("hospital", "")) != city:
                    continue
                verified.append(doctor)

        title = topic.get("title", "")
        if speciality:
            title = f"{speciality} — {where}" if where else speciality
        elif where:
            title = f"{title} — {where}"

        lines = [title, ""]
        speech_parts = []

        if verified:
            lines.append("Verified in Netcare's records:")
            for doctor in verified:
                line = f"{doctor['name']} — {doctor['speciality']} — {doctor['hospital']}."
                if doctor.get("contact"):
                    line += f" {doctor['contact']}"
                lines.append(line)
            speech_parts.append(
                "I have a verified match. " +
                " ".join(f"{d['name']}, at {d['hospital']}." for d in verified[:SPOKEN_FACILITIES])
            )
        elif speciality:
            lines.append(
                f"I do not have a verified {speciality.lower()} on file"
                f"{f' for {where}' if where else ''}, and I do not want to guess a doctor's name. "
                "Netcare's specialist search below has the current list; appointmed can also match you "
                "to one and book the appointment, free of charge."
            )
            speech_parts.append(
                f"I do not have a verified {speciality.lower()} on file"
                f"{f' for {where}' if where else ''}. Use Netcare's specialist search, or call appointmed "
                "on 0 8 6 0, 5 5 5, 5 6 5, and they will match you to one."
            )
        else:
            lines.append(topic.get("message", ""))
            speech_parts.append(topic.get("speech", ""))

        hospitals = (
            self.directory.in_area(province=province, city=city if not province else None, hospitals_only=True)
            if where else []
        )
        if hospitals:
            lines += ["", "Netcare hospitals in the area:"]
            lines += [f"{item.get('name')} — {item.get('city')}" for item in hospitals]
            speech_parts.append(
                "Hospitals in the area include "
                + ", ".join(item.get("name", "") for item in hospitals[:SPOKEN_FACILITIES]) + "."
            )

        return self.response(
            "\n".join(lines).strip(),
            [],
            self.build_links(lang, topic.get("links", ["specialists", "appointmed"])),
            session_id,
            speech=" ".join(part for part in speech_parts if part),
            facilities=self.facility_cards(hospitals[:FACILITIES_PER_ANSWER]),
            lang=lang,
        )

    def no_match_response(self, lang: str, session_id: str) -> dict[str, Any]:
        """Return the honest no-answer response with official referrals."""
        return self.response(
            self.translations.phrase(lang, "no_match"),
            [],
            self.build_links(lang, ["hospital_search", "appointmed", "contact"]),
            session_id,
            lang=lang,
        )

    # ------------------------------------------------------- legacy lookups

    def find_doctors(self, text: str) -> list[dict[str, Any]]:
        """Return verified doctor records matching names, specialties or hospitals."""
        normalized = normalize_text(text)
        records = self.knowledge.get("doctors", [])
        if not normalized:
            return records[:5]
        tokens = set(normalized.split())
        scored: list[tuple[int, dict[str, Any]]] = []
        for doctor in records:
            haystack = normalize_text(" ".join(
                str(doctor.get(field, ""))
                for field in ("name", "speciality", "hospital")
            ))
            score = sum(1 for token in tokens if len(token) >= 3 and token in haystack)
            if score:
                scored.append((score, doctor))
        scored.sort(key=lambda item: (-item[0], item[1].get("name", "")))
        return [item[1] for item in scored[:8]]

    def doctor_response(self, text: str, session_id: str, lang: str = "en") -> dict[str, Any]:
        """Build a response for a named-doctor lookup, or hand off to the directory."""
        matches = self.find_doctors(text)
        if not matches:
            return self.topic_response(lang, "specialist", session_id)
        lines = [self.translations.topic(lang, "specialist").get("title", "")]
        lines.append("")
        for doctor in matches:
            line = f"{doctor['name']} — {doctor['speciality']} — {doctor['hospital']}."
            if doctor.get("contact"):
                line += f" {doctor['contact']}"
            lines.append(line)
        speech_lines = [
            f"{doctor['name']}, {doctor['speciality']}, at {doctor['hospital']}."
            for doctor in matches[:SPOKEN_FACILITIES]
        ]
        return self.response(
            "\n".join(lines),
            [],
            self.build_links(lang, ["specialists", "appointmed"]),
            session_id,
            speech=" ".join(speech_lines),
            lang=lang,
        )

    def human_response(self, session_id: str, lang: str = "en") -> dict[str, Any]:
        """Return official human-contact options."""
        service = self.phone("customer_service", "0860 638 2273")
        accounts = self.phone("hospital_accounts", "010 205 7335")
        message = (
            f"Netcare's customer service centre can assist with general enquiries on {service}, "
            f"Monday to Friday from 08:00 to 16:00. For hospital account queries, call {accounts} "
            "Monday to Friday from 08:00 to 17:00."
        )
        speech = (
            f"Netcare's customer service centre is on {spoken_digits(service)}, "
            f"weekdays from 8 a.m. to 4 p.m. For hospital accounts, call {spoken_digits(accounts)}."
        )
        return self.response(
            message,
            [
                {"label": "General Netcare contact", "value": "How do I contact Netcare?"},
                {"label": "Hospital account", "value": "Who do I contact about my hospital account?"},
            ],
            self.build_links(lang, ["contact"]),
            session_id,
            speech=speech,
            lang=lang,
        )

    # ----------------------------------------------------------------- router

    def handle(self, message: str, session_id: str | None = None,
               lang: str | None = None, location: dict[str, float] | None = None) -> dict[str, Any]:
        """Process one user message and return a deterministic response."""
        lang = self.translations.resolve(lang)
        safe_message = str(message or "").strip()
        session_id, session = self.get_session(session_id)

        if not safe_message:
            ui = self.translations.ui(lang)
            return self.response(
                ui.get("welcome", ""),
                ui.get("quick_replies", []),
                session_id=session_id,
                lang=lang,
            )

        if len(safe_message) > MAX_INPUT_LENGTH:
            safe_message = safe_message[:MAX_INPUT_LENGTH]

        normalized = normalize_text(safe_message)

        # 1. Emergency always wins, in every language, before anything else.
        if self.translations.matches(lang, "emergency", normalized):
            return self.topic_response(lang, "emergency", session_id)

        # 2. Continuation of a truncated facility list.
        if self.translations.matches(lang, "rest", normalized):
            remainder = self.remainder_response(lang, session_id)
            if remainder:
                return remainder

        # 3. Proximity search, which needs coordinates from the browser.
        if self.translations.matches(lang, "nearest", normalized):
            if location and location.get("lat") is not None:
                return self.nearest_response(lang, session_id, location)
            return self.response(
                self.translations.phrase(lang, "no_location"),
                self.translations.ui(lang).get("quick_replies", [])[:2],
                self.build_links(lang, ["hospital_search"]),
                session_id,
                lang=lang,
            )

        # 4. Explicit booking request, which auto-opens appointmed in voice mode.
        explicit_booking = any(
            phrase in normalized
            for phrase in (
                "i want to book an appointment", "i want an appointment",
                "book an appointment now", "start booking an appointment",
                "take me to the appointment booking", "open appointment booking",
                "open appointmed", "book appointmed",
                "ek wil 'n afspraak maak", "ek wil n afspraak maak",
                "ngifuna ukubhuka", "ke batla ho beha letsatsi",
            )
        )
        if explicit_booking:
            booking_url = self.link_url("appointmed")
            booking = self.topic_response(lang, "booking", session_id)
            booking["auto_open_url"] = booking_url
            return booking

        # 5. Specialist queries take priority over the generic facility list:
        # a province name inside "gynae in Gauteng" must not be treated as a
        # plain request for every hospital in Gauteng.
        if self.translations.matches(lang, "specialist", normalized) or self.translations.specialty_for(safe_message):
            named_doctor = " dr " in f" {normalized} " or "doctor" in normalized
            if named_doctor and self.find_doctors(safe_message):
                return self.doctor_response(safe_message, session_id, lang)
            return self.specialist_response(lang, session_id, safe_message)

        # 6. Facility lookups by province, city or facility name.
        area = self.area_response(lang, session_id, safe_message)
        if area:
            return area

        # 7. Translated topic answers.
        for group in ("preadmission", "maternity", "mental", "gap", "dentist", "gp"):
            if self.translations.matches(lang, group, normalized):
                return self.topic_response(lang, group, session_id)

        if self.translations.matches(lang, "booking", normalized):
            return self.topic_response(lang, "booking", session_id)

        if normalized in {"human", "person", "agent", "talk to a person", "contact human"}:
            return self.human_response(session_id, lang)

        if normalized in {"menu", "main menu", "start over", "restart", "home"}:
            self.reset_session(session_id)
            ui = self.translations.ui(lang)
            return self.response(
                ui.get("welcome", ""),
                ui.get("quick_replies", []),
                session_id=session_id,
                lang=lang,
            )

        # 7. English intent and FAQ content from the original knowledge base.
        if lang == "en":
            faq_match = self.find_faq(safe_message)
            intent_name = self.best_intent(safe_message)

            if faq_match and (intent_name is None or intent_name in {"faq", "help"}):
                return self.response(
                    faq_match.get("answer"),
                    [{"label": "Show FAQs", "value": "Show me the FAQs"}],
                    faq_match.get("links", []),
                    session_id,
                    lang=lang,
                )

            if intent_name:
                payload = self.intents[intent_name].get("response", {})
                return self.response(
                    payload.get("message"),
                    payload.get("quick_replies"),
                    payload.get("links"),
                    session_id,
                    lang=lang,
                )

        self.log_unanswered(session_id, safe_message)
        if lang == "en" and self.fallback.get("message"):
            return self.response(
                self.fallback.get("message"),
                self.fallback.get("quick_replies"),
                self.fallback.get("links", []),
                session_id,
                lang=lang,
            )
        return self.no_match_response(lang, session_id)


def strip_for_speech(message: str) -> str:
    """Return message text with list markers and line breaks smoothed for speech."""
    text = str(message or "")
    text = re.sub(r"^[•\-\*]\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\n{2,}", ". ", text)
    text = text.replace("\n", ". ")
    return re.sub(r"\s{2,}", " ", text).strip()
