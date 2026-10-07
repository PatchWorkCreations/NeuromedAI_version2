from django.contrib.auth import get_user_model
from django.core import mail
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from neuromed_v2.mail import MailNotConfiguredError, email_ready, send_html_email
from visits.models import VisitRecording
from visits.templatetags.visit_extras import summary_format, summary_preview


@override_settings(RECAPTCHA_SITE_KEY="", RECAPTCHA_SECRET_KEY="")
class SignedInHomeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("pat", "pat@example.com", "Passw0rd!xy", first_name="Pat")

    def test_login_lands_on_home(self):
        r = self.client.post(reverse("accounts:login"), {"username": "pat", "password": "Passw0rd!xy"})
        self.assertRedirects(r, reverse("dashboard"))

    def test_landing_redirects_signed_in_users_home(self):
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get("/"), reverse("dashboard"))

    def test_new_user_is_pointed_at_first_recording(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse("dashboard"))
        self.assertEqual(r.context["next_step"]["kind"], "first_visit")
        self.assertContains(r, "Record your first visit")
        self.assertNotContains(r, "site-foot")  # no marketing footer inside the app

    def test_recent_summary_is_offered_for_review(self):
        VisitRecording.objects.create(user=self.user, summary="Key points\nAll good.", status="summarized")
        self.client.force_login(self.user)
        r = self.client.get(reverse("dashboard"))
        self.assertEqual(r.context["next_step"]["kind"], "review")

    def test_dashboard_requires_login(self):
        r = self.client.get(reverse("dashboard"))
        self.assertEqual(r.status_code, 302)


class SummaryFilterTests(TestCase):
    def test_preview_drops_headings(self):
        self.assertEqual(summary_preview("Key points\nBP is high.\n\nMedications & dosages\n- Lisinopril."), "BP is high. Lisinopril.")

    def test_format_escapes_html(self):
        self.assertIn("&lt;script&gt;", summary_format("Key points\n<script>x</script>."))


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="Aira <no-reply@example.org>",
)
class SendHtmlEmailTests(SimpleTestCase):
    def test_sends_one_html_message(self):
        send_html_email(to=["pat@example.com"], subject="Hello", html_body="<p>Hi</p>", reply_to=["help@example.org"])
        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ["pat@example.com"])
        self.assertEqual(sent.from_email, "Aira <no-reply@example.org>")
        self.assertEqual(sent.reply_to, ["help@example.org"])
        self.assertEqual(sent.content_subtype, "html")

    def test_blank_recipients_are_dropped(self):
        send_html_email(to=["  ", "pat@example.com ", ""], subject="Hello", html_body="<p>Hi</p>")
        self.assertEqual(mail.outbox[0].to, ["pat@example.com"])

    def test_no_recipients_raises(self):
        with self.assertRaises(MailNotConfiguredError):
            send_html_email(to=["", "  "], subject="Hello", html_body="<p>Hi</p>")
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(DEFAULT_FROM_EMAIL="")
    def test_missing_from_address_raises(self):
        self.assertFalse(email_ready())
        with self.assertRaises(MailNotConfiguredError):
            send_html_email(to=["pat@example.com"], subject="Hello", html_body="<p>Hi</p>")
