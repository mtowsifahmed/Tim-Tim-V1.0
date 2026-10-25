# Tim-Tim and WhatsApp

## What works now (official, safe for your WhatsApp account)
Say or type things like:
- "Open WhatsApp."
- "Message **Mom** on WhatsApp: I'll be late, start without me."
- "WhatsApp **Rahul** that the meeting moved to 5."
- "Open my chat with **Anna**." (opens the chat, sends nothing)

How it works:
1. You keep a small **contact list inside Tim-Tim** (Settings → **WhatsApp contacts**): add people by hand, or import a `.vcf` / `.csv` file exported from your phone's contacts. Set your **default country code** so 10-digit numbers work.
2. Tim-Tim picks the contact by name (it ignores capital letters and accents, and accepts a first name when only one person matches).
3. A confirmation box shows **who** (name and full number) and **exactly what** will be sent. Sending a message always asks; it can never be set to "Always allow".
4. **Windows desktop app**: after you confirm, Tim-Tim opens the chat with your message typed in and presses Send for you (switch this off in Settings if you would rather press Send yourself).
   **Phone and browser**: WhatsApp opens with your message ready; you tap Send (browsers and phones don't let any app press Send for you).
Your contact list stays on the device it was entered on. Only the name and the words you spoke go to the AI services; the phone number is looked up locally.

Export contacts from a phone: **Android**: Contacts → Settings → Export → `.vcf`. **Google Contacts** (contacts.google.com): Export → vCard. **iPhone**: icloud.com → Contacts → select all → Export vCard.

## What it cannot do, and why
| Wish | Why not |
|---|---|
| Read your chats | WhatsApp has **no official way** for any app to read a personal account's messages. |
| Post a status | There is no official way to post a status from another app. |
| Search all your contacts | WhatsApp doesn't share your contact list with other apps; that is why Tim-Tim keeps its own list. |

## The risky way (not built): only if you decide you want it
Unofficial tools can control a WhatsApp account by imitating WhatsApp Web (for example the open-source libraries *Baileys* or *whatsapp-web.js*). They can read chats, list contacts and post status, but:
- It **breaks WhatsApp's Terms of Service**; WhatsApp can **ban the number**, sometimes permanently. Use only a spare number you can afford to lose, never your main one.
- Your **friends' private messages** would be passed to free AI services to be read out or summarised, which is a privacy problem for them, not just you.
- It would have to run **only on your own computer**, never on the shared server, because it holds a login to your account.
- It can stop working whenever WhatsApp changes something.
If you want it anyway, tell me and I will build it as a separate, opt-in, desktop-only add-on with clear warnings.

## The official business route (a different thing)
Meta's **WhatsApp Business Platform** lets a *business number* receive messages people send to it and reply. It does not give access to your personal chats or contacts, needs a Meta business account and verification, and has rules and fees for messages you start. It would suit a "message Tim-Tim's own WhatsApp number" feature, not controlling your personal WhatsApp.
