# CLAUDE.md — NeuroMed Aira v2

Instructions for any Claude Code / AI session working in this repository. Read this before making changes.

## What this project is

NeuroMed Aira helps a patient or their family understand, remember, and act on what happened in a doctor's visit — before, during, and after. It captures the visit itself, explains it in plain language and the patient's own language, remembers it for next time, and knows when to send the patient back to their doctor instead of answering on its own.

**Positioning (non-negotiable):** Aira complements Epic, MyChart, and the clinical record. It does not compete with them, replace a clinician, or become clinical workflow software. This isn't a marketing tagline — it's the filter every feature decision passes through.

Reference docs from the planning phase (ask Julia for current links if these have moved):
- *Complement, Not Compete* — the GTM/positioning roadmap this build executes against
- *Keep, Rework, Cut* — the audit of the v1 codebase this project is rebuilt from, with the reasoning behind every reuse/cut decision

See also `ARCHITECTURE.md` (system design) and `DESIGN.md` (visual/UX system) in this repo.

## Hard boundaries — do not cross without a product conversation first

1. **No clinician workflow tools.** No ambient clinical-documentation/scribe feature, no medical coding/billing feature, no triage queue, no EHR-replacement feature. v1 grew a full "Organizational Portal" with exactly these tools over time — it's the specific reason this is a fresh repository instead of a continuation. If a feature looks like something a hospital's operations team would use instead of a patient, it does not belong here. When in doubt, ask: does this serve the patient's understanding, or the hospital's workflow?

2. **Every AI response that could touch a medication, a severe symptom, or an emergency sign passes through the safety layer before it reaches the user.** Never rely on prompt instructions alone to catch these (v1 did — see `ARCHITECTURE.md` § Safety layer for why that wasn't enough). The categories: stopping or starting a medication, a flagged severe drug interaction, anything emergency-shaped. Each one gets a logged `EscalationEvent` and a "contact your doctor" action shown to the user — not a confident free-text answer.

3. **Every recording has a consent record before the microphone opens.** No audio capture path may skip writing a `ConsentRecord` first. v1 shipped this as a UI banner with no audit trail; v2 does not repeat that.

4. **The core capture-and-summarize function is never behind a paywall.** Billing gates apply to care-circle sharing, extended history, and voice narration — never to recording a visit and getting the plain-language summary. This is an equity commitment from the roadmap, not a soft preference, and it directly overrides how v1's paywall worked (a flat chat-count cutoff that could ration this function).

5. **OpenAI is the only LLM vendor for this build** — GPT-4o-class model for chat, Whisper for transcription. Don't add a second AI vendor without checking BAA/compliance status first; that's a compliance decision before it's an engineering one.

6. **PostgreSQL only**, including local dev, once auth/consent/escalation models exist — so behavior matches production from day one and nothing gets tested against a database that can't actually hold what production holds.

## Stack conventions

This is a Django app with server-rendered HTML templates, not an SPA — that's a deliberate choice matching how this team builds, not a gap to fill with React.

- Django + HTML templates + vanilla JS enhancement (the "Care Orb" progressive-enhancement pattern from v1's `new_dashboard.html` is the model to follow for interactive pieces like the recorder).
- Django REST Framework only where a real API boundary is needed (e.g. a future PWA client) — not as a wrapper around every view by default.
- PostgreSQL via `DATABASE_URL` / `dj-database-url`, matching v1's deploy pattern (Procfile + gunicorn + whitenoise).
- OpenAI SDK direct calls — reuse the shape of v1's `voice_ai.py` (Whisper transcription) and `PROMPT_TEMPLATES` (tone prompts) rather than reinventing prompt plumbing from zero. Content ports over; see `ARCHITECTURE.md` for what changes structurally.

## Documentation discipline (a lesson from v1, not a suggestion)

v1 accumulated 50+ standalone `*_FIX.md`, `*_DEBUG.md`, and `*_STATUS.md` files as one-off problems came up, until nobody could tell which doc was current. Don't repeat that here:

- Update `ARCHITECTURE.md` and `DESIGN.md` in place when something changes structurally.
- Use commit messages and PR descriptions for the history of *how* a bug got fixed — that's what git log is for.
- A new root-level markdown file needs a real reason (a genuinely new subsystem worth its own reference doc), not "I fixed something and want to remember how."

## Before adding any feature, ask three questions

1. **Does this help a patient or family understand, remember, or act on their own care — or does it help a hospital run its operations?** If the latter, it's out of scope (see boundary #1).
2. **Could this ever need to give guidance on stopping/starting a medication, a severe interaction, or an emergency sign?** If yes, it must route through the safety layer, not free-text generation alone (boundary #2).
3. **Does this touch patient data in a new way?** If yes, check it against current FTC Health Breach Notification Rule coverage and BAA scope before shipping, not after.

## Where things live

Fill in as the app is scaffolded — see `ARCHITECTURE.md` § App structure for the target Django app layout (`accounts`, `chat`, `visits`, `safety`, `care_circle`, `documents`, `billing`, `compliance`) and keep this section current as real paths land.
