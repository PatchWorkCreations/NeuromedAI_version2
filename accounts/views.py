import secrets

import requests
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import LoginForm, SignupForm
from .google import exchange_code, google_authorize_url, google_configured

User = get_user_model()


def _auth_context(**extra):
    ctx = {"google_ready": google_configured()}
    ctx.update(extra)
    return ctx


def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect(request.GET.get("next") or reverse("home"))
    return render(request, "accounts/login.html", _auth_context(form=form))


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("home")
    return render(request, "accounts/signup.html", _auth_context(form=form))


@require_POST
@login_required
def logout_view(request):
    logout(request)
    return redirect("home")


def google_start(request):
    if not google_configured():
        messages.error(request, "Google sign-in isn’t set up on this server yet. Use email and password for now.")
        return redirect("accounts:login")
    state = secrets.token_urlsafe(24)
    request.session["google_oauth_state"] = state
    request.session["google_oauth_next"] = request.GET.get("next") or reverse("home")
    return redirect(google_authorize_url(request, state))


def google_callback(request):
    if request.GET.get("error"):
        messages.error(request, "Google sign-in was cancelled.")
        return redirect("accounts:login")
    state = request.GET.get("state")
    code = request.GET.get("code")
    if not code or state != request.session.get("google_oauth_state"):
        messages.error(request, "Google sign-in couldn’t be verified. Please try again.")
        return redirect("accounts:login")
    request.session.pop("google_oauth_state", None)
    try:
        info = exchange_code(request, code)
    except requests.RequestException:
        messages.error(request, "Google sign-in failed. Please try email and password, or try again.")
        return redirect("accounts:login")

    email = (info.get("email") or "").strip().lower()
    if not email:
        messages.error(request, "Google didn’t share an email address, so we couldn’t open an account.")
        return redirect("accounts:signup")

    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        base = email.split("@")[0][:140] or "aira"
        username = base
        n = 1
        while User.objects.filter(username__iexact=username).exists():
            n += 1
            username = f"{base}{n}"
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=info.get("given_name") or "",
            last_name=info.get("family_name") or "",
        )
        user.set_unusable_password()
        user.save(update_fields=["password"])

    login(request, user)
    return redirect(request.session.pop("google_oauth_next", None) or reverse("home"))
