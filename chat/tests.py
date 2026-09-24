from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import ChatMessage, ChatSession


@override_settings(OPENAI_API_KEY="")  # no network: send_chat stops after saving the question
class ConversationHistoryTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("pat", "pat@example.com", "Passw0rd!xy")
        self.other = User.objects.create_user("sam", "sam@example.com", "Passw0rd!xy")
        self.client.force_login(self.user)

    def send(self, message, conversation_id=None):
        body = {"message": message, "tone": "auto"}
        if conversation_id:
            body["conversation_id"] = conversation_id
        return self.client.post(reverse("chat:send_chat"), body, content_type="application/json")

    def test_each_new_chat_is_its_own_conversation(self):
        first = self.send("What does LDL mean on my blood test?").json()
        second = self.send("How do I prepare for my MRI?").json()
        self.assertNotEqual(first["conversation_id"], second["conversation_id"])
        self.assertEqual(ChatSession.objects.filter(user=self.user).count(), 2)
        self.assertEqual(first["title"], "What does LDL mean on my blood test?")

    def test_follow_up_stays_in_the_same_conversation(self):
        cid = self.send("First question").json()["conversation_id"]
        self.send("Follow-up", conversation_id=cid)
        convo = ChatSession.objects.get(pk=cid)
        self.assertEqual(convo.messages.filter(role=ChatMessage.Role.USER).count(), 2)
        self.assertEqual(convo.title, "First question")

    def test_cannot_post_into_someone_elses_conversation(self):
        theirs = ChatSession.objects.create(user=self.other)
        self.assertEqual(self.send("hi", conversation_id=theirs.pk).status_code, 404)
        self.assertEqual(self.client.get(reverse("chat:conversation", args=[theirs.pk])).status_code, 404)

    def test_history_lists_only_my_conversations(self):
        cid = self.send("Explain my lab results please").json()["conversation_id"]
        theirs = ChatSession.objects.create(user=self.other, title="Private to Sam")
        ChatMessage.objects.create(session=theirs, role="user", content="Private to Sam")
        page = self.client.get(reverse("chat:conversation", args=[cid]))
        self.assertContains(page, "Explain my lab results please")
        self.assertNotContains(page, "Private to Sam")

    def test_delete_conversation(self):
        cid = self.send("Delete me").json()["conversation_id"]
        r = self.client.post(reverse("chat:delete_conversation", args=[cid]))
        self.assertRedirects(r, reverse("chat:room"))
        self.assertFalse(ChatSession.objects.filter(pk=cid).exists())

    def test_long_titles_are_trimmed_on_a_word(self):
        title = ChatSession.title_from("word " * 30)
        self.assertLessEqual(len(title), 61)
        self.assertTrue(title.endswith("…"))


from unittest import mock

from documents.models import UploadedDocument
from visits.models import VisitRecording

from .context import build_patient_context


def _fake_openai(captured):
    """Stand-in for openai.OpenAI that records the messages it was sent."""
    client = mock.MagicMock()

    def create(**kwargs):
        captured.update(kwargs)
        reply = mock.MagicMock()
        reply.choices = [mock.MagicMock()]
        reply.choices[0].message.content = "Here is your visit in plain words."
        return reply

    client.chat.completions.create.side_effect = create
    return mock.MagicMock(return_value=client)


@override_settings(OPENAI_API_KEY="test-key")
class VisitMemoryTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("pat", "pat@example.com", "Passw0rd!xy")
        self.other = User.objects.create_user("sam", "sam@example.com", "Passw0rd!xy")
        self.client.force_login(self.user)

    def test_chat_sees_my_latest_visit_summary(self):
        VisitRecording.objects.create(
            user=self.user, status="summarized",
            summary="Key points\nBlood pressure 150/95. Start amlodipine 5mg daily.",
        )
        captured = {}
        with mock.patch("chat.views.openai.OpenAI", _fake_openai(captured)):
            r = self.client.post(
                reverse("chat:send_chat"),
                {"message": "Can you explain my last visit summary in plain words?"},
                content_type="application/json",
            )
        self.assertEqual(r.status_code, 200)
        system = captured["messages"][0]["content"]
        self.assertIn("Blood pressure 150/95", system)
        self.assertIn("most recent visit", system)

    def test_context_never_includes_other_patients(self):
        VisitRecording.objects.create(user=self.other, status="summarized", summary="Sam's private visit")
        UploadedDocument.objects.create(user=self.other, extracted_text="Sam's private lab")
        ctx = build_patient_context(self.user)
        self.assertNotIn("Sam's private", ctx)
        self.assertIn("none yet", ctx)

    def test_discarded_visits_and_guests_are_excluded(self):
        VisitRecording.objects.create(user=self.user, status="discarded", summary="Thrown away")
        self.assertNotIn("Thrown away", build_patient_context(self.user))
        self.assertEqual(build_patient_context(None), "")

    def test_documents_are_included_and_long_text_is_capped(self):
        UploadedDocument.objects.create(
            user=self.user, kind="lab_result", source_institution="St. Luke's",
            extracted_text="LDL 142 mg/dL. " + "filler " * 2000,
        )
        ctx = build_patient_context(self.user)
        self.assertIn("LDL 142", ctx)
        self.assertIn("St. Luke's", ctx)
        self.assertLess(len(ctx), 5000)


from .guidance import build_starters, split_follow_ups


class FollowUpParsingTests(TestCase):
    def test_splits_next_line_off_the_reply(self):
        reply, qs = split_follow_ups(
            "Your LDL is a little high.\nWant to go through it?\n"
            "NEXT: What LDL should I aim for? || Do I need medicine for this? || What foods help?"
        )
        self.assertEqual(reply, "Your LDL is a little high.\nWant to go through it?")
        self.assertEqual(qs, ["What LDL should I aim for?", "Do I need medicine for this?", "What foods help?"])

    def test_tolerates_markdown_and_single_pipes(self):
        _, qs = split_follow_ups("Ok.\n**NEXT:** Why was I given this? | When is my recheck?")
        self.assertEqual(qs, ["Why was I given this?", "When is my recheck?"])

    def test_no_next_line_means_no_suggestions(self):
        self.assertEqual(split_follow_ups("Just an answer."), ("Just an answer.", []))


class StarterTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("pat", "pat@example.com", "Passw0rd!xy")

    def test_new_patient_gets_help_working_out_what_to_ask(self):
        titles = [s["title"] for s in build_starters(self.user)]
        self.assertEqual(len(titles), 4)
        self.assertIn("I’m not sure what to ask", titles)

    def test_starters_follow_the_latest_visit(self):
        VisitRecording.objects.create(user=self.user, status="summarized", summary="Key points\nBP high.")
        starters = build_starters(self.user)
        self.assertTrue(starters[0]["title"].startswith("Explain my visit from"))
        self.assertIn("next appointment", starters[1]["ask"])


@override_settings(OPENAI_API_KEY="test-key")
class FollowUpEndToEndTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("pat", "pat@example.com", "Passw0rd!xy")
        self.client.force_login(self.user)

    def _send(self, model_reply):
        client = mock.MagicMock()
        out = mock.MagicMock()
        out.choices = [mock.MagicMock()]
        out.choices[0].message.content = model_reply
        client.chat.completions.create.return_value = out
        with mock.patch("chat.views.openai.OpenAI", mock.MagicMock(return_value=client)):
            r = self.client.post(reverse("chat:send_chat"), {"message": "what should I ask?"},
                                 content_type="application/json")
        return r, client.chat.completions.create.call_args.kwargs["messages"][0]["content"]

    def test_reply_comes_back_with_tappable_questions(self):
        r, system = self._send(
            "Here are three.\nWhich of these feels most urgent to you?\n"
            "NEXT: Why is my pressure high? || When do I recheck?"
        )
        data = r.json()
        self.assertEqual(data["reply"], "Here are three.\nWhich of these feels most urgent to you?")
        self.assertEqual(data["follow_ups"], ["Why is my pressure high?", "When do I recheck?"])
        self.assertIn("GUIDING THE PATIENT", system)
        saved = ChatMessage.objects.filter(role="assistant").latest("created_at")
        self.assertEqual(saved.follow_ups, data["follow_ups"])
        self.assertNotIn("NEXT:", saved.content)

    def test_safety_redirect_has_no_suggestions(self):
        from safety import engine
        esc = mock.MagicMock(response_text="Please check with your doctor.", category="medication_change")
        with mock.patch("chat.views.check_escalation", return_value=esc), mock.patch("chat.views.log_escalation"):
            r, _ = self._send("Stop taking it.\nNEXT: Can I stop today?")
        self.assertTrue(r.json()["escalated"])
        self.assertNotIn("follow_ups", r.json())


from .guidance import CHECK_INS, GUIDE_PROMPT, ensure_open_ending


class OpenEndingTests(TestCase):
    def test_sign_offs_are_replaced_with_a_caring_question(self):
        out = ensure_open_ending("Your LDL is a bit high. Let me know if you have any other questions! I'm here to help.")
        self.assertTrue(out.startswith("Your LDL is a bit high."))
        self.assertNotIn("Let me know", out)
        self.assertNotIn("here to help", out)
        self.assertIn(out.splitlines()[-1], CHECK_INS)

    def test_reply_that_already_asks_is_left_alone(self):
        text = "That sounds hard. What are you feeling right now?"
        self.assertEqual(ensure_open_ending(text), text)

    def test_never_empties_a_reply(self):
        out = ensure_open_ending("Hope this helps.")
        self.assertTrue(out.startswith("Hope this helps."))
        self.assertTrue(out.endswith("?"))

    def test_prompt_forbids_closing_the_conversation(self):
        self.assertIn("Always end your reply with one gentle, specific question", GUIDE_PROMPT)
        self.assertIn("The patient decides when the conversation is over", GUIDE_PROMPT)


import shutil as _shutil
import tempfile as _tempfile
from pathlib import Path as _Path

from django.core.files.uploadedfile import SimpleUploadedFile

from documents.tests import TEST_KEY, pdf_bytes, png_bytes


@override_settings(OPENAI_API_KEY="test-key", DOCUMENT_STORAGE="local", DOCUMENT_ENCRYPTION_KEY=TEST_KEY)
class ChatAttachmentTests(TestCase):
    def setUp(self):
        self.tmp = _tempfile.mkdtemp()
        self.media = override_settings(PRIVATE_MEDIA_ROOT=_Path(self.tmp))
        self.media.enable()
        self.user = get_user_model().objects.create_user("pat", "pat@example.com", "Passw0rd!xy")
        self.client.force_login(self.user)

    def tearDown(self):
        self.media.disable()
        _shutil.rmtree(self.tmp, ignore_errors=True)

    def _send(self, message, files):
        client = mock.MagicMock()
        out = mock.MagicMock()
        out.choices = [mock.MagicMock()]
        out.choices[0].message.content = "I can see it. What worries you most about it?"
        client.chat.completions.create.return_value = out
        with mock.patch("chat.views.openai.OpenAI", mock.MagicMock(return_value=client)):
            r = self.client.post(reverse("chat:send_chat"), {"message": message, "files": files})
        call = client.chat.completions.create.call_args
        return r, (call.kwargs["messages"] if call else None)

    def test_photo_reaches_the_model_as_an_image(self):
        r, msgs = self._send("What does this say?", [SimpleUploadedFile("rx.png", png_bytes(), "image/png")])
        self.assertEqual(r.status_code, 200, r.content)
        parts = msgs[-1]["content"]
        self.assertTrue(any(p["type"] == "image_url" and p["image_url"]["url"].startswith("data:image/jpeg;base64,") for p in parts))
        doc = UploadedDocument.objects.get()
        self.assertEqual(doc.chat_message.role, "user")
        self.assertEqual(doc.source_institution, "Shared in Ask Aira")
        self.assertEqual(r.json()["attachments"][0]["url"], reverse("documents:file", args=[doc.pk]))

    def test_pdf_text_is_given_to_the_model_and_filed_in_documents(self):
        r, msgs = self._send("", [SimpleUploadedFile("labs.pdf", pdf_bytes(), "application/pdf")])
        self.assertEqual(r.status_code, 200, r.content)
        text = " ".join(p.get("text", "") for p in msgs[-1]["content"])
        self.assertIn("A1c 7.2", text)
        self.assertEqual(ChatSession.objects.get().title, "Shared labs.pdf")

    def test_bad_file_is_rejected_before_anything_is_saved(self):
        r, msgs = self._send("hi", [SimpleUploadedFile("virus.exe", b"MZ", "application/octet-stream")])
        self.assertEqual(r.status_code, 400)
        self.assertIsNone(msgs)
        self.assertFalse(ChatMessage.objects.exists())
        self.assertFalse(UploadedDocument.objects.exists())

    def test_more_than_three_files_is_refused(self):
        files = [SimpleUploadedFile(f"p{i}.png", png_bytes(), "image/png") for i in range(4)]
        r, _ = self._send("", files)
        self.assertEqual(r.status_code, 400)

    def test_guests_cannot_upload(self):
        self.client.logout()
        r = self.client.post(reverse("chat:send_chat"),
                             {"message": "x", "files": [SimpleUploadedFile("p.png", png_bytes(), "image/png")]})
        self.assertEqual(r.status_code, 403)


class ImagingGuidanceTests(ChatAttachmentTests):
    def test_imaging_rule_is_always_in_the_prompt(self):
        self.assertIn("never read findings from a scan image", GUIDE_PROMPT)
        self.assertIn("radiologist's written report", GUIDE_PROMPT)

    def test_photo_adds_the_what_is_this_note(self):
        _, msgs = self._send("Can you read my MRI?", [SimpleUploadedFile("mri.png", png_bytes(), "image/png")])
        self.assertIn("follow SCANS AND IMAGING", msgs[0]["content"])

    def test_pdf_only_does_not_add_the_photo_note(self):
        _, msgs = self._send("", [SimpleUploadedFile("labs.pdf", pdf_bytes(), "application/pdf")])
        self.assertNotIn("follow SCANS AND IMAGING", msgs[0]["content"])
