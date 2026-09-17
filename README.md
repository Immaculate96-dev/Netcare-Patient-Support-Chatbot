# Netcare Help Assistant
http://127.0.0.1:5000/

A deterministic, rule-based Netcare website-navigation chatbot built with Flask, vanilla JavaScript, CSS and JSON files.

## Design goal

The chatbot is designed as a navigation layer that makes the Netcare website easier to use. It follows an **answer-first** policy:

1. If verified Netcare information in the local JSON knowledge base answers the question, answer directly.
2. If the user must perform an action on a secure/personalised Netcare system, provide the exact official destination.
3. If the chatbot cannot safely answer, say so instead of inventing information and provide the most relevant official Netcare referral.
4. Never diagnose a condition, prescribe treatment or interpret medical results.

## Project structure

```text
netcare-chatbot/
├── app.py
├── chatbot.py
├── directory.py
├── i18n.py
├── directory.json
├── i18n.json
├── intents.json
├── faqs.json
├── flows.json
├── fallback.json
├── knowledge.json
├── sessions.json
├── unanswered.json
├── conversations.log
├── requirements.txt
├── netcare-logo.svg
├── templates/
│   └── index.html
└── static/
    ├── style.css
    └── script.js
```

## Run locally

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

### Linux/macOS

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

## Production deployment

The Flask app listens on the `PORT` environment variable when present.

For Render or Railway, use a production WSGI server such as Gunicorn. Because Gunicorn is a deployment dependency rather than chatbot logic, it is intentionally not part of the runtime chatbot requirements file. A typical deployment command is:

```text
gunicorn app:app
```

Install it in the platform build command when required:

```text
pip install -r requirements.txt gunicorn
```

## Current verified Netcare information

The knowledge was based on current official Netcare website pages consulted during development, including:

- Netcare appointmed: https://www.netcare.co.za/netcare-appointmed
- Online appointment form: https://www.netcare.co.za/netcare-appointmed/appointmed-form
- MyNetcare Online: https://www.netcare.co.za/MyNetcare-Online
- Netcare Contact Us: https://www.netcare.co.za/Contact-us
- Netcare Hospitals: https://www.netcare.co.za/netcare-hospitals
- Hospital pre-admission: https://www.netcare.co.za/netcare-hospitals/patient-information/hospital-pre-admission
- Netcare 911: https://www.netcare.co.za/netcare-911
- Netcare 911 contact: https://www.netcare.co.za/netcare-911/contact-us
- Emergency and trauma care: https://www.netcare.co.za/netcare-hospitals/specialist-services/emergency-and-trauma
- NetcarePlus FAQs: https://www.netcare.co.za/NetcarePlus/FAQs

## Important safety note

This is a service-navigation chatbot, not a medical decision-maker. Do not use it to diagnose symptoms, choose medication, interpret medical results or delay emergency care.

## Accessibility: speech input

The chat interface includes an optional microphone button for people who have difficulty typing, including people with visual impairments. Speech recognition is implemented in the browser with the Web Speech API (`SpeechRecognition` / `webkitSpeechRecognition`) and does not add a Python speech package or a new backend API endpoint.

### How it works

1. Select the **Speak** microphone button.
2. Give the browser microphone permission when prompted.
3. Speak a question in English.
4. The recognized text is placed into the normal message box.
5. The user can edit the text or press **Send**.

The project does not depend on browser speech recognition being available. On unsupported browsers the microphone control is disabled and the normal text box remains available.

### Accessibility features included

- Semantic labels for the microphone and text field.
- Live status messages such as "Listening" and recognition errors.
- Keyboard-focus styling for interactive controls.
- Large microphone and send controls suitable for touch use.
- Reduced-motion support via `prefers-reduced-motion`.
- Higher-contrast borders via `prefers-contrast: more`.
- Text entry remains available as a fallback.

### Browser compatibility note

Speech recognition support varies by browser and operating system. The feature uses the browser's built-in recognition implementation rather than shipping its own speech engine. Depending on the browser, speech recognition processing may involve the browser vendor's speech service; this is outside the Flask application and should be covered by the browser's own privacy/permission controls.

## Voice accessibility mode

The chatbot supports a hands-free wake-word experience for users who have difficulty typing or visually navigating controls. Supported trigger phrases are:

- `Hi Netcare`
- `Hello Netcare`
- `Hi`
- `Help`

After the wake phrase, the user can speak the question naturally. The browser automatically sends the recognised question without requiring the Send button. The chatbot reads the answer aloud using the browser Speech Synthesis API.

For an explicit request such as `I want to book an appointment`, the chatbot returns Netcare's official appointmed booking page and, when the request came through voice, automatically opens that page after the response is spoken. The bot does not claim to complete the medical appointment itself; the official Netcare appointmed form completes the booking workflow.

### Browser accessibility note

Speech recognition support depends on the browser and operating system. The application uses the browser's `SpeechRecognition`/`webkitSpeechRecognition` API and `speechSynthesis`; it does not add a speech-processing Python dependency or external API. The first time voice mode is used, the browser may ask for microphone permission. If a browser does not support speech recognition, the normal text input remains available.

## Hospital and doctor lookup

The chatbot includes a verified Netcare hospital and doctor directory compiled from Netcare webpages during the build. Hospital queries can match facility name, city/location or province. Doctor queries can match doctor name, speciality or hospital. The chatbot never fabricates missing details; when a record is not available, it directs the user to the official Netcare directory or appointmed service.


## Facility directory

`directory.json` holds 69 Netcare hospitals, day clinics and Medicross medical
and dental centres, each with a physical address, switchboard number, city,
province and coordinates. `directory.py` searches it four ways:

- **By province** — "Netcare hospitals in Gauteng" returns every Gauteng
  facility with its address and number.
- **By city or suburb** — common nicknames are handled, so "Joburg", "Jozi",
  "PTA", "Kaapstad" and "eThekwini" all resolve.
- **By facility name** — "Netcare Milpark Hospital" returns that one record.
- **By proximity** — see below.

Every facility in an answer is returned as a structured card alongside the text,
so the interface can render a tap-to-call button and a directions link rather
than making somebody copy a phone number by hand.

### Data provenance and what must change before launch

The directory was seeded from public listings during development, and the
coordinates are **suburb-level approximations entered by hand**. Distance
ranking is reliable at city scale but two hospitals a few kilometres apart can
swap order, and distances are straight-line rather than driving distance.

Before production, replace `directory.json` with a feed from Netcare's own
facility directory, with proper geocoded coordinates. The file's `meta` block
records this, and `/config` exposes it so the status is visible in the running
application rather than buried in a comment.

## Nearest facility search

When a person asks for hospitals near them, the browser requests location
permission, and the coordinates are posted with the message:

```json
{"message": "hospitals near me", "lang": "en", "location": {"lat": -26.2, "lng": 28.04}}
```

`app.parse_location` validates the pair and rejects anything out of range. The
coordinates are used for the distance sort and then discarded: they are not
written to `sessions.json`, not written to `conversations.log`, and not stored
in the browser. The conversation log records only whether a request carried
coordinates, never the values.

If permission is refused, the assistant says so plainly and asks for a town or
province instead, which routes to the ordinary directory search.

## Languages

The assistant answers in **English, Afrikaans, isiZulu and Sesotho**. All
wording lives in `i18n.json`; `i18n.py` loads it and `/config` serves the
interface strings to the front end, so a wording or translation fix is a JSON
edit rather than a JavaScript change.

Each language pack carries its own interface strings, wake phrases, stop
phrases, topic answers and matching keywords. Keyword sets are **merged with
English at match time**, because South African users routinely code-switch: a
Zulu sentence often carries English medical nouns, and "izibhedlela in Gauteng"
must route as cleanly as either language alone.

### Translation status

The Afrikaans, isiZulu and Sesotho content is a **first draft and has not been
reviewed by native speakers**. Medical instructions are exactly where clumsy
phrasing does harm, so review is required before this is put in front of the
public. `/config` exposes `translation_status` for the same reason the
directory status is exposed.

### Speech support by language

Speech recognition and speech synthesis are the browser's, not ours, and their
language coverage is uneven:

| Language | Recognition | Synthesis |
| --- | --- | --- |
| English (en-ZA) | Supported in Chrome, Edge, Safari | Widely available |
| Afrikaans (af-ZA) | Supported in Chrome | Rarely installed |
| isiZulu (zu-ZA) | Supported in Chrome | Rarely installed |
| Sesotho | Not supported; listens in en-ZA | Rarely installed |

When no voice exists for the selected language, the interface says so once and
then reads the answer with an English voice, rather than feeding Zulu text to an
English engine and pretending the result is fine. Delivering proper voice in all
four languages needs a server-side speech service, which moves audio off the
device and is a POPIA question as much as a technical one.

## Spoken answers

Every response now carries a `speech` field alongside `message`. It is the same
answer written to be heard: phone numbers are spaced into individual digits so
synthesis reads "0 8 2, 9 1 1" rather than a mangled number, bullet markers and
line breaks are smoothed into sentences, and URLs are dropped because a spoken
web address is useless. The on-screen `message` keeps its structure.

## Accessibility controls

- Language picker, applied to the interface, the answers, recognition and voice
- Read-answers-aloud toggle, with a stop control while speech is playing
- Three text sizes, up to roughly 140% of the base size
- Light and dark themes, honouring the system setting until overridden
- Atkinson Hyperlegible, designed by the Braille Institute for low vision
- 44px minimum touch targets throughout
- A persistent emergency strip with a one-tap call to 082 911
- Skip link, visible keyboard focus, live status region, reduced-motion support

## Routing order

Emergency wording is checked **first, in every language, before anything else**,
so someone typing in Sesotho about chest pain reaches 082 911 without passing
through intent scoring. After that the order is: continuation of a truncated
facility list, proximity search, explicit booking, facility lookup, translated
topic answers, then the original English intent and FAQ layer, then the honest
no-answer response.

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /` | Chat interface |
| `GET /health` | Service health |
| `GET /config` | Languages, interface strings, wake words, data-status notices |
| `POST /chat` | `{message, session_id, lang, location}` → `{message, speech, facilities, quick_replies, links, auto_open_url, lang, session_id}` |
| `POST /feedback` | Helpful / not-helpful signal |

`lang` and `location` are both optional. Omitting them gives the original
English, non-geographic behaviour, so existing clients keep working unchanged.


## Specialist search: what the live link can and can't do

You asked for this to pull from
`https://www.netcare.co.za/search?path=hospitals_specialists`. I checked it
directly: it's a client-side search widget from a third party (Medpages
International), not a page with retrievable data. There's no static content to
read, and appending query parameters for discipline or province gets silently
stripped — it always redirects back to the bare search path. There's no way to
deep-link into a filtered result, and no feed to query server-side.

So the assistant does the next best honest thing:

1. **Recognises the discipline.** `specialty_aliases` in `i18n.json` maps
   everyday terms — "gynae", "cardio", "heart doctor", "ginekoloog" — to the
   canonical speciality labels used in `knowledge.json`.
2. **Checks verified records first.** If a doctor matching that discipline and
   area is already verified in `knowledge.json`, it's shown with a "Verified in
   Netcare's records" label — never invented.
3. **Says plainly when it doesn't have one.** Most discipline/province
   combinations won't have a verified match yet, since the doctor list is a
   small starting sample. Rather than fabricate a name, the assistant says so,
   lists the real Netcare hospitals in that area that offer that kind of care,
   and hands over the live specialist search link plus the appointmed number —
   both of which are the actual authoritative source for who's currently
   practising where.

Growing `knowledge.json`'s `doctors` array is the way to get more verified
matches; there's no shortcut through the search widget itself. If Netcare can
provide a real feed or API behind that search page, wiring `directory.py` up to
it would replace this fallback with live results.

### Routing note

A specialist question is checked **before** the general area/hospital list, so
"gynae in Gauteng" doesn't get swallowed by the plain "list every hospital in
Gauteng" handler just because it contains a province name.
#   N e t c a r e - P a t i e n t - S u p p o r t - C h a t b o t 
 
 "# Netcare-Patient-Support-Chatbot" 
