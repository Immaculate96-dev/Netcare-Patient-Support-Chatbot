# 🏥 Netcare Help Assistant

> **A deterministic, rule-based chatbot for navigating Netcare services, facilities and online resources.**

Built with **Flask, vanilla JavaScript, CSS and JSON**, the Netcare Help Assistant provides a simple, accessible way to find Netcare information without pretending to be a medical decision-maker.

---

## ✨ What it does

The assistant acts as a **navigation layer for the Netcare website**.

It follows an **answer-first** approach:

1. **Answer directly** when verified Netcare information exists in the local knowledge base.
2. **Route users to official Netcare services** when an action must be completed on a secure or personalised system.
3. **Be transparent when information is unavailable** rather than inventing an answer.
4. **Never diagnose, prescribe or interpret medical results.**

> ⚠️ **Important:** This is a service-navigation chatbot, not a medical decision-maker. Users should not use it to diagnose symptoms, choose medication, interpret medical results or delay emergency care.

---

# 🚀 Features

### 💬 Intelligent navigation

* Rule-based, deterministic response system
* Verified local knowledge base
* FAQ and intent matching
* Context-aware facility searches
* Honest fallback responses when information is unavailable

### 🏥 Hospital & doctor lookup

* Search facilities by:

  * Province
  * City or suburb
  * Facility name
  * Proximity
* Search doctors by:

  * Name
  * Speciality
  * Hospital
* Structured facility cards with:

  * Address
  * Phone number
  * Tap-to-call
  * Directions

### 🌍 Multilingual support

The assistant supports:

* 🇿🇦 English
* 🇿🇦 Afrikaans
* 🇿🇦 isiZulu
* 🇿🇦 Sesotho

Language content is maintained in `i18n.json`, allowing translations and interface wording to be updated without modifying JavaScript.

### 🎙️ Voice accessibility

* Browser-based speech recognition
* Wake-word interaction
* Spoken responses
* Automatic appointment-page opening for supported voice workflows
* Text input remains available as a fallback

### ♿ Accessibility

* Adjustable text sizes
* Light and dark themes
* Atkinson Hyperlegible font
* Keyboard navigation
* Visible focus states
* Screen-reader-friendly labels
* Reduced-motion support
* High-contrast support
* 44px minimum touch targets
* Persistent emergency call strip
* Skip link and live status regions

---

# 🧱 Project Structure

```text
netcare-chatbot/
│
├── app.py                  # Flask application and API routes
├── chatbot.py              # Chatbot logic and routing
├── directory.py            # Facility/doctor directory search
├── i18n.py                 # Internationalisation helpers
│
├── directory.json          # Netcare facility directory
├── i18n.json               # Languages, translations and keywords
├── intents.json            # Intent definitions
├── faqs.json               # Frequently asked questions
├── flows.json              # Conversation flows
├── fallback.json           # Fallback responses
├── knowledge.json          # Verified chatbot knowledge
├── sessions.json           # Session data
├── unanswered.json         # Unanswered questions
├── conversations.log       # Conversation metadata/log
│
├── requirements.txt
├── netcare-logo.svg
│
├── templates/
│   └── index.html
│
└── static/
    ├── style.css
    └── script.js
```

---

# ⚡ Quick Start

## 1. Clone the project

```bash
git clone <repository-url>
cd netcare-chatbot
```

## 2. Create a virtual environment

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Linux / macOS

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

## 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Start the application

```bash
python app.py
```

## 5. Open the chatbot

Visit:

```text
http://127.0.0.1:5000
```

---

# ☁️ Production Deployment

The Flask application uses the `PORT` environment variable when one is provided.

For platforms such as **Render** or **Railway**, use a production WSGI server such as **Gunicorn**.

### Start command

```text
gunicorn app:app
```

### Build/install command

```text
pip install -r requirements.txt gunicorn
```

Gunicorn is intentionally kept outside the chatbot's runtime requirements because it is a deployment dependency rather than part of the chatbot's application logic.

---

# 📚 Verified Netcare Information

The chatbot's knowledge base was developed using official Netcare website pages, including:

| Resource                | Purpose                             |
| ----------------------- | ----------------------------------- |
| Netcare appointmed      | Appointment booking                 |
| Online appointment form | Appointment workflow                |
| MyNetcare Online        | Online patient services             |
| Contact Us              | General Netcare contact information |
| Netcare Hospitals       | Hospital information                |
| Hospital pre-admission  | Pre-admission information           |
| Netcare 911             | Emergency services                  |
| Netcare 911 Contact     | Emergency contact information       |
| Emergency & Trauma Care | Emergency and trauma services       |
| NetcarePlus FAQs        | NetcarePlus information             |

The local knowledge base should be treated as a **verified snapshot**, not a replacement for Netcare's live website.

---

# 🏥 Facility Directory

`directory.json` contains **69 Netcare hospitals, day clinics and Medicross medical and dental centres**.

Each facility includes:

* Physical address
* Switchboard number
* City
* Province
* Coordinates

The directory supports four search modes:

### 1. Province

```text
Netcare hospitals in Gauteng
```

Returns facilities in the requested province.

### 2. City / suburb

Common location names are supported, including:

```text
Joburg
Jozi
PTA
Kaapstad
eThekwini
```

### 3. Facility name

```text
Netcare Milpark Hospital
```

Returns the matching facility.

### 4. Proximity

```text
hospitals near me
```

Uses browser location permission to calculate proximity.

---

## 📍 Location & Privacy

When a user requests nearby facilities, the browser can provide their location to the application.

Example request:

```json
{
  "message": "hospitals near me",
  "lang": "en",
  "location": {
    "lat": -26.2,
    "lng": 28.04
  }
}
```

The application:

* Validates the coordinates.
* Uses them only for distance sorting.
* Does **not** store the coordinates in `sessions.json`.
* Does **not** store them in `conversations.log`.
* Does **not** persist them in the browser.
* Logs only whether a request included location data.

If location permission is denied, the assistant asks the user for a town, city or province instead.

---

# ⚠️ Directory Data Status

The current directory was seeded from public listings during development.

> **Important:** Coordinates are suburb-level approximations entered manually.

This means:

* City-level distance ranking is generally useful.
* Nearby facilities can occasionally appear in a different order.
* Distances are **straight-line distances**, not driving distances.

### Before production

The recommended production change is to replace `directory.json` with a feed from Netcare's own facility directory containing properly geocoded coordinates.

The application exposes the directory's data status through `/config`.

---

# 👨‍⚕️ Specialist & Doctor Search

The assistant supports specialist-related questions using verified records in `knowledge.json`.

Speciality aliases are defined in `i18n.json`, allowing everyday expressions such as:

```text
gynae
cardio
heart doctor
ginekoloog
```

to map to canonical speciality labels.

### Search behaviour

The assistant:

1. Recognises the requested speciality.
2. Checks verified doctor records.
3. Returns verified matches where available.
4. Avoids fabricating doctors or unavailable information.
5. Provides relevant Netcare facilities when no verified doctor match exists.
6. Refers users to Netcare's live specialist search and appointmed service where appropriate.

Specialist questions are processed **before general area/facility searches**, preventing queries such as:

```text
gynae in Gauteng
```

from being interpreted as a generic request for hospitals in Gauteng.

### Current limitation

The Netcare specialist search is powered by a client-side third-party search widget and does not expose a reliable static dataset or server-side feed that the chatbot can query directly.

Therefore, expanding the verified `doctors` dataset in `knowledge.json` is currently the supported way to increase local specialist coverage.

If Netcare provides an official specialist API or data feed in future, `directory.py` can be updated to use live data.

---

# 🌍 Languages & Internationalisation

The assistant currently supports:

| Language  | Code |
| --------- | ---- |
| English   | `en` |
| Afrikaans | `af` |
| isiZulu   | `zu` |
| Sesotho   | `st` |

All interface and conversational wording is stored in:

```text
i18n.json
```

The Python internationalisation layer loads this data through:

```text
i18n.py
```

The `/config` endpoint exposes the relevant interface configuration to the frontend.

### Code-switching

Keyword matching combines each selected language with English keywords.

This is intentional because South African users commonly mix languages in a single sentence.

For example:

```text
izibhedlela in Gauteng
```

can still be routed correctly.

---

# ⚠️ Translation Status

The Afrikaans, isiZulu and Sesotho content is currently a **first draft** and has not been reviewed by native speakers.

Because the chatbot can provide service and emergency-related information:

> **Native-speaker review is required before public production use.**

The translation status is exposed through `/config`.

---

# 🎙️ Voice & Speech

Voice interaction uses browser APIs rather than a Python speech-processing package.

### Speech recognition

The application uses:

```text
SpeechRecognition
webkitSpeechRecognition
```

### Speech synthesis

Responses are spoken using:

```text
speechSynthesis
```

No additional speech-processing backend or external speech API is required by the current implementation.

---

## 🎤 Speech Input

Users can:

1. Select the **Speak** microphone button.
2. Grant microphone permission.
3. Speak their question.
4. Review or edit the recognised text.
5. Press **Send**.

If speech recognition is unavailable, the microphone control is disabled and normal text input remains available.

---

# 🗣️ Voice Accessibility Mode

The chatbot supports hands-free interaction through wake phrases:

```text
Hi Netcare
Hello Netcare
Hi
Help
```

After the wake phrase, the user can speak naturally.

The application can then:

1. Recognise the question.
2. Submit it automatically.
3. Receive the chatbot response.
4. Read the response aloud.

For example:

```text
I want to book an appointment
```

can route the user to Netcare's official appointmed booking page.

The chatbot does **not** claim to complete the appointment itself. The official Netcare booking workflow remains responsible for the actual appointment.

---

# 🔊 Spoken Responses

Every chatbot response includes both:

```text
message
speech
```

The `message` field is optimised for the screen.

The `speech` field is optimised for listening.

Speech formatting includes:

* Spacing phone numbers into individual digits.
* Smoothing bullet points and line breaks.
* Removing URLs that are not useful when spoken aloud.
* Keeping the on-screen response structurally formatted.

---

## 🎧 Browser Speech Compatibility

Speech recognition and synthesis support varies by browser and operating system.

| Language            | Recognition                 | Synthesis        |
| ------------------- | --------------------------- | ---------------- |
| English (`en-ZA`)   | Chrome, Edge, Safari        | Widely available |
| Afrikaans (`af-ZA`) | Chrome                      | Rarely installed |
| isiZulu (`zu-ZA`)   | Chrome                      | Rarely installed |
| Sesotho             | Uses `en-ZA` listening mode | Rarely installed |

When a suitable voice is unavailable, the interface informs the user and falls back to an available English voice rather than presenting an inaccurate language-specific voice experience.

Full voice support across all four languages would require a server-side speech service, which introduces additional privacy and POPIA considerations.

---

# ♿ Accessibility

The interface includes:

* Language selector
* Read-answers-aloud toggle
* Speech stop control
* Three text-size levels
* Text scaling up to approximately 140%
* Light/dark themes
* System theme detection
* Atkinson Hyperlegible font
* 44px minimum touch targets
* Keyboard-focus styling
* Semantic labels
* Live status messages
* Skip link
* Reduced-motion support
* Higher-contrast support
* Persistent emergency call strip
* Text input fallback for voice features

---

# 🚨 Emergency Routing

Emergency wording is checked **before all other intent processing**.

This means an emergency-related message is prioritised before:

* Intent scoring
* Facility searches
* Booking flows
* FAQ matching
* General knowledge lookup

This behaviour applies across supported languages.

For example, emergency-related wording in Sesotho can still be routed to the emergency response rather than being processed as a normal information request.

The interface also provides a persistent emergency strip with a one-tap call option for:

```text
082 911
```

---

# 🔀 Routing Architecture

The chatbot follows this routing order:

```text
                    ┌──────────────────────┐
                    │      User Input      │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Emergency Detection  │
                    └──────────┬───────────┘
                               │
                               ▼
                 ┌────────────────────────────┐
                 │ Truncated Facility List?   │
                 └─────────────┬──────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Proximity Search      │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Explicit Booking     │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Facility Lookup      │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Translated Topics    │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ English Intent + FAQ │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Honest No-Answer     │
                    └──────────────────────┘
```

This ordering helps ensure that more specific and safety-critical requests are not swallowed by broader matching rules.

---

# 🔌 API Reference

| Method | Endpoint    | Purpose                                                              |
| ------ | ----------- | -------------------------------------------------------------------- |
| `GET`  | `/`         | Chat interface                                                       |
| `GET`  | `/health`   | Service health check                                                 |
| `GET`  | `/config`   | Languages, interface strings, wake words and data-status information |
| `POST` | `/chat`     | Process a chatbot message                                            |
| `POST` | `/feedback` | Submit helpful / not-helpful feedback                                |

### `POST /chat`

Example request:

```json
{
  "message": "hospitals near me",
  "session_id": "example-session",
  "lang": "en",
  "location": {
    "lat": -26.2,
    "lng": 28.04
  }
}
```

Example response structure:

```json
{
  "message": "...",
  "speech": "...",
  "facilities": [],
  "quick_replies": [],
  "links": [],
  "auto_open_url": null,
  "lang": "en",
  "session_id": "example-session"
}
```

Both `lang` and `location` are optional.

Omitting them preserves the original English, non-geographic behaviour for existing clients.

---

# 🔐 Safety & Privacy Principles

The chatbot follows several core principles:

### No medical diagnosis

The assistant does not:

* Diagnose conditions
* Prescribe treatment
* Recommend medication
* Interpret medical results

### No fabricated information

If verified information is unavailable, the assistant says so and refers the user to an appropriate official Netcare resource.

### Minimal location handling

Location coordinates are used only for proximity sorting and are discarded after processing.

### Official destinations

When an action requires Netcare's secure or personalised systems, the chatbot directs users to the appropriate official Netcare service rather than pretending to complete the action itself.

---

# 🧪 Development Considerations

Before public production deployment, the following areas require attention:

* Replace manually seeded facility coordinates with properly geocoded Netcare data.
* Establish a reliable official facility/specialist data feed where available.
* Have Afrikaans, isiZulu and Sesotho content reviewed by native speakers.
* Validate all medical/service information against current Netcare sources.
* Review browser speech-processing privacy implications.
* Assess POPIA requirements for any future server-side speech service.
* Add automated tests around emergency routing and multilingual intent matching.
* Monitor unanswered questions to identify gaps in the knowledge base.

---

# 📈 Improving the Knowledge Base

Unanswered questions can be tracked through:

```text
unanswered.json
```

This provides a practical feedback loop:

```text
User question
      ↓
No verified answer
      ↓
Record unanswered query
      ↓
Review recurring questions
      ↓
Add verified knowledge
      ↓
Test routing
      ↓
Deploy improvement
```

This keeps the assistant deterministic while allowing its coverage to grow over time.

---

# 🛡️ Design Philosophy

The project prioritises:

| Principle           | Approach                                        |
| ------------------- | ----------------------------------------------- |
| **Accuracy**        | Prefer verified information                     |
| **Transparency**    | Say when information is unavailable             |
| **Safety**          | Emergency routing comes first                   |
| **Privacy**         | Avoid unnecessary storage of location data      |
| **Accessibility**   | Support multiple input and presentation methods |
| **Maintainability** | Keep content in JSON rather than hard-coding it |
| **Local relevance** | Support South African languages and terminology |
| **User agency**     | Navigate users to official Netcare services     |

---

# 📄 License

Add the project's applicable license here.

```text
License: [Choose appropriate license]
```

---

## 🏁 Project Status

**Current status:** Development / prototype

The core chatbot, facility lookup, multilingual interface, accessibility features, voice interaction and routing architecture are implemented.

Before public-facing production deployment, the **data provenance, translations, specialist coverage, browser compatibility and safety-related content should undergo formal review**.
