from .greetings import build_greeting


def greeting(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}

    first_time = bool(request.session.pop("aira_just_signed_up", False))
    welcome = first_time or bool(request.session.pop("aira_just_signed_in", False))
    return {"aira_greeting": build_greeting(user, welcome=welcome, first_time=first_time)}
