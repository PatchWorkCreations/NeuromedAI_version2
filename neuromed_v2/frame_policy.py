"""
Lets Internal Workspace show this site inside its "Open inside" frame, and no other site.

Django's XFrameOptionsMiddleware sends "X-Frame-Options: DENY", which stops every site from framing this one.
This middleware sits after it in MIDDLEWARE, so it handles the response first: it marks the response exempt
from X-Frame-Options and sends "Content-Security-Policy: frame-ancestors 'self' <allowed sites>" instead.
Browsers then allow only this site and the sites listed below to frame it.

The allowed sites come from the FRAME_ANCESTORS environment variable (space-separated origins); by default
that is Internal Workspace.
"""
import os

DEFAULT_ANCESTORS = "https://internal-product-production.up.railway.app"


def _ancestors():
    origins = os.environ.get("FRAME_ANCESTORS", DEFAULT_ANCESTORS).split()
    # Only plain https:// origins, so a typo can't open the site to every page.
    return [o.rstrip("/") for o in origins if o.startswith("https://") and "*" not in o]


class AllowInternalWorkspaceFrameMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.policy = "frame-ancestors " + " ".join(["'self'"] + _ancestors())

    def __call__(self, request):
        response = self.get_response(request)
        response.xframe_options_exempt = True
        csp = response.get("Content-Security-Policy")
        if not csp:
            response["Content-Security-Policy"] = self.policy
        elif "frame-ancestors" not in csp:
            response["Content-Security-Policy"] = csp.rstrip("; ") + "; " + self.policy
        return response
