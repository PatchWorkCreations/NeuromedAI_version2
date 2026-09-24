from urllib.parse import urlencode

import requests
from django.conf import settings
from django.urls import reverse


GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO = "https://www.googleapis.com/oauth2/v3/userinfo"


def google_configured():
    return bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET)


def google_redirect_uri(request):
    return request.build_absolute_uri(reverse("accounts:google_callback"))


def google_authorize_url(request, state):
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": google_redirect_uri(request),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH}?{urlencode(params)}"


def exchange_code(request, code):
    response = requests.post(
        GOOGLE_TOKEN,
        data={
            "code": code,
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "redirect_uri": google_redirect_uri(request),
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    response.raise_for_status()
    tokens = response.json()
    info = requests.get(
        GOOGLE_USERINFO,
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        timeout=15,
    )
    info.raise_for_status()
    return info.json()
