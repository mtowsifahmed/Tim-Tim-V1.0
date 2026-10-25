# Free-tier providers used by Tim-Tim

Free limits change often and some sources disagree, so treat the numbers as a guide. Last checked: October 2026.
Run `python check_providers.py` (in `backend`) any time: it tests every key you have and tells you what is wrong.

## Language models (the rotation tries them in this order)
| Provider | Free key | Notes (checked Oct 2026) |
|---|---|---|
| **Google Gemini** | https://aistudio.google.com/apikey | Free tier is per Google project (not per key), resets at midnight Pacific. **`gemini-2.0-flash` was shut down on 1 June 2026** and `gemini-2.5-flash` is scheduled to shut down on 16 Oct 2026, so Tim-Tim tries `gemini-3.5-flash` first and falls back automatically. Reported limits for 3.5 Flash vary by source (about 15 requests/min and up to ~1,500/day, others report far fewer): check your AI Studio page. |
| **Groq** | https://console.groq.com/keys | Free tier, no card. About 30 requests/min; daily token/request limits per model (older `llama-3.x` ids were retired with HTTP 404s). Tim-Tim's ladder now leads with `openai/gpt-oss-120b` and `openai/gpt-oss-20b`, then `qwen/qwen3.8-27b`, then the llama models; retired ids are skipped automatically. |
| **Cerebras** | https://cloud.cerebras.ai | Free tier with small daily limits. Check the console for current model names. |
| **SambaNova** | https://cloud.sambanova.ai | Free tier with rate limits. Check the console. |
| **OpenRouter** | https://openrouter.ai/keys | Models whose id ends in `:free`. Tim-Tim discovers a working one if the default disappears. Daily limits are small unless you add credit. |
| **Mistral** | https://console.mistral.ai | "Experiment" plan (free, rate limited). |
| **NVIDIA NIM** | https://build.nvidia.com | Free developer credits/limits. Check the page. |
| **Your own gateway** | any OpenAI-compatible URL | Set `CUSTOM_LLM_BASE_URL`, `CUSTOM_LLM_API_KEY`, `CUSTOM_LLM_MODEL` in `.env`. Same for `CUSTOM_STT_*`, `CUSTOM_TTS_*`, `CUSTOM_EMBED_*`. |

You only need ONE key to start — and the Gemini key covers **chat, speech recognition and the spoken voice**, so a single
free key gives you the whole companion. More keys = more free quota (and more voice options) before anyone is told to wait.
Many accounts on one provider to dodge limits can get keys banned; don't.

## Speech-to-text
| Provider | Free key | Notes |
|---|---|---|
| **Google Gemini** | same Gemini key | `gemini-3.5-transcribe` hears the utterance you record. No extra key: the key that answers chat also hears you. Free tier; accuracy drops on noisy audio, and it is not real-time (the whole utterance is sent at once). |
| **Cloudflare Workers AI** | https://dash.cloudflare.com | `@cf/openai/whisper-large-v3-turbo`. **10,000 free neurons every day** (about 240 minutes of audio), no card. Needs both `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` — the account id is part of the URL. |
| **Groq Whisper** | same Groq key | Free tier, per-minute and per-day audio limits (see Groq's rate-limit page). Fast, and strong on noisy speech. |
| **ElevenLabs Scribe** | same ElevenLabs key | `scribe_v1`, covered by the free plan's monthly credits — the same key can also speak. |
| **Deepgram** | https://console.deepgram.com | **One-time $200 credit**, no card, doesn't expire, but it does not renew. Covers a very large amount of speech. |
| Custom gateway | `CUSTOM_STT_*` | Any OpenAI-compatible `/audio/transcriptions` server. |

## Text-to-speech (voices)
| Provider | Free key | Notes |
|---|---|---|
| **Google Gemini** | same Gemini key | `gemini-3.8-flash-tts` speaks the reply. 30 prebuilt voices; Tim-Tim maps the calm male voice to **Charon** and the expressive female one to **Aoede**. Free tier, no extra key — this is the default voice now. |
| **Groq Orpheus** | same Groq key | `canopylabs/orpheus-v1-english` — voices `troy` (calm male) and `hannah` (expressive female). Reuses the chat key, but unlike chat **Groq bills this per character** and limits each request to 200 characters (Tim-Tim splits long sentences). WAV output. |
| **Cloudflare Workers AI** | same Cloudflare account | `@cf/myshell-ai/melotts`, falling back to `@cf/deepgram/aura-1`. Shares the free daily neuron allowance with Cloudflare's speech recognition. |
| **Deepgram Aura** | same Deepgram key | Uses the same $200 one-time credit (Aura-1 is about $0.015 per 1,000 characters). No card. |
| **ElevenLabs** | https://elevenlabs.io | Free plan: 10,000 credits/month (about 10 minutes). **Not licensed for commercial use and requires attribution**, so it suits personal testing. Since Pro is a paid plan, leave the key empty if you charge anyone. Most expressive voices. |
| **Edge TTS** | none | Microsoft's read-aloud voices through the unofficial `edge-tts` package. No key, no account, always the last fallback. Unofficial, so it could stop working one day. |
| Custom gateway | `CUSTOM_TTS_*` | Any OpenAI-compatible `/audio/speech` server. |

Not included on purpose: Google Cloud and Azure speech need a billing account with a card, which conflicts with your $0 rule. You can still add them later through the custom gateway.

## Supabase (database + login), free plan
Free projects pause after about a week without activity (open the dashboard to wake it). The built-in email sender allows only a few emails per hour; use a free SMTP sender for more.

## Pro users and their own keys
Pro (granted by you in the admin panel) can paste their own keys under Settings → API keys. Requests then go straight to their provider, never through your rotation, and their limit is whatever their own plan allows.
