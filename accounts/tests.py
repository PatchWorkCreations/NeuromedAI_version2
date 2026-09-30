from unittest import mock

import requests
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from . import recaptcha

KEYS = {"RECAPTCHA_SITE_KEY": "site-key", "RECAPTCHA_SECRET_KEY": "secret-key"}


def google_says(**result):
    """Patch Google's siteverify to answer with this JSON."""
    response = mock.MagicMock()
    response.json.return_value = result
    return mock.patch("accounts.recaptcha.requests.post", return_value=response)


@override_settings(**KEYS)
class RecaptchaVerifyTests(TestCase):
    def test_ticked_box_passes(self):
        with google_says(success=True, hostname="localhost") as post:
            self.assertTrue(recaptcha.verify("tok", "login"))
        self.assertEqual(post.call_args.kwargs["data"], {"secret": "secret-key", "response": "tok"})

    def test_invalid_token_fails(self):
        with google_says(success=False, **{"error-codes": ["invalid-input-response"]}):
            self.assertFalse(recaptcha.verify("tok", "login"))

    def test_unticked_box_fails_without_calling_google(self):
        with mock.patch("accounts.recaptcha.requests.post") as post:
            self.assertFalse(recaptcha.verify("", "login"))
        post.assert_not_called()

    def test_google_unreachable_lets_people_through(self):
        with mock.patch("accounts.recaptcha.requests.post", side_effect=requests.Timeout):
            self.assertTrue(recaptcha.verify("tok", "login"))

    @override_settings(RECAPTCHA_SITE_KEY="", RECAPTCHA_SECRET_KEY="")
    def test_off_without_keys(self):
        self.assertTrue(recaptcha.verify("", "login"))


@override_settings(**KEYS)
class RecaptchaFormTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("pat", "pat@example.com", "Passw0rd!xy")

    def test_login_blocked_for_bots(self):
        with google_says(success=False):
            r = self.client.post(reverse("accounts:login"), {
                "username": "pat@example.com", "password": "Passw0rd!xy", "g-recaptcha-response": "tok",
            })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "I’m not a robot")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_works_for_people(self):
        with google_says(success=True):
            r = self.client.post(reverse("accounts:login"), {
                "username": "pat@example.com", "password": "Passw0rd!xy", "g-recaptcha-response": "tok",
            })
        self.assertRedirects(r, reverse("dashboard"))

    def test_signup_blocked_for_bots(self):
        with google_says(success=False):
            r = self.client.post(reverse("accounts:signup"), {
                "first_name": "Bo", "last_name": "T", "email": "bot@example.com", "username": "bot",
                "password1": "Sp4m!Sp4m!x", "password2": "Sp4m!Sp4m!x", "terms": "on",
                "g-recaptcha-response": "tok",
            })
        self.assertContains(r, "I’m not a robot")
        self.assertFalse(get_user_model().objects.filter(username="bot").exists())

    def test_password_reset_blocked_for_bots(self):
        with google_says(success=False):
            r = self.client.post(reverse("accounts:password_reset"), {
                "email": "pat@example.com", "g-recaptcha-response": "tok",
            })
        self.assertContains(r, "I’m not a robot")
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_works_for_people(self):
        with google_says(success=True):
            r = self.client.post(reverse("accounts:password_reset"), {
                "email": "pat@example.com", "g-recaptcha-response": "tok",
            })
        self.assertRedirects(r, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)

    def test_checkbox_shows_on_auth_pages(self):
        for name in ("login", "signup", "password_reset"):
            r = self.client.get(reverse(f"accounts:{name}"))
            self.assertContains(r, "recaptcha/api.js")
            self.assertContains(r, 'class="g-recaptcha" data-sitekey="site-key"')

    def test_unticked_login_is_blocked(self):
        r = self.client.post(reverse("accounts:login"), {"username": "pat@example.com", "password": "Passw0rd!xy"})
        self.assertContains(r, "I’m not a robot")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_script_never_loads_inside_the_app(self):
        self.client.force_login(self.user)
        for url in (reverse("dashboard"), reverse("chat:room")):
            self.assertNotContains(self.client.get(url), "recaptcha")


@override_settings(RECAPTCHA_SITE_KEY="", RECAPTCHA_SECRET_KEY="")
class RecaptchaOffTests(TestCase):
    def test_no_script_without_keys(self):
        self.assertNotContains(self.client.get(reverse("accounts:login")), "recaptcha")
