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
