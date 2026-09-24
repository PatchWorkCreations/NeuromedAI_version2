# NeuroMed Aira v2

A patient/family companion that captures a doctor's visit, explains it in
plain language and the patient's own language, remembers it, and knows
when to hand the patient back to their doctor instead of answering itself.
Built to complement Epic/MyChart, not compete with them.

Read **CLAUDE.md** first — it has the non-negotiable boundaries this
codebase is built around. Then **ARCHITECTURE.md** (system design, open
decisions) and **DESIGN.md** (visual system, carried over from v1's real
brand). The user-flow storyboard referenced in those docs shows the actual
screens this scaffold is wired for.

## Status

This is a fresh scaffold. Working end-to-end: the safety engine (with a
passing regression suite in `safety/tests.py`), visit consent + recording +
Stop & summarize, and now `chat`'s `send_chat` — tone inference, prompt
building, and the OpenAI call, all routed through the same safety layer
before anything reaches the user. Billing/document/auth logic is still
marked `# TODO: port from v1` where it depends on wiring credentials or a
vendor decision that isn't made yet. See ARCHITECTURE.md § Open decisions
before filling those in.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# fill in SECRET_KEY, DATABASE_URL, OPENAI_API_KEY at minimum

createdb neuromed_v2   # or point DATABASE_URL at an existing Postgres instance
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## App map

| App | What it owns |
|---|---|
| `accounts` | Users, profiles, auth (Google OAuth + Microsoft MSAL — TODO: port from v1) |
| `chat` | **working**: tone inference (fixes v1's mobile default-to-plain_clinical bug — see ARCHITECTURE.md), prompt building, `send_chat` (routes through the safety layer) |
| `visits` | Recording, consent (**working**: `start_visit` requires consent before a recording exists), Whisper transcription (TODO), Stop & summarize (**working**, including the safety-layer check) |
| `safety` | The escalation engine — **working**: `safety/engine.py` classifies against three categories and logs every trigger |
| `care_circle` | Family/caregiver sharing — models done, invite/digest views TODO (blocked on translation vendor decision) |
| `documents` | OCR ingestion (TODO: port from v1), cross-institution timeline (new) |
| `billing` | Free-tier boundary (**working logic**: `Subscription.can_record_and_summarize()` always returns True — see CLAUDE.md boundary #4), Square integration TODO |
| `compliance` | Policy version history + breach incident log |

## What's deliberately not here

No clinician workflow tools — no scribe, no medical coding, no triage
queue, no multi-tenant hospital portal. See `CLAUDE.md` boundary #1 and
*Keep, Rework, Cut* for why.
# NeuromedAI_version2
