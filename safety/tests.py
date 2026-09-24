"""
Regression tests for the escalation engine — CLAUDE.md boundary #2 says
every AI response touching medication/severe-symptom/emergency content
must pass through this layer before it reaches the user. These tests exist
so that boundary can't quietly regress as chat/views.py and visits/views.py
evolve.
"""
from django.test import TestCase

from safety.engine import check_escalation
from safety.models import EscalationCategory


class EscalationEngineTests(TestCase):
    def test_no_match_on_ordinary_message(self):
        result = check_escalation(user_message="What does an MRI show?", draft_response="An MRI shows...")
        self.assertIsNone(result)

    def test_emergency_sign_in_user_message(self):
        result = check_escalation(user_message="I have chest pain and can't breathe", draft_response="")
        self.assertIsNotNone(result)
        self.assertEqual(result.category, EscalationCategory.EMERGENCY_SIGN)

    def test_medication_stop_start_in_user_message(self):
        result = check_escalation(user_message="Should I stop taking my blood pressure medication?", draft_response="")
        self.assertIsNotNone(result)
        self.assertEqual(result.category, EscalationCategory.MEDICATION_STOP_START)

    def test_severe_interaction_in_draft_response(self):
        # A model could introduce risky content even if the user's own
        # message didn't ask about it directly — the engine has to scan
        # the draft response too, not just the user's message.
        result = check_escalation(
            user_message="Can I have a glass of wine tonight?",
            draft_response="It should be fine to mix with alcohol given your prescription.",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.category, EscalationCategory.SEVERE_INTERACTION)

    def test_emergency_takes_priority_over_other_matches(self):
        # A message that matches both an emergency sign and a medication
        # term must resolve to EMERGENCY_SIGN — that's the whole point of
        # checking categories in a fixed, deliberate order.
        result = check_escalation(
            user_message="I stopped taking my heart medication and now I have chest pain",
            draft_response="",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.category, EscalationCategory.EMERGENCY_SIGN)

    def test_response_text_is_never_empty(self):
        for message in ["chest pain", "stop taking my medication", "mix with alcohol"]:
            result = check_escalation(user_message=message, draft_response="")
            self.assertTrue(result.response_text.strip())
