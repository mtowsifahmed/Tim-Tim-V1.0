# Tim-Tim email templates

These two files are the sign-in emails Supabase sends. They are kept here so a change is versioned
instead of living only in a dashboard.

| File | Supabase template | Sent when |
|---|---|---|
| `confirmation.html` | Confirm signup | Someone signs in with an email address for the first time |
| `magic-link.html` | Magic Link | An existing account asks for a code |

## Rules

- `{{ .Token }}` is the 6-digit code and **must** stay in both files. Without it the email has no code to type in the app.
- Keep everything inline and table-based: Gmail strips `<style>` blocks in some clients and ignores modern layout.
- The logo is loaded from `https://tim-tim-v1-app.onrender.com/icons/logo-mark.png`. If the site address ever changes, update it here and re-upload.
- The code box uses `Consolas`/`SF Mono` with wide letter-spacing so the digits stay readable on a phone.

## How to apply a change

1. Edit the file here.
2. Supabase dashboard → project → **Authentication → Emails** → open *Confirm signup* (or *Magic Link*).
3. Paste the whole file into the message body, set the subject to `Your Tim-Tim code is {{ .Token }}`, and **Save**.

Applying with the Management API instead (what the current deployment used):

```python
PATCH https://api.supabase.com/v1/projects/<ref>/config/auth
{ "mailer_templates_confirmation_content": "<full html>",
  "mailer_templates_magic_link_content": "<full html>",
  "mailer_subjects_confirmation": "Your Tim-Tim code is {{ .Token }}",
  "mailer_subjects_magic_link": "Your Tim-Tim code is {{ .Token }}" }
```

After saving, check `mailer_templates_custom_contents` reports `true` for both templates — if it does not,
Supabase is still sending its default email.
