"""
Helping patients ask the right questions.

Many patients don't know what they need to ask, so a generic list of
things to "consider asking your doctor" doesn't help. This module:

1. GUIDE_PROMPT: tells Aira to narrow a vague question down, ground its
   suggestions in the patient's own records, and end each reply with 2-3
   specific next questions the patient can tap.
2. split_follow_ups(): pulls those suggested questions off the reply so
   the UI can show them as chips instead of text.
3. build_starters(): personalised opening questions for an empty chat,
   built from the patient's latest visit and document.
"""
import re

from django.utils import timezone

GUIDE_PROMPT = (
    "GUIDING THE PATIENT\n"
    "Many patients don't know what they need to ask. Your job is to help them find it.\n"
    "- If a question is vague or broad (for example 'what should I ask?', 'I'm sick', "
    "'explain my results'), don't answer with a generic list. First look at the patient "
    "records above. If you still need more, ask at most two short questions and give "
    "simple choices, for example: 'Is this about your blood pressure follow-up, or "
    "something new?'\n"
    "- When records exist, make everything specific to them: name the medicine, test, "
    "value or instruction, and the visit date.\n"
    "- When asked what to ask a doctor, give 3 to 5 concrete questions tailored to the "
    "records, written in the first person so the patient can read them out as they are. "
    "Put the most important question first.\n"
    "- Watch for gaps the patient may not notice: an instruction without a timeframe, a "
    "new medicine without a reason, a result without a next step. Gently point them out "
    "as questions worth asking.\n"
    "- Never suggest stopping, starting or changing a medicine yourself.\n\n"
    "SCANS AND IMAGING (X-ray, MRI, CT, ultrasound)\n"
    "- You never read findings from a scan image, and you never guess what a scan shows. "
    "General-purpose AI is not reliable at this, and a patient could act on a wrong guess.\n"
    "- But never shut the person down either. Say kindly what the image appears to be (for "
    "example 'This looks like an MRI of your knee') and what that kind of scan is used for.\n"
    "- Then point them to the radiologist's written report, which explains what the scan "
    "showed. Say where to find it: usually in their patient portal (MyChart or similar) "
    "under Imaging or Test results, or from the clinic that did the scan. Invite them to "
    "take a photo of the report and share it here.\n"
    "- When they share or paste a report, explain it line by line in plain words: what each "
    "term means ('unremarkable' means normal; 'incidental' means found by chance), which "
    "lines are routine, and which are worth asking the doctor about. Use their words and "
    "dates. Don't add conclusions the report doesn't state.\n\n"
    "HOW AIRA TALKS\n"
    "You care about the person, not only their question.\n"
    "- When someone shares a symptom, a worry, or a hard result, start with one short, "
    "genuine sentence that acknowledges how they might be feeling. Mean it; no formulas.\n"
    "- Always end your reply with one gentle, specific question that invites them to keep "
    "talking: how they are feeling right now, what worries them most, what happened, or "
    "what they want to understand next. For example: 'What are you feeling right now?', "
    "'Which part of this is worrying you most?', 'How have you been since the visit?'\n"
    "- Ask one question at a time, never a list of questions at the end.\n"
    "- Never close the conversation. Do not end with 'I'm here to help', 'Let me know if "
    "you have any other questions', 'Feel free to reach out', 'Hope this helps', 'Take "
    "care' or any other sign-off. The patient decides when the conversation is over.\n"
    "- Be warm, not sugary: no 'Great question!', no piling on apologies.\n\n"
    "FORMAT FOR SUGGESTED NEXT QUESTIONS\n"
    "End every reply with one final line in exactly this format, with nothing after it:\n"
    "NEXT: <question> || <question> || <question>\n"
    "These are 2 or 3 short questions the patient could tap to ask you next. Write them "
    "in the patient's voice (first person), each under 60 characters, specific to this "
    "conversation and their records. Don't repeat something already answered."
)

_NEXT_LINE = re.compile(r"^\s*\**\s*NEXT\s*:\s*(.+?)\s*\**\s*$", re.IGNORECASE)


def split_follow_ups(text: str) -> tuple[str, list[str]]:
    """Return (reply without the NEXT line, up to 3 suggested questions)."""
    if not text:
        return "", []
    lines = text.rstrip().splitlines()
    for i in range(len(lines) - 1, max(len(lines) - 4, -1), -1):
        m = _NEXT_LINE.match(lines[i])
        if m:
            raw = re.split(r"\s*\|\|\s*|\s*\|\s*", m.group(1))
            questions = []
            for q in raw:
                q = q.strip().strip("*\"'“”<>").strip()
                if 3 <= len(q) <= 90 and q not in questions:
                    questions.append(q)
            reply = "\n".join(lines[:i] + lines[i + 1:]).rstrip()
            return reply, questions[:3]
    return text.rstrip(), []


# Sign-offs that end a conversation instead of continuing it.
_CLOSER = re.compile(
    r"(let me know|feel free|don'?t hesitate|do reach out|reach out (to me|anytime|any time)|"
    r"i'?m (always )?here (to help|for you|if you need)|here if you need|"
    r"hope (this|that|it) helps|take care|wishing you|if you have (any )?(other|more|further) questions)",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

CHECK_INS = [
    "How are you feeling about all of this right now?",
    "What’s on your mind most as you read this?",
    "Which part of this would you like us to go through together next?",
    "How have you been feeling since then?",
]


def ensure_open_ending(reply: str) -> str:
    """
    Keep the conversation open: drop a trailing sign-off, and if the reply
    no longer ends with a question, add a gentle check-in. The model is told
    to do this itself; this is the safety net for when it doesn't.
    """
    text = (reply or "").rstrip()
    if not text:
        return text

    for _ in range(3):
        paragraphs = text.split("\n")
        last = paragraphs[-1].strip()
        sentences = [x for x in _SENTENCE_END.split(last) if x.strip()]
        if not sentences:
            break
        tail = sentences[-1].strip()
        if tail.endswith("?") or not _CLOSER.search(tail):
            break
        kept = " ".join(sentences[:-1]).strip()
        candidate = "\n".join(paragraphs[:-1] + ([kept] if kept else [])).rstrip()
        if not candidate:
            break
        text = candidate

    if not text.rstrip().rstrip("\"'”)").endswith("?"):
        pick = CHECK_INS[sum(map(ord, text)) % len(CHECK_INS)]
        text = f"{text}\n\n{pick}"
    return text


SHARED_IMAGE_NOTE = (
    "The patient has shared a photo in this message. First work out what it is: a document "
    "(lab report, prescription, discharge paper, radiology report), a medicine label, or a "
    "medical image such as an X-ray, MRI, CT or ultrasound. For documents and labels, read "
    "the text and explain it. For a medical image, follow SCANS AND IMAGING: name what it "
    "appears to be, never describe findings, and help them get and understand the written "
    "report."
)


def _day(dt) -> str:
    return timezone.localtime(dt).strftime("%d %B").lstrip("0")


def build_starters(user) -> list[dict]:
    """Opening questions for an empty chat, specific to the patient's records where possible."""
    from documents.models import UploadedDocument
    from visits.models import VisitRecording

    starters = []
    visit = (
        VisitRecording.objects.filter(user=user)
        .exclude(status=VisitRecording.Status.DISCARDED)
        .exclude(summary="")
        .order_by("-started_at")
        .first()
    )
    doc = UploadedDocument.objects.filter(user=user).exclude(extracted_text="").order_by("-uploaded_at").first()

    if visit:
        day = _day(visit.started_at)
        starters.append({
            "title": f"Explain my visit from {day}",
            "sub": "In plain words",
            "ask": f"Can you explain my visit from {day} in plain words?",
        })
        starters.append({
            "title": "What should I ask next time?",
            "sub": f"Based on your {day} visit",
            "ask": f"Based on my visit from {day}, what questions should I ask at my next appointment?",
        })
    if doc:
        kind = doc.get_kind_display().lower()
        starters.append({
            "title": f"What does my {kind} mean?",
            "sub": f"Added {_day(doc.uploaded_at)}",
            "ask": f"Can you explain my {kind} from {_day(doc.uploaded_at)} in plain words? What stands out?",
        })

    starters.append({
        "title": "I’m not sure what to ask",
        "sub": "Aira will help you work it out",
        "ask": "I’m not sure what I should be asking about my health. Can you help me figure it out?",
    })

    defaults = [
        {"title": "Prepare for an appointment", "sub": "Questions worth asking",
         "ask": "I have a doctor’s appointment coming up. Help me prepare the right questions."},
        {"title": "Understand a medicine", "sub": "What it’s for, what to watch",
         "ask": "Can you help me understand one of my medicines, what it’s for and what to watch out for?"},
        {"title": "Make sense of lab results", "sub": "What the numbers mean",
         "ask": "Can you help me understand my lab results?"},
    ]
    for d in defaults:
        if len(starters) >= 4:
            break
        starters.append(d)
    return starters[:4]
