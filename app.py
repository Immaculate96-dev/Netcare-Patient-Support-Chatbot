"""Flask application for the deterministic Netcare chatbot."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, render_template, request

from chatbot import NetcareChatbot


def parse_location(raw: object) -> dict[str, float] | None:
    """Return validated coordinates from the request payload, or None.

    Coordinates arrive only when the person has granted browser location
    permission for a proximity search. They are validated, used for the distance
    sort, and never persisted.
    """
    if not isinstance(raw, dict):
        return None
    try:
        lat = float(raw.get("lat"))
        lng = float(raw.get("lng"))
    except (TypeError, ValueError):
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
        return None
    return {"lat": lat, "lng": lng}


def configure_logging(app: Flask) -> None:
    """Configure rotating application and conversation logging."""
    handler = RotatingFileHandler(
        "conversations.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    configure_logging(app)
    chatbot = NetcareChatbot()

    @app.get("/")
    def index():
        """Render the chatbot interface."""
        return render_template("index.html")

    @app.get("/health")
    def health():
        """Return a simple service-health response."""
        return jsonify({"status": "ok", "service": "netcare-rule-based-chatbot"})

    @app.get("/version")
    def version():
        """Confirm which build is running, for terminal-based troubleshooting.

        Visiting this in a browser, or running
        ``curl http://127.0.0.1:5000/version`` in a terminal, proves the running
        process is this multilingual build and not an older copy of the app.
        """
        return jsonify(
            {
                "build": "multilingual-v2",
                "languages": [entry["code"] for entry in chatbot.translations.catalogue()],
                "facility_count": chatbot.directory.meta.get("count", len(chatbot.directory.facilities)),
            }
        )

    @app.get("/config")
    def config():
        """Return the languages and interface strings the front end renders with.

        Keeping the strings server-side means a wording or translation fix ships
        as a JSON edit, without touching the JavaScript bundle.
        """
        return jsonify(
            {
                "default_language": chatbot.translations.default,
                "languages": chatbot.translations.catalogue(),
                "ui": {
                    entry["code"]: chatbot.translations.ui(entry["code"])
                    for entry in chatbot.translations.catalogue()
                },
                "wake_words": {
                    entry["code"]: chatbot.translations.wake_words(entry["code"])
                    for entry in chatbot.translations.catalogue()
                },
                "stop_words": {
                    entry["code"]: chatbot.translations.stop_words(entry["code"])
                    for entry in chatbot.translations.catalogue()
                },
                "emergency_number": chatbot.phone("emergency", "082 911"),
                "translation_status": chatbot.translations.translation_status,
                "directory_status": chatbot.directory.meta,
            }
        )

    @app.post("/chat")
    def chat():
        """Handle a chatbot message and return deterministic JSON."""
        try:
            payload = request.get_json(silent=True) or {}
            message = payload.get("message", "")
            session_id = payload.get("session_id")
            language = payload.get("lang")
            location = parse_location(payload.get("location"))
            response = chatbot.handle(message, session_id, language, location)
            # Coordinates are used for the distance calculation and then
            # discarded. They are deliberately not written to the log.
            app.logger.info(
                "session=%s | lang=%s | geo=%s | user=%r | bot=%r",
                response["session_id"],
                response.get("lang"),
                "yes" if location else "no",
                str(message)[:500],
                response["message"][:500],
            )
            return jsonify(response)
        except Exception as exc:  # pragma: no cover
            app.logger.exception("chat endpoint failure: %s", exc)
            return jsonify(
                chatbot.response(
                    "I’m sorry, something went wrong on my side. Please try again or contact Netcare directly.",
                    [{"label": "Contact Netcare", "value": "How do I contact Netcare?"}],
                    [{"label": "Netcare Contact Us", "url": "https://www.netcare.co.za/Contact-us"}],
                    session_id,
                    lang=chatbot.translations.resolve(request.get_json(silent=True, force=True) and None),
                )
            ), 200

    @app.post("/feedback")
    def feedback():
        """Accept helpful/not-helpful feedback without storing sensitive health data."""
        try:
            payload = request.get_json(silent=True) or {}
            app.logger.info(
                "feedback session=%s | helpful=%s",
                payload.get("session_id"),
                bool(payload.get("helpful")),
            )
            return jsonify({"status": "ok"})
        except Exception as exc:  # pragma: no cover
            app.logger.exception("feedback failure: %s", exc)
            return jsonify({"status": "ok"})

    @app.after_request
    def add_cors(response):
        """Add permissive CORS headers suitable for local development."""
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return response

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
