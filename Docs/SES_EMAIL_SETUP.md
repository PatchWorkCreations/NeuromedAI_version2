# Outbound email with Amazon SES (boto3 + IAM role)

A copy-paste guide for wiring a Django app to send email through Amazon SES,
using the same pattern as AiraMed. The app never holds AWS access keys:
on AWS (ECS Fargate) boto3 picks up credentials from the **task IAM role**.

Two parts:

1. **App side** — what the developer adds to the project (sections 1–5).
2. **DevOps side** — what DevOps sets up in AWS and the Azure pipelines
   (section 6). Azure DevOps runs the build/deploy; the permissions themselves
   live in **AWS IAM**.

---

## How it works

```
Django view ──> myApp/mail.py (send_html_email)
                    │
                    ▼
        Django EMAIL_BACKEND
          ├─ local laptop: console backend (prints the email to the terminal)
          └─ on AWS:       django_ses.SESBackend ──> boto3 ──> Amazon SES
                                                    │
                              credentials from the ECS task IAM role
```

- `django-ses` is the Django email backend. It uses **boto3** under the hood.
- boto3 uses the AWS **default credential chain**. On ECS Fargate that is the
  task role, so no `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` anywhere.
- SES is switched on only when a region env var is present, so local dev
  never calls AWS by accident.

---

## 1. Dependency

Add to `requirements.txt`:

```text
django-ses==4.8.0
```

`django-ses` installs `boto3` / `botocore` itself. Run the security scan
(`pip-audit -r requirements.txt`) after adding it — the Azure build fails on
Critical/High CVEs.

---

## 2. Settings (`settings.py`)

Put this near the top of settings, after `ENVIRONMENT` is read:

```python
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")

# Outbound email via Amazon SES (django-ses).
# On AWS (ECS/etc.) credentials come from the task IAM role — no access keys required.
# Region: DevOps sets AWS_REGION; AWS_SES_REGION_NAME also accepted.
_default_from_by_env = (
    "support@example.org" if ENVIRONMENT == "prod" else "support-dev@example.org"
)
CONTACT_ADMIN_EMAIL = os.environ.get("CONTACT_ADMIN_EMAIL", _default_from_by_env)
DEFAULT_FROM_EMAIL = (
    (os.environ.get("DEFAULT_FROM_EMAIL") or _default_from_by_env)
    .strip()
    .strip('"')
    .strip("'")
)

# Do not set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY here.
# boto3 / django-ses use the task IAM role on AWS (default credential chain).
AWS_SES_REGION_NAME = (
    os.environ.get("AWS_SES_REGION_NAME")
    or os.environ.get("AWS_REGION")
    or os.environ.get("AWS_DEFAULT_REGION")
    or ""
).strip()
AWS_SES_REGION_ENDPOINT = (
    f"email.{AWS_SES_REGION_NAME}.amazonaws.com" if AWS_SES_REGION_NAME else ""
)

# Force console with EMAIL_USE_CONSOLE=1 (handy for local laptop without IAM).
_force_console = (os.environ.get("EMAIL_USE_CONSOLE") or "").strip().lower() in {
    "1",
    "true",
    "yes",
}
if AWS_SES_REGION_NAME and not _force_console:
    EMAIL_BACKEND = "django_ses.SESBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
```

Replace `example.org` with the new project's verified sender domain.

**Do not** add `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` settings. DevOps
flagged these on review: with an IAM role they are not needed, and leaving them
in invites someone to paste keys into env vars.

---

## 3. Shared mail helper (`myApp/mail.py`)

Every email in the app goes through one function, so the transport can change
without touching each feature:

```python
"""Shared outbound email helper (Django mail API)."""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import EmailMessage

logger = logging.getLogger(__name__)


class MailNotConfiguredError(Exception):
    """Raised when DEFAULT_FROM_EMAIL is missing."""


def email_ready() -> bool:
    return bool((getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip())


def send_html_email(
    *,
    to: list[str],
    subject: str,
    html_body: str,
    reply_to: list[str] | None = None,
) -> None:
    """Send one HTML email via the configured Django email backend."""
    from_email = (settings.DEFAULT_FROM_EMAIL or "").strip()
    if not from_email:
        raise MailNotConfiguredError("DEFAULT_FROM_EMAIL is not configured.")

    recipients = [addr.strip() for addr in to if (addr or "").strip()]
    if not recipients:
        raise MailNotConfiguredError("No recipient address provided.")

    message = EmailMessage(
        subject=subject,
        body=html_body,
        from_email=from_email,
        to=recipients,
        reply_to=reply_to or None,
    )
    message.content_subtype = "html"
    try:
        message.send(fail_silently=False)
    except Exception:
        # Do not log subject/body/recipients (may contain sensitive content).
        logger.exception("Outbound email send failed")
        raise
```

Calling it from a feature:

```python
from myApp.mail import MailNotConfiguredError, send_html_email

send_html_email(
    to=[settings.CONTACT_ADMIN_EMAIL],
    subject="New contact form message",
    html_body=body_html,          # html.escape() any user input first
    reply_to=[visitor_email],
)
```

If the old project used Resend (or another HTTP email API), replace each direct
`requests.post(...)` call with `send_html_email(...)` and delete the old API
key settings.

**Health data:** keep patient details (diagnoses, transcripts, summaries) out of
subjects and bodies. Send a link back to the app instead.

---

## 4. Environment variables

| Variable | Where | Value |
|----------|-------|-------|
| `ENVIRONMENT` | every env | `dev`, `stg`, or `prod` — picks the default From address |
| `AWS_REGION` | AWS task (DevOps) | SES region, e.g. `us-east-1`. `AWS_SES_REGION_NAME` also works |
| `DEFAULT_FROM_EMAIL` | optional | Override the From address. Must be a verified SES identity |
| `CONTACT_ADMIN_EMAIL` | optional | Inbox for internal notifications |
| `EMAIL_USE_CONSOLE` | **local only** | `1` to print mail to the terminal. Never set on AWS |

`.env.example` block:

```bash
# Outbound email — Amazon SES (IAM role on AWS)
# DevOps sets AWS_REGION=us-east-1 on the task; django-ses reads it.
ENVIRONMENT=dev
CONTACT_ADMIN_EMAIL=support-dev@example.org
DEFAULT_FROM_EMAIL=support-dev@example.org
AWS_REGION=us-east-1
# Optional overrides:
# AWS_SES_REGION_NAME=us-east-1
# EMAIL_USE_CONSOLE=1
```

---

## 5. Local testing

A laptop has no task role, so print mail instead of calling SES:

```bash
# .env
EMAIL_USE_CONSOLE=1
AWS_REGION=us-east-1
```

```bash
python manage.py shell -c "
from myApp.mail import send_html_email
send_html_email(to=['test@example.com'], subject='SES wiring test', html_body='<p>Hello</p>')
print('SEND_OK')
"
```

The email prints in the terminal. Real SES delivery can only be tested after
deploying to an AWS environment.

---

## 6. DevOps checklist (AWS + Azure)

Send this section to DevOps when the new project is pushed.

### 6a. SES identity and account

- [ ] Verify the sending **domain** (or address) in SES, in the same region as
      `AWS_REGION` (e.g. `us-east-1`).
- [ ] Publish **DKIM** (3 CNAMEs), **SPF**, and a **DMARC** record for the domain.
      Without these, mail is more likely to land in spam.
- [ ] Move SES **out of the sandbox**. In sandbox, SES only sends to verified
      addresses.
- [ ] If the app handles health data: confirm the **AWS BAA** covers the account.
- [ ] Optional: a configuration set + SNS for bounce/complaint tracking.

### 6b. Task role permission (the app's runtime permission)

Attach this inline policy to each ECS **task role** (dev, stg, prod):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowSendingEmails",
      "Effect": "Allow",
      "Action": ["ses:SendEmail", "ses:SendRawEmail"],
      "Resource": "*"
    }
  ]
}
```

Tighter option: set `Resource` to the identity ARN, e.g.
`arn:aws:ses:us-east-1:<account-id>:identity/example.org`.

### 6c. Builder role permission (the deploy pipeline's permission)

If the Pulumi deployer creates that policy (an `aws:iam:RolePolicy` resource),
the **builder role** that Azure Pipelines runs as must be allowed to attach it:

```json
{
  "Effect": "Allow",
  "Action": ["iam:PutRolePolicy", "iam:GetRolePolicy", "iam:DeleteRolePolicy"],
  "Resource": "arn:aws:iam::<account-id>:role/<project>-*-task-role-*"
}
```

On AiraMed, the first DEV deploy after the SES change failed on exactly this:

```text
AccessDenied: User: arn:aws:sts::<account>:assumed-role/<...>-builder-role-<...>
is not authorized to perform: iam:PutRolePolicy on resource:
role <...>-fargate-<app>-dev-task-role-<...>
```

Granting this up front avoids a failed first deploy.

### 6d. Task environment

- [ ] `AWS_REGION=us-east-1` (or the SES region)
- [ ] `ENVIRONMENT=dev` / `stg` / `prod`
- [ ] `DEFAULT_FROM_EMAIL` only if it differs from the default
- [ ] **No** `EMAIL_USE_CONSOLE`
- [ ] **No** `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`

---

## 7. Release flow (Azure DevOps)

1. Pull latest `develop` → create `feature/<name>`.
2. Commit the app changes above. Push the branch.
3. Open a PR `feature/<name>` → `develop`.
4. Link a work item (branch policy requires it).
5. Run **Premerge**. Resolve every reviewer comment.
6. Get the required approvals. A new push resets approvals.
7. Merge → run **Build** on `develop`.
8. Run **Deploy** with that build's artifact → **DEV**.
9. Test email on the dev site. Check **Inbox and Spam**.

---

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Email prints in the logs on AWS | `AWS_REGION` missing, or `EMAIL_USE_CONSOLE` set | Set region, remove `EMAIL_USE_CONSOLE` |
| `AccessDenied ... ses:SendRawEmail` | Task role has no SES policy | Section 6b |
| `AccessDenied ... iam:PutRolePolicy` during deploy | Builder role can't attach the policy | Section 6c |
| `MessageRejected: Email address is not verified` | From not verified, or SES still in sandbox | Section 6a |
| Arrives in spam | DKIM/SPF/DMARC missing, or From domain mismatch | Section 6a |
| `MailNotConfiguredError` | `DEFAULT_FROM_EMAIL` empty | Set it, or set `ENVIRONMENT` so the default applies |
| Azure build fails on Critical/High CVEs | Outdated pins | `pip-audit -r requirements.txt` and bump |
