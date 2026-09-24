# Architecture — NeuroMed Aira v2

## Product thesis

Aira captures a doctor's visit, explains it in plain language and the patient's own language, remembers it for next time, and knows when to hand the patient back to their doctor instead of answering itself. It is built to sit *alongside* Epic/MyChart and the clinical record, not to replace, integrate into, or compete with them. Every architectural decision below is filtered through that.

## Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Backend framework | Django (4.2+ / 5.x) | Server-rendered templates; matches v1 and the team's usual stack |
| Frontend | Django templates + HTML/CSS + vanilla JS | No SPA framework. Progressive enhancement, following the Care Orb pattern from v1's `new_dashboard.html` |
| Database | PostgreSQL | via `DATABASE_URL` / `dj-database-url`. Single source of truth in every environment — no SQLite once auth/consent/escalation models exist |
| Realtime | Django Channels + WebSockets | live transcript streaming during recording; optional realtime voice mode (ported from v1) |
| AI / LLM | OpenAI — GPT-4o-class model for chat, Whisper for transcription, Realtime API for voice | Sole vendor for v2. A signed BAA must be active before any pilot patient's data reaches it |
| Media storage | Cloud object storage — **host TBD** | Audio chunks (transient) and uploaded documents. Must sit on the same BAA-covered cloud host as Postgres so the compliance story stays in one place |
| Translation | Real contracted vendor — **TBD, replaces v1's deep-translator/langdetect** | Multilingual reach is a core differentiator; the free-tier wrapper library v1 used is a reliability and compliance risk at that load-bearing a role |
| Web payments | Square | Reused from v1 |
| iOS payments | Not used — PWA only | StoreKit stays out unless a native iOS decision is reopened |
| Auth | Django auth + Google OAuth + Microsoft MSAL | Reused from v1 |
| Deployment | Procfile + gunicorn + whitenoise (Heroku/Railway-style) | Reused pattern from v1 |

## Open decisions this architecture assumes will get answered early

- **Client shape: PWA (decided).** Aira ships as an installable Progressive Web App — no native iOS shell and no StoreKit in `billing`. Known constraint: Safari PWAs cannot keep recording once the screen locks or the app loses focus; the Record UI should warn patients to keep the screen awake during a visit. Revisit only if pilot data shows that constraint blocks real visits.
- **Cloud host: Railway (decided for this build).** Production Postgres via Railway’s Postgres plugin (`DATABASE_URL`). Media/object storage for audio + uploads still needs a Railway volume or an S3-compatible bucket on the same compliance story — wire that before pilot patient files are stored. Local and production databases are PostgreSQL only (see CLAUDE.md boundary #6) — never SQLite.
- **Translation vendor.**

## App structure

```
neuromed_v2/
├── accounts/       # users, profiles, auth backends (Google/Microsoft) — no multi-tenant org/portal
├── chat/           # send_chat view, tone system (PROMPT_TEMPLATES ported), chat sessions, medical summaries
├── visits/         # recording capture, Whisper transcription, visit summaries, consent
├── safety/         # the escalation engine — rules, event log, hooks into chat + visits
├── care_circle/    # family/caregiver sharing — new in v2
├── documents/      # OCR/document ingestion, cross-institution timeline
├── billing/        # Square; StoreKit only if the native-iOS decision lands that way
└── compliance/     # privacy policy versioning, breach-notice logging
```

Deliberately absent: anything resembling v1's Organizational Portal (`triage`, `frontdesk`, `clinical`, `diagnostics`, `scribe`, `coding`, `care` staff apps) and the kiosk feature. See *Keep, Rework, Cut* for the full reasoning — these are hospital operations tools, not patient tools, and they're the specific thing that made v1's positioning contradict itself.

## Data model — the three subsystems that are genuinely new in v2

### Safety (`safety` app)

```python
class EscalationCategory(models.TextChoices):
    MEDICATION_STOP_START = "medication_stop_start", "Medication stop/start"
    SEVERE_INTERACTION   = "severe_interaction", "Severe drug interaction"
    EMERGENCY_SIGN       = "emergency_sign", "Emergency / red-flag symptom"

class EscalationEvent(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    session_id = models.CharField(max_length=255, blank=True)       # guest support
    chat_session = models.ForeignKey("chat.ChatSession", null=True, blank=True, on_delete=models.SET_NULL)
    category = models.CharField(max_length=32, choices=EscalationCategory.choices)
    trigger_text = models.TextField()      # the user message/snippet that triggered it — audit trail
    response_shown = models.TextField()    # the exact refusal/redirect text shown to the user
    created_at = models.DateTimeField(auto_now_add=True)
```

The rule check runs as a discrete step, not a prompt instruction: classify the message/response against the three categories *before* anything reaches the user, log every trigger, and always show the same "contact your doctor" action regardless of what the model would otherwise have said.

### Visits & consent (`visits` app)

```python
class VisitRecording(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    session_id = models.CharField(max_length=255, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    transcript = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=[
        ("recording", "Recording"), ("summarized", "Summarized"), ("discarded", "Discarded"),
    ])

class ConsentRecord(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    session_id = models.CharField(max_length=255, blank=True)
    visit_recording = models.ForeignKey(VisitRecording, on_delete=models.CASCADE, related_name="consents")
    consented_at = models.DateTimeField(auto_now_add=True)
    consent_text_version = models.CharField(max_length=20)   # which wording of the banner was shown
    ip_address = models.GenericIPAddressField(null=True, blank=True)
```

A `ConsentRecord` is written *before* `getUserMedia` is ever called — not after, and not only as a UI banner.

### Care circle (`care_circle` app)

```python
class CareCircle(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="care_circles")
    visit_recording = models.ForeignKey("visits.VisitRecording", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

class CareCircleMember(models.Model):
    circle = models.ForeignKey(CareCircle, on_delete=models.CASCADE, related_name="members")
    invited_email = models.EmailField()
    preferred_language = models.CharField(max_length=10, default="en")
    delivery_mode = models.CharField(max_length=20, choices=[
        ("async_digest", "Async digest"), ("live", "Live access"),
    ], default="async_digest")
    invited_at = models.DateTimeField(auto_now_add=True)
    joined_at = models.DateTimeField(null=True, blank=True)
```

One visit, many viewers, each in their own language, delivered on their own schedule — this is the diaspora/caregiver wedge from the roadmap, and nothing in v1 does this today.

## Core flow

1. Patient opens the app (web or PWA) → dashboard.
2. Taps the Care Orb → **Record & remember** (ported from v1: chunked `MediaRecorder` capture, live Whisper transcription per 6-second segment).
3. Consent banner shown → `ConsentRecord` written → *then* the microphone opens.
4. Live transcript builds in the recorder panel as chunks return.
5. Patient taps **Stop & summarize** → full transcript sent to OpenAI with the structured Visit Summary prompt.
6. Before the response reaches the patient, it passes through the **safety layer**: checked against the three escalation categories. If triggered, an `EscalationEvent` is logged and the patient sees a calm, explicit "contact your doctor" card instead of (or alongside) the model's text.
7. Visit Summary appears in the chat thread. Follow-up actions reuse the transcript: *Questions for next visit*, *Caregiver support*.
8. Patient can share the summary to their **Care Circle** — invite by email, set the viewer's language, choose async digest or live access.
9. Each care-circle member receives their digest in their own language, on their own time — no live presence required.
10. Billing gate applies only at steps 8 onward (care-circle sharing, extended history, voice narration) — never at steps 1–7.

## Safety layer as a first-class architectural piece

v1's red-flag handling lived entirely inside prompt phrasing ("mention red flags calmly," "identify escalation thresholds") with nothing enforcing it outside whatever the model chose to generate, and no record of when it happened. In v2, this is a discrete pipeline stage — classify → log → respond — that runs the same way regardless of tone, mode, or which prompt template produced the draft response. This is also the artifact meant to become a published trust policy: something an evaluating hospital or physician can actually read, unlike the undisclosed internal handling of comparable EHR-native assistants.

## Deployment & environments

- Procfile + gunicorn + whitenoise, same shape as v1.
- `DATABASE_URL`, `OPENAI_API_KEY`, cloud storage credentials, and translation vendor credentials all sourced from environment variables — never hardcoded, never logged.
- Every third-party service that can touch patient data (OpenAI, the cloud host, the translation vendor) needs its BAA status confirmed *before* it's wired into a code path a pilot patient can reach.

## Chat memory of the patient's records

`chat/context.py` builds a short briefing from the signed-in patient's own records and appends it to the chat system prompt on every reply. It covers the 3 most recent non-discarded visit summaries (up to 1,800 characters each) and the 3 most recent uploaded documents (up to 1,200 characters each). Without it, "explain my last visit" had nothing to work from. The briefing only adds context: replies still pass through `safety.engine.check_escalation()`. It never includes other users' records and is empty for guests.

## Helping patients ask the right questions

`chat/guidance.py` covers the patients who don't know what to ask:
- **`GUIDE_PROMPT`** is appended to every chat system prompt. It tells Aira to narrow a vague question with at most two short questions offering simple choices, to tie suggestions to the patient's records (medicine, value, visit date), to point out gaps such as an instruction with no timeframe, and to write "questions for my doctor" in the first person so they can be read aloud.
- **Suggested next questions:** the model ends each reply with a `NEXT: q || q || q` line. `split_follow_ups()` removes that line from the reply and saves the questions on `ChatMessage.follow_ups`, and the UI shows them as tappable chips under Aira's latest reply. There are none after a safety redirect, because the next step there is the doctor.
- **`build_starters()`** builds the four opening cards in an empty chat from the patient's latest visit and document. "I'm not sure what to ask" is always one of them.

## Patient files: chat attachments and Documents

Patients can share up to 3 files per message in Ask Aira (photos, PDF, Word, text; 15 MB each). They can use the paperclip, the camera button, drag and drop, or paste. On phones the camera button opens the native camera; on desktop it opens a webcam view. Every upload, from the chat or the Documents page, goes through `documents/ingest.py`: check the extension and the actual bytes, extract text, then store the original encrypted. Each file becomes an `UploadedDocument`, linked to its `ChatMessage` if it was shared in a chat, so it also appears on the Documents timeline.

- **What the model sees:** photos go to GPT-4o as images, downsized to 1,600px JPEG. PDF, Word and text files go as extracted text (up to 8,000 characters). Later turns in the same chat carry a short text note about earlier files. OpenAI is still the only vendor (boundary #5), and the safety check covers the message plus the shared text.
- **Storage (`documents/storage.py`):** files are encrypted with Fernet using `DOCUMENT_ENCRYPTION_KEY` before they leave the app. Storage keys are random (`<prefix>/<uuid>.bin`) and never include names. `DOCUMENT_STORAGE=iceberg` stores them on cdn.katalyst-crm.com using its three-step upload (init-upload → PUT to presigned R2 → complete). **Iceberg delivery URLs are public with no private or signed option**, which is why encryption is mandatory rather than optional. Patients open files only through `documents:file`, which checks ownership, decrypts, and sends `Cache-Control: private, no-store`. Deleting a document trashes the Iceberg asset (purged after 30 days) or removes the local file.
- **Open compliance item:** Iceberg's underlying storage is Cloudflare R2. It only ever holds ciphertext, but confirm with counsel that encrypted storage without a BAA is acceptable for the pilot before real patient data goes there (CLAUDE.md, "three questions" #3).
