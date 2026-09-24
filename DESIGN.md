# Design — NeuroMed Aira v2

## Carried forward from v1 — proven, don't reinvent

v1's visual system was already built around a real accessibility commitment (font-size controls, an Easy Read mode, a high-contrast toggle, WCAG AA contrast minimums). That's not cosmetic — it's the same population the whole v2 strategy is built around: older adults, caregivers, non-English speakers, and neurodivergent users who need calm, uncluttered, legible screens more than they need a flashy interface. Keep it.

### Brand colors

| Token | Hex | Usage |
|---|---|---|
| `--nm-primary` | `#236092` | Primary buttons, headers, brand marks |
| `--nm-primary-dark` | `#1B5A8E` | Hover states |
| `--nm-accent` | `#28926D` | Highlights, selected states, focus rings |
| `--nm-accent-light` | `#10b981` | Light accent variant |
| `--nm-text-primary` | `#0f172a` | Body text, headings |
| `--nm-text-secondary` | `#475569` | Secondary text |
| `--nm-text-muted` | `#94a3b8` | Placeholders, hints |
| `--nm-paper` | `#ffffff` | Cards, modals, chat bubbles |
| Body background | `#f8fafc` → `#f1f5f9` | Gradient, main page background |

### Tone colors (chat tone selector — reused as-is)

| Tone | Color |
|---|---|
| Balanced (PlainClinical) | Blue `#236092` |
| Caregiver | Amber `#F59E0B` |
| Faith | Indigo `#4F46E5` |
| Clinical | Slate `#475569` |
| Geriatric | Green `#28926D` |
| Emotional Support | Rose `#E11D48` |

### Accessibility commitments — non-negotiable, already proven in v1

- Font size controls (A− / A+) in the header and mobile menu
- Easy Read mode, auto-enabled when Geriatric tone is selected
- High-contrast toggle
- WCAG AA contrast minimum (4.5:1) on all text
- Information is never conveyed by color alone

Every new v2 screen gets checked against this list before it ships — it isn't a nice-to-have layered on top of the design, it's a load-bearing part of who this product is for.

### Voice (carried forward from v1's prompt design, extended to UI copy)

Calm, confident, human. Conversational, not instructional. No markdown symbols in user-facing text. No robotic phrasing, no excessive disclaimers. v1 wrote this as a rule for AI-generated chat responses; in v2 it applies to every button label, empty state, and error message too — the product should sound like one consistent voice, not a warm AI and a cold interface stitched together.

## New for v2 — three moments that don't exist yet in the current design language

### The escalation moment

When the safety layer redirects instead of answering, the screen has to read as *care*, not as a system failure or a legal disclaimer. Avoid red error-banner styling. Use the accent green and calm, first-person language ("This is something your doctor should weigh in on — here's how to reach them") over alarm-red and passive legal phrasing ("This request cannot be processed"). The action to contact a doctor should be the visually primary element on the screen, not a small link beneath a wall of caveat text.

### The consent moment

Recording consent needs to feel like a real, respected step, not fine print under a record button. Give it its own short screen or modal state before the mic opens: what will be recorded, who it's for, and a single clear affirmative action — not a checkbox buried in a longer form. This is also the moment to make multilingual support visible, since a caregiver reading this in Tagalog or Arabic on behalf of an English-speaking relative is a real, expected use case, not an edge case.

### Care-circle sharing

New surface, no existing pattern to extend. Design language: each invited member reads as a small, named presence (avatar or initials + a language tag), not a row in a settings table — this is a family, not a permissions list. Show each member's delivery mode (async digest vs. live) plainly, since that's a real choice with real implications for a family member who isn't online at the same time as the patient.

## Typography

Confirmed against the live site (`neuromedai.org` login/signup):

- UI: `DM Sans`, system-ui, sans-serif
- Display / headlines: `Instrument Serif`, Georgia, serif (italic for emphasis)
- Auth navy: `#0F4C81` / `#08305A`; cream page ground `#FAFAF8`; body text `#0D1B2A`

## Signed-in app shell

Signed-in pages extend `templates/app_base.html`, not `base.html`. The marketing header and footer belong to the landing and legal pages only.

- **Desktop (≥1040px):** fixed left sidebar with a primary "Record a visit" button, then Home, Your visits, Ask Aira, and Documents. At the bottom is a one-line care note ("works alongside your doctor / emergency number") that stands in for the footer disclaimer. A slim top bar holds the date, Reading options, and the account menu.
- **Phone/tablet:** top bar (logo, Reading, avatar) plus a bottom tab bar. The raised centre tab is Record.
- **Home (`/home/`, `neuromed_v2.views.dashboard`)** is where sign-in lands. It shows one "Your next step" card, chosen from the patient's state (first visit → unfinished recording → review a recent summary → record the next appointment), then a getting-started checklist, quick actions, recent visits and documents, and a care card.
- Styles live in `static/css/app.css` and reuse the shell.css tokens, so Light, Dark, and High contrast all work. Sizes are in rem so the text-size control scales the whole shell.
- Inner pages use `.page-head` (left-aligned serif title, actions on the right) rather than the old centred header with the greeting repeated on every page.
- **Ask Aira** is a full-height conversation. Each chat is its own `ChatSession`, titled from its first question, at `/chat/<id>/`. `/chat/` starts a new one, which is saved only when the first message is sent. Past chats are listed beside it, grouped Today / Yesterday / Previous 7 days / Earlier. Below 1100px that list becomes a drawer opened from the chat header. Deleting a chat removes its messages, but any safety `EscalationEvent` keeps its audit row.
- **Aira's conversational voice:** Aira cares about the person, not only the question. It acknowledges feelings in one genuine sentence and always ends with one gentle, specific question ("What are you feeling right now?"). It never signs off with lines like "I'm here to help" or "let me know if you have any questions"; the patient decides when the conversation is over. This is set in `chat/guidance.py` (`GUIDE_PROMPT`). `ensure_open_ending()` is a safety net: it removes a trailing sign-off and adds a gentle check-in if a reply doesn't already end with a question.
- **Scans and imaging:** Aira never reads findings from an X-ray, MRI, CT or ultrasound image. General-purpose AI isn't reliable at that, and a tool that reads scans would count as a regulated medical device. It doesn't refuse either: it names what the image appears to be ("an MRI of your knee"), says what that scan is for, points the patient to the radiologist's written report (usually in MyChart under Imaging), and explains that report line by line when they share it. This is set in `chat/guidance.py` (`GUIDE_PROMPT`; `SHARED_IMAGE_NOTE` is added when a photo is shared).
