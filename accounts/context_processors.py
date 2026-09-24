from .greetings import build_greeting


def greeting(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}

    welcome = bool(request.session.pop("aira_just_signed_in", False))
    return {"aira_greeting": build_greeting(user, welcome=welcome)}
