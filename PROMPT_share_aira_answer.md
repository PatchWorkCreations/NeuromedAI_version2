# Prompt: Add "Print" and "Email me this" to Aira's answers

Copy everything below into the AI coding assistant, with the NeuromedAI_v2 repo open.

---

You are working in the NeuromedAI_v2 Django project (Aira, a patient-facing medical explainer). Read `CLAUDE.md`, `ARCHITECTURE.md`, `DESIGN.md` and `TODO.md` first and follow their rules. Do not create extra `*_STATUS.md` files; update `TODO.md` when done.

## Goal

When a signed-in user chats with Aira about a concern (for example "How can I talk to my doctor about my test results?"), they can keep Aira's answer, especially the suggested questions to ask their doctor, in two ways:

1. **Print**: open a clean, printable page of that answer and print it or save it as a PDF from the browser.
2. **Email me this**: Aira emails that answer to the user's own account email, sent through **Resend**.

This is a feature on each Aira reply, not a new chat mode.

## Where things are today (verify before changing)

- `chat/models.py`: `ChatSession` (user, title, tone, lang) and `ChatMessage` (role, content, `follow_ups` JSON list of suggested next questions).
- `chat/views.py`: `send_chat` saves the assistant `ChatMessage` and returns JSON including `follow_ups`. `conversation_page` and `chat_page` render `templates/chat/room.html`.
- `chat/urls.py`: `chat/`, `chat/<id>/`, `chat/<id>/delete/`, `api/send-chat/`.
- `static/js/chat.js`: renders the bubbles; `addFollowUps(row, questions)` draws the follow-up chips. Styles are in `static/css/aira.css`.
- `neuromed_v2/settings.py`: `EMAIL_BACKEND` and `DEFAULT_FROM_EMAIL` are read from env (default from: `Aira <no-reply@neuromedai.org>`). **Resend is not wired in yet.**
- Messages are stored as Markdown-ish plain text from the model.

## What to build

### 1. Message actions in the chat UI
- Under every **assistant** bubble (both the ones loaded from history and new ones added by `chat.js` after `send_chat`), add a small action row: **Print** and **Email me this**.
- `send_chat` must return the new assistant message's `id` in its JSON so `chat.js` can attach the actions to fresh replies. Render the `id` in `room.html` for history messages too (e.g. `data-message-id`).
- Match the existing look in `aira.css` / `DESIGN.md`: quiet text buttons with icons, large tap targets, works on mobile, keyboard accessible, `aria-label`s.
- Actions appear only for signed-in users (chat already requires login).

### 2. Printable page
- New view + URL, e.g. `chat/message/<int:message_id>/print/` (name `chat:print_message`).
- Only the owner can open it: fetch `ChatMessage` where `session__user=request.user` and `role="assistant"`, else 404.
- New template `templates/chat/print_message.html`, **standalone** (does not extend the app shell; no sidebar, nav or chat box). Include:
  - Aira logo + "Prepared with Aira" and the date.
  - The user's question (the user message right before this answer in the same session).
  - Aira's answer rendered cleanly (convert the Markdown to safe HTML; escape anything else, never `|safe` on raw model text).
  - A section **"Questions to ask your doctor"** as a numbered list with blank lines under each for handwritten notes. Source: questions inside the answer if the answer is about talking to a doctor, plus `follow_ups` if present. Keep it simple: if you can't reliably extract questions, list `follow_ups` and show the full answer above.
  - The standard safety footer: "Aira explains health information; it does not replace your doctor. In an emergency call your local emergency number."
- `@media print` CSS: black on white, readable 12–13pt font, no buttons printed, sensible page breaks. A visible "Print" button on screen calls `window.print()`.
- The **Print** action in chat opens this page in a new tab (you can auto-trigger `window.print()` once it loads).

### 3. Email via Resend
- Add Resend with the **official `resend` Python package** (add to `requirements.txt`, pinned) **or** plain `requests` to `https://api.resend.com/emails`. Preferred: a small wrapper `chat/emailing.py` (or a shared `core`/`accounts` helper if one already fits) with `send_aira_answer(user, message) -> bool`.
- Settings / env (add to `settings.py` and `.env.example` with comments):
  - `RESEND_API_KEY=` (required for sending; if empty, fall back to Django's `send_mail` with the console backend so local dev still works)
  - `RESEND_FROM_EMAIL=` defaulting to `DEFAULT_FROM_EMAIL`. The sending domain must be verified in Resend (likely `airamed.org`; confirm with the team, don't guess silently).
- New endpoint: `POST api/chat/message/<int:message_id>/email/` (name `chat:email_message`), login required, CSRF protected, owner check exactly like the print view. Returns JSON `{ok: true}` or `{ok: false, error: "..."}` with a friendly message.
- Sends **only to `request.user.email`**. Do not accept an arbitrary recipient address in this version (privacy, no spam relay). If the user has no email, return a clear error.
- Email content: subject like `Your notes from Aira: <session title>`; HTML body reusing the same content as the print page (make a shared partial `templates/chat/_answer_export.html` used by both) plus a plain-text version. Include the "Questions to ask your doctor" list and the safety footer. Include a link back to the conversation (`https://pilot.airamed.org/chat/<session_id>/`, build it from the request / a `SITE_URL` setting, not hardcoded).
- **Rate limit**: e.g. max 5 emails per user per hour (use Django cache). Return a friendly error when exceeded.
- In the UI: clicking **Email me this** shows a small confirm ("Send this to you@example.com?"), then a loading state, then "Sent to you@example.com" or the error. No `alert()` dialogs.
- Log sends (message id, user id, success/failure) but **never log the email body or medical content**.

### 4. Privacy and safety
- This is health information. Only the owner can print/email their own messages; everything else 404s.
- Don't include other chats, documents or attachments in the email.
- Keep the existing safety engine untouched; don't bypass it.
- If `compliance` has an audit/log model that fits, record "answer emailed" events there; otherwise skip and note it in `TODO.md`.

### 5. Tests (`chat/tests.py`)
- Owner can open the print page; another user gets 404; anonymous gets redirected to login.
- Print page shows the question, answer, follow-up questions and safety footer; raw HTML in model output is escaped.
- Email endpoint: sends to the user's own email (mock Resend / use `locmem` backend), rejects other users' messages (404), requires POST + CSRF, respects the rate limit, errors cleanly when the user has no email or Resend fails.
- `send_chat` JSON now includes the message `id`.
- Run the full test suite and make sure everything passes.

### 6. Finish
- Update `.env.example`, `TODO.md` (tick the feature, list any follow-ups such as "email to my doctor" or PDF attachment), and a short note in `ARCHITECTURE.md` about Resend.
- Summarize what changed, the new env vars to add in Railway (`RESEND_API_KEY`, `RESEND_FROM_EMAIL`, `SITE_URL=https://pilot.airamed.org`), and anything that needs a decision.

## Out of scope for now
- Emailing to someone else (e.g. the doctor or a care-circle member). Design the helper so this can be added later.
- Server-side PDF generation (browser print-to-PDF is enough for v1; `reportlab` is available if we add it later).
