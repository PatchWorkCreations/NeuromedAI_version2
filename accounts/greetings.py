"""Warm, rotating greetings for signed-in patients."""
from __future__ import annotations

import hashlib
from datetime import datetime

from django.utils import timezone


def display_name(user) -> str:
    raw = (getattr(user, "first_name", None) or "").strip()
    if not raw:
        raw = (getattr(user, "username", None) or "").strip()
    if not raw:
        email = (getattr(user, "email", None) or "").strip()
        raw = email.split("@")[0] if email else ""
    if not raw:
        return ""
    return raw.split()[0]


def _period(hour: int) -> str:
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 22:
        return "evening"
    return "night"


def build_greeting(user, when: datetime | None = None, *, welcome: bool = False) -> dict:
    """Return a stable-for-today greeting so refreshes don't reshuffle the line."""
    when = when or timezone.localtime()
    name = display_name(user)
    period = _period(when.hour)

    seed_src = f"{getattr(user, 'pk', 'anon')}:{when.date().isoformat()}:{period}:{'w' if welcome else 'd'}"
    seed = int(hashlib.md5(seed_src.encode()).hexdigest(), 16)

    if name:
        by_period = {
            "morning": [
                f"Good morning, {name}",
                f"Morning, {name} — nice to see you",
                f"Hey {name}, ready for a fresh start?",
                f"Hi fighter — morning, {name}",
            ],
            "afternoon": [
                f"Good afternoon, {name}",
                f"Hey {name}",
                f"Hi {name} — you made it",
                f"Afternoon, champ — hey {name}",
            ],
            "evening": [
                f"Good evening, {name}",
                f"Hey {name}, winding down?",
                f"Evening, {name} — Aira’s here",
                f"Hi {name} — glad you’re back",
            ],
            "night": [
                f"Hey {name} — still up?",
                f"Hi {name}",
                f"Night owl mode, {name}",
                f"Hey fighter — hi {name}",
            ],
        }
        welcome_lines = [
            f"Welcome back, {name}",
            f"You’re in, {name} — let’s go",
            f"Hi {name} — good to have you",
            f"Hey fighter — welcome, {name}",
        ]
    else:
        by_period = {
            "morning": [
                "Good morning",
                "Morning — nice to see you",
                "Hey there — fresh start energy",
                "Hi fighter — good morning",
            ],
            "afternoon": [
                "Good afternoon",
                "Hey there",
                "Hi — you made it",
                "Afternoon, champ",
            ],
            "evening": [
                "Good evening",
                "Hey — winding down?",
                "Evening — Aira’s here",
                "Hi — glad you’re back",
            ],
            "night": [
                "Hey — still up?",
                "Hi there",
                "Night owl mode",
                "Hey fighter",
            ],
        }
        welcome_lines = [
            "Welcome back",
            "You’re in — let’s go",
            "Hi — good to have you",
            "Hey fighter — welcome",
        ]

    lines = welcome_lines if welcome else by_period[period]
    headline = lines[seed % len(lines)]

    return {
        "headline": headline,
        "name": name,
        "period": period,
        "welcome": welcome,
    }
