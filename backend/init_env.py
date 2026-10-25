"""Fills in KEY_ENCRYPTION_SECRET in backend/.env if it is empty (so you never have to run a command to make one)."""
import re
from pathlib import Path

from cryptography.fernet import Fernet

p = Path(__file__).resolve().parent / ".env"
if not p.exists():
    raise SystemExit(".env not found. Copy .env.example to .env first.")
t = p.read_text(encoding="utf-8")
m = re.search(r"(?m)^KEY_ENCRYPTION_SECRET=(.*)$", t)
if m and m.group(1).strip():
    print("KEY_ENCRYPTION_SECRET is already set. Left it alone.")
else:
    key = Fernet.generate_key().decode()
    t = re.sub(r"(?m)^KEY_ENCRYPTION_SECRET=.*$", f"KEY_ENCRYPTION_SECRET={key}", t) if m else t + f"\nKEY_ENCRYPTION_SECRET={key}\n"
    p.write_text(t, encoding="utf-8")
    print("Created KEY_ENCRYPTION_SECRET. Keep it: changing it later makes saved API keys unreadable.")
