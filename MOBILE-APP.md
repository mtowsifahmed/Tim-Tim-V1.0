# Tim-Tim on phones

There are three ways. Start with **Way 1**: it is free, instant and works on both Android and iPhone.

## Way 1: install the web app (recommended for launch)
Open your Tim-Tim address (for example `https://tim-tim-app.onrender.com`) on the phone and sign in.
- **Android (Chrome)**: menu (⋮) → **Install app** (or Settings → *Install Tim-Tim as an app* inside Tim-Tim). It gets your logo, opens full-screen, and works like an app.
- **iPhone (Safari)**: tap **Share** → **Add to Home Screen**. (Must be Safari.)
- **Quick link**: in the desktop app, Settings → **Open on my phone** shows a QR code of your address; scan it with the phone camera.
Hold the big mic button to talk. Allow the microphone when asked. Use headphones if you want to interrupt Tim-Tim by talking.

## Way 2: a real Android app file (APK)
Needs Flutter (you already have it) and the Android SDK that comes with Android Studio.
1. Double-click **`build-mobile.bat`** (it opens your website at `https://tim-tim-app.onrender.com`; if your address is different, first type `set APP_URL=https://your-address` in the same window).
2. It creates `release\Tim-Tim.apk`. Copy it to a phone, open it, allow "install unknown apps" once.
The app is a thin shell around your website, so it always matches the site, and it asks for the microphone properly.
Supports Android 7 and newer (needs the "Android System WebView" updated from Google Play, which phones do automatically).

## Way 3: app stores (later, optional)
- **Google Play**: one-time $25 developer fee, then upload an app bundle built with `flutter build appbundle` signed with your own key (see flutter.dev "Build and release an Android app"). Add your privacy policy link: `https://YOUR-ADDRESS/privacy.html`.
- **Apple App Store**: $99 per year and a Mac are required. Until then iPhone users use Way 1.

## Good to know
- The phone app talks to the same backend and account as the desktop. Your chats, memory and settings follow you.
- Computer actions (open apps, files, typing) need the Windows desktop app; the phone can still set reminders, open web pages and search.
