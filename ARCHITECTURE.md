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
| iOS payments | Apple StoreKit — **only if a native iOS app ships** | Not required at all if iOS ships as a PWA; see open decision below |
| Auth | Django auth + Google OAuth + Microsoft MSAL | Reused from v1 |
| Deployment | Procfile + gunicorn + whitenoise (Heroku/Railway-style) | Reused pattern from v1 |

## Open decisions this architecture assumes will get answered early

- **PWA vs. native iOS**, specifically because of the recording feature's need for reliable microphone capture in the background (Safari PWAs on iOS cannot record once the screen locks or the app loses focus). Current lean from planning: a thin native app for the recording flow, PWA for everything else. This decision determines whether the `billing` app needs any StoreKit code at all — resolve it before that app is scaffolded.
- **Cloud host** for Postgres + media storage. Needs to be chosen before the OpenAI BAA is signed, since both should be on BAA-covered, encryption-audited infrastructure together.
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
