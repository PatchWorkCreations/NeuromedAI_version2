# Aira v2 — TODO

Living list of what is done, what is not, and what is blocked on a decision.
Update this file when a box gets finished — do not add extra `*_STATUS.md` files.

Last reviewed: 15 Sep 2026 (auth + first product screens).

---

## Already working

- Landing page at `/` (patient/family copy, A−/A+, high contrast)
- Safety engine + tests (`safety/engine.py`, `safety/tests.py`)
- Visit **APIs**: consent copy, `start_visit` (writes `ConsentRecord` first), Stop & summarize (through safety)
- Chat **API**: `send_chat` with tone inference + safety (no chat screen yet)
- Billing rule: record + summarize is never paywalled (`Subscription.can_record_and_summarize()` always `True`)
- Models scaffolded for care circle, documents, compliance, profiles

Sign-up, log-in, Google, record (consent first), chat, visit history, and document upload now have screens. Google still needs real client credentials in `.env` to complete the redirect.

---

## Next — so a person can actually use it

- [x] Email/password signup + login (name, username, email, password, repeat password)
- [x] Continue with Google (wired; needs `GOOGLE_OAUTH_*` in `.env`)
- [x] Logout
- [x] Record a visit screen — consent first, then mic, then Stop & summarize
- [x] Whisper transcription endpoint (needs `OPENAI_API_KEY`)
- [x] Chat screen
- [x] After-visit summary page
- [ ] Local **Postgres** database `neuromed_v2` created + `migrate` run
- [ ] Local Google OAuth client (localhost / 127.0.0.1 callback) in `.env`

---

## By app

### `accounts`

- [x] Email/password signup + login (same split layout as neuromedai.org)
- [x] Google OAuth (no Microsoft)
- [x] Logout
- [x] Profile fields: language, profession, referral code
- [x] Guest vs signed-in: record, chat, and documents require login
- [ ] Forgot-password email in production (console backend locally)

### `visits`

- [x] HTML recorder UI (consent first, then mic)
- [x] Consent as its own step before `getUserMedia`
- [ ] Live transcript over Channels / WebSockets (HTTP chunk upload is in place)
- [x] Whisper call on `/visits/transcribe/`
- [x] Discard recording path
- [x] Visit history list for the signed-in user

### `chat`

- [x] Chat page (composer, thread, tone selector)
- [x] Easy Read mode — toggle + auto-on with Geriatric tone
- [x] Escalation card UI — teal/care, not a red error banner

### `care_circle`

- [ ] Invite member view (URL is commented out)
- [ ] Invite email in the member’s `preferred_language`
- [ ] Async digest job
- [ ] Keep gated on `ENABLE_CARE_CIRCLE` until the translation vendor is chosen

### `documents`

- [x] Upload UI + PDF/DOCX text extract
- [ ] Image OCR via pytesseract
- [ ] Cross-institution timeline view (field exists: `UploadedDocument.source_institution`)

### `billing`

- [ ] Square checkout (Plus: care-circle, extended history, voice narration only)
- [x] Never gate record + summarize
- [ ] StoreKit **only if** native iOS is chosen — do not scaffold it speculatively

### `compliance`

- [x] Placeholder Privacy + Terms pages (signup links here)
- [ ] Counsel-published policy versions
- [ ] Admin/ops path to log a `BreachIncident` and start the 60-day FTC clock
- [ ] Confirm FTC Health Breach Notification Rule coverage before any new patient-data path ships

### `safety`

- Working. Escalation card is on the chat thread when the engine fires.

---

## Open decisions (block other work)

From `ARCHITECTURE.md`. Do not guess a vendor in code.

- [ ] **PWA vs thin native iOS** for recording (Safari PWA cannot record when the screen locks). Leaning: native for record, PWA for the rest. This decides StoreKit.
- [ ] **Cloud host** for Postgres + media (audio, uploads). Same BAA-covered host as production DB.
- [ ] **Translation vendor** — replaces v1’s deep-translator. Blocks care-circle invites/digests.

---

## Compliance / ops before a *real-patient* pilot

Internal / dummy data does **not** need these. Real patients do, before their data hits a vendor.

- [ ] OpenAI **API BAA** + Modified Retention on the production org (`baa@openai.com`). No dashboard toggle.
- [ ] Cloud host BAA (once the host is chosen)
- [ ] Translation vendor BAA (once chosen)
- [ ] Production `OPENAI_API_KEY` from the BAA org only
- [ ] Counsel: who is covered entity vs business associate

---

## Deploy (`airamed.neuromedai.org`)

- [ ] Host + `DATABASE_URL` + env on the subdomain
- [ ] Google OAuth origin + redirect: `https://airamed.neuromedai.org` and `https://airamed.neuromedai.org/accounts/google/callback/` (same Neuromed project; do not put localhost on the production client)
- [ ] `ALLOWED_HOSTS` + `CSRF_TRUSTED_ORIGINS` for the subdomain
- [ ] HTTPS
- [ ] `DEBUG=False`, real `SECRET_KEY`

---

## Deliberately not doing

Do not add these without a product conversation. See `CLAUDE.md` boundary #1.

- Clinician / hospital workflow (scribe, coding, triage, org portal, kiosk)
- A second LLM vendor (BAA/compliance decision first)
- Microsoft login (v1 had it; v2 is Google-only unless that changes)
- Paywall on record + summarize
- Recording without a `ConsentRecord`
- SQLite “just for local” once auth/consent/escalation are in play
