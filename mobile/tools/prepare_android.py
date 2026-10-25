"""Run by build-mobile.bat after Flutter creates the Android folder. Adds the permissions Tim-Tim needs and the app name.
Safe to run more than once."""
import re
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
if not p.exists():
    raise SystemExit("android/app/src/main/AndroidManifest.xml not found. Run build-mobile.bat so Flutter creates the Android folder first.")
t = p.read_text(encoding="utf-8")
need = ["android.permission.INTERNET", "android.permission.RECORD_AUDIO", "android.permission.MODIFY_AUDIO_SETTINGS"]
add = "".join(f'    <uses-permission android:name="{n}"/>\n' for n in need if n not in t)
if add:
    t = re.sub(r"(<manifest[^>]*>\s*\n)", lambda m: m.group(1) + add, t, count=1)
t = re.sub(r'android:label="[^"]*"', 'android:label="Tim-Tim"', t, count=1)
p.write_text(t, encoding="utf-8")
print("AndroidManifest.xml ready (internet, microphone, audio; app name Tim-Tim)")
