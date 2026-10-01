# Multilingual Voice AI

A real-time, multilingual, conversational voice AI web app. The user speaks in
any supported language, the app transcribes the speech, generates a
**human-like** reply in the same language, and speaks the reply back.

Pipeline:

```
User microphone
   ↓
Speech-to-Text  (Groq · Whisper Large V3 Turbo)
   ↓
Language detection (auto from Whisper metadata)
   ↓
LLM / NLG       (Google Gemini · free-tier model)
   ↓
Natural Language Generation (human-like, multilingual)
   ↓
Text-to-Speech (ElevenLabs · multilingual voice)
   ↓
🔊 Natural-sounding spoken response
```

Initial test languages: **English, Hindi, Telugu**. The catalogue also ships
with Tamil, Kannada, Malayalam, Bengali, Marathi, Gujarati, Punjabi, Urdu,
Odia, Spanish, French, German — and adding more is a one-line change in
`backend/app/services/language_service.py`.

---

## 1. Project overview

* **Frontend** — Next.js 16 + React 19 + TypeScript + Tailwind CSS 4 +
  shadcn/ui. A single page renders the microphone button, the conversation
  bubbles, the live pipeline progress, the detected-language badge, and an
  audio player for AI replies.
* **Backend** — Python 3.12 + FastAPI. Modular service architecture:
  separate services for STT, LLM/NLG, TTS, and language catalogue. Three
  endpoints under `/api`: `/stt`, `/chat`, `/tts`. Plus `/api/health` and
  `/api/languages`.
* **API keys** — every key (`GROQ_API_KEY`, `GEMINI_API_KEY`,
  `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`) lives **only** in
  `backend/.env` on the server. The browser never sees them.

### Repository layout

```
project-root/
├── backend/                      Python FastAPI server
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py             env-based settings (no key exposure)
│   │   ├── main.py               FastAPI app + CORS + rate limiter
│   │   ├── models/__init__.py    Pydantic schemas (STT/Chat/TTS/Health)
│   │   ├── utils/__init__.py     language normalisation + error sanitiser
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── health.py         GET  /api/health
│   │   │   ├── languages.py      GET  /api/languages
│   │   │   ├── stt.py            POST /api/stt
│   │   │   ├── chat.py           POST /api/chat
│   │   │   └── tts.py            POST /api/tts
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── language_service.py  catalogue + NLG system prompt
│   │       ├── stt_service.py       Groq Whisper Large V3 Turbo
│   │       ├── llm_service.py       Google Gemini
│   │       └── tts_service.py       ElevenLabs multilingual
│   ├── requirements.txt
│   ├── .env.example              copy → .env and fill in your keys
│   └── run.py                    `python run.py` shortcut
└── src/                          Next.js app (Next.js convention)
    ├── app/
    │   ├── layout.tsx            root layout
    │   ├── page.tsx              main page — orchestrates the pipeline
    │   └── globals.css
    ├── components/
    │   ├── ui/                   shadcn/ui component set
    │   └── voice/                voice-specific components
    │       ├── AudioPlayer.tsx
    │       ├── ConversationView.tsx
    │       ├── ErrorBanner.tsx
    │       ├── LanguageBadge.tsx
    │       ├── MicrophoneButton.tsx
    │       ├── PipelineProgress.tsx
    │       └── ProviderStrip.tsx
    ├── hooks/
    │   └── use-microphone.ts     MediaRecorder wrapper hook
    ├── lib/
    │   ├── languages.ts          UI-side language metadata
    │   └── utils.ts
    ├── services/
    │   └── voiceApi.ts          typed fetch wrappers for /api/*
    └── types/
        └── voice.ts             shared TS types mirroring backend schemas
```

> The current scaffold uses the Next.js convention where the app lives under
> `src/` at the project root (this is what the fullstack-dev tool generates).
> All the source files described under `frontend/` in the original brief
> live under `src/` here — they are functionally identical.

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│ Browser                                                          │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ src/app/page.tsx                                             │ │
│  │   ├── useMicrophone() → MediaRecorder → Blob                │ │
│  │   ├── PipelineProgress   (Listening/Thinking/Speaking UI)   │ │
│  │   ├── ConversationView   (chat bubbles + audio player)      │ │
│  │   └── src/services/voiceApi.ts (relative fetch, no keys)    │ │
│  └──────────────────────────────────────────────────────────────┘
│                              │
│            fetch /api/stt?XTransformPort=8000  (relative URL)
│            fetch /api/chat?XTransformPort=8000
│            fetch /api/tts?XTransformPort=8000
└──────────────────────────────┼───────────────────────────────────┘
                               │
                        Caddy gateway (:81)
                               │
┌──────────────────────────────┼───────────────────────────────────┐
│ FastAPI (:8000)              ▼                                  │
│  /api/stt   → stt_service  → Groq Whisper Large V3 Turbo       │
│  /api/chat  → llm_service  → Google Gemini (free tier)         │
│  /api/tts   → tts_service  → ElevenLabs (multilingual)         │
│  + per-IP rate limiter (60 req/min)                             │
│  + CORS allowlist (localhost:3000 + preview-*.space-z.ai)      │
│  + error sanitiser (never returns API keys in messages)        │
└──────────────────────────────────────────────────────────────────┘
```

Key design decisions:

1. **No keys in browser.** The browser only knows `/api/stt`, `/api/chat`,
   `/api/tts`. The FastAPI server holds the keys and proxies to the
   upstream providers.
2. **Language auto-detection.** Whisper Large V3 Turbo is multilingual;
   we let it auto-detect instead of forcing `language=` so users can
   switch language mid-session without UI changes.
3. **Human-like NLG.** The system prompt in
   `backend/app/services/language_service.py` explicitly forbids the
   "Certainly / As an AI / Sure, I would be happy to…" patterns and
   tells the model to match the user's language and register.
4. **Conversation memory.** The browser keeps the last 20 turns in
   `historyRef`; each `/api/chat` call sends only the last 10 (server
   clamps again), so context works without unbounded growth.
5. **Error codes everywhere.** Every failure path returns
   `{success: false, error: "friendly message", error_code: "stable_code"}`
   so the frontend can map a stable code to a tailored message.

---

## 3. Features

* 🎤 Real browser microphone capture (`MediaRecorder` + `getUserMedia`),
  with permission handling, animated record button, recording timer.
* 📝 Live transcription with detected-language badge.
* 🧠 Conversational LLM tuned for human-like replies in the user's
  language, with conversation memory.
* 🔊 Spoken replies auto-play; user can replay each AI turn via an
  inline audio player.
* 🚦 Visual pipeline indicator (Listening → Transcribing → Thinking →
  Speaking) that maps 1:1 to real backend calls — no fake progress.
* 🌐 15+ supported languages out of the box, easily extensible.
* 🔒 API keys never leave the server. CORS allowlist + per-IP rate
  limit + error sanitiser (redacts anything that looks like a key).
* 📱 Responsive mobile/desktop layout.
* ⚙️ Configurable models via env (`GROQ_STT_MODEL`, `GEMINI_MODEL`,
  `ELEVENLABS_MODEL_ID`, `ELEVENLABS_VOICE_ID`).

---

## 4. Technology stack

| Layer    | Technology                                                        |
| -------- | ----------------------------------------------------------------- |
| Frontend | Next.js 16, React 19, TypeScript 5, Tailwind CSS 4, shadcn/ui      |
| Backend  | Python 3.12, FastAPI 0.128, Pydantic v2, Uvicorn                  |
| STT      | Groq SDK + Whisper Large V3 Turbo (multilingual, auto-detect)     |
| LLM/NLG  | Google GenAI SDK + Gemini free-tier (default `gemini-2.0-flash`)   |
| TTS      | ElevenLabs SDK + multilingual voice (default `eleven_multilingual_v2`) |

---

## 5. Prerequisites

* **Node.js ≥ 20** and **bun** (or npm) for the frontend.
* **Python ≥ 3.10** (developed on 3.12) for the backend.
* A free **Groq** account.
* A free **Google Gemini** API key.
* A free **ElevenLabs** account.
* A modern browser that supports `MediaRecorder` (Chrome, Edge, Firefox,
  Safari 14.1+). HTTPS is required by the browser for `getUserMedia` —
  the dev sandbox provides HTTPS automatically; on localhost it works
  without HTTPS too.

---

## 6. API account setup

### Groq (STT)

1. Create a free account at <https://console.groq.com>.
2. Open **API Keys** → **Create API Key** → copy it.
3. Free tier limits (as of writing): ~30 requests/min on Whisper Large V3
   Turbo, generous daily caps. See <https://console.groq.com/docs/rate-limits>.

### Google Gemini (LLM)

1. Visit <https://aistudio.google.com/apikey>.
2. Sign in with a Google account → **Create API key** → copy it.
3. Free tier limits: <https://ai.google.dev/pricing>. As of writing,
   `gemini-2.0-flash` gives 15 RPM / 1500 requests/day / 1M tokens/min
   on the free tier.

### ElevenLabs (TTS)

1. Create a free account at <https://elevenlabs.io>.
2. **Profile → API Keys → Create API key** → copy it.
3. **Voice Lab**: pick a multilingual voice (e.g. *Rachel*, *Adam*,
   *Antoni*, *Bella*) → open the voice page → copy the **Voice ID**.
4. Free tier limits: 10,000 characters/month on the free plan. Enough for
   testing the pipeline but tight — keep replies short.
5. Default model `eleven_multilingual_v2` supports 29+ languages.

---

## 7. API key setup

All keys live in `backend/.env`. Copy the template and edit it:

```bash
# Windows CMD
cd backend
copy .env.example .env

# Windows PowerShell
Copy-Item .env.example .env

# macOS / Linux / Git Bash
cp .env.example .env
```

Then open `backend/.env` in VS Code and fill in your own keys:

```dotenv
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GROQ_STT_MODEL=whisper-large-v3-turbo

GEMINI_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
GEMINI_MODEL=gemini-2.0-flash

ELEVENLABS_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ELEVENLABS_VOICE_ID=your-voice-id-here        # e.g. 21m00Tcm4TlvDq8ikWAM
ELEVENLABS_MODEL_ID=eleven_multilingual_v2

BACKEND_PORT=8000
BACKEND_CORS_ORIGINS=http://localhost:3000
```

> The `.env.example` file is the canonical list of variables. Anything in
> `BACKEND_*` has a sensible default, so you only really need to fill the
> four provider-related keys.

---

## 8. Environment variables

| Variable                  | Required | Default                       | Notes                                                   |
| ------------------------- | -------- | ----------------------------- | ------------------------------------------------------- |
| `GROQ_API_KEY`            | ✅ yes   | —                             | Get from <https://console.groq.com>                    |
| `GROQ_STT_MODEL`          | ❌       | `whisper-large-v3-turbo`      | Alternative: `whisper-large-v3`                         |
| `GEMINI_API_KEY`          | ✅ yes   | —                             | Get from <https://aistudio.google.com/apikey>          |
| `GEMINI_MODEL`            | ❌       | `gemini-2.0-flash`            | Update if Google releases new free-tier models           |
| `ELEVENLABS_API_KEY`      | ✅ yes   | —                             | Get from <https://elevenlabs.io>                        |
| `ELEVENLABS_VOICE_ID`     | ✅ yes   | —                             | Copy from the Voice Lab page on ElevenLabs              |
| `ELEVENLABS_MODEL_ID`     | ❌       | `eleven_multilingual_v2`      | Alternative: `eleven_turbo_v2_5`                        |
| `BACKEND_PORT`            | ❌       | `8000`                        | Port FastAPI listens on                                 |
| `BACKEND_CORS_ORIGINS`    | ❌       | `http://localhost:3000`       | Comma-separated list of allowed origins                  |
| `BACKEND_MAX_AUDIO_MB`   | ❌       | `25`                          | Audio upload size cap                                   |
| `BACKEND_MAX_HISTORY`     | ❌       | `10`                          | Max conversation turns sent to Gemini                    |

---

## 9. Backend installation

> Commands below are Windows-friendly. The project was developed and tested
> in VS Code on Windows. macOS/Linux users can use the equivalent commands
> in their shell.

```powershell
cd backend

# Create and activate a virtual environment (Windows)
python -m venv venv
venv\Scripts\activate

# Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Copy the env template (only the first time)
copy .env.example .env
# Now edit .env and fill in your API keys.
```

macOS / Linux / Git Bash:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your keys.
```

---

## 10. Frontend installation

```powershell
# From the project root (not the backend folder)
npm install
# or
bun install
```

The frontend talks to the backend via relative paths like
`/api/stt?XTransformPort=8000`. No additional proxy configuration is
needed in the dev sandbox. If you ever run the Next.js and FastAPI servers
on different machines, set `BACKEND_CORS_ORIGINS` in `backend/.env` to
the Next.js origin and update `BACKEND_PORT` in
`src/services/voiceApi.ts` to match.

---

## 11. How to run

You need **two terminal windows** (one for backend, one for frontend).

### Terminal 1 — backend

```powershell
cd backend
venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

Or the shortcut:

```powershell
python run.py
```

You should see `Uvicorn running on http://127.0.0.1:8000`. The interactive
API docs are at <http://127.0.0.1:8000/docs>.

### Terminal 2 — frontend

```powershell
# From the project root
npm run dev
# or
bun run dev
```

The Next.js dev server starts on <http://localhost:3000>.

Open <http://localhost:3000> in your browser. You should see the page
header "Multilingual Voice AI", the provider strip showing which providers
are configured, and the big microphone button.

Click the mic button, allow microphone permission, speak, and click again
to stop. The pipeline then runs through Transcribe → Think → Speak.

---

## 12. Testing

The README ships with an explicit manual test plan. Run all eight:

### TEST 1 — English end-to-end

1. Click the mic button, speak a short English question, e.g.
   *"What is AI in simple terms?"*
2. Click again to stop.
3. Expected: the user bubble fills with the transcription, an
   "English" badge appears, the AI bubble shows a thinking spinner, then
   the reply fills in and the audio auto-plays.

### TEST 2 — Hindi end-to-end

1. Click the mic, speak in Hindi, e.g.
   *"AI అంటే ఏంటి కొంచెం సులభంగా చెప్పండి"* (or any natural Hindi).
2. Click again to stop.
3. Expected: detected language shows **Hindi (hi)**, AI reply is in
   Hindi, audio plays with natural Hindi pronunciation.

### TEST 3 — Telugu end-to-end

1. Click the mic, speak in Telugu, e.g.
   *"నాకు AI గురించి చెప్పండి"* (tell me about AI).
2. Click again to stop.
3. Expected: detected language shows **Telugu (te)**, AI reply is in
   Telugu script, audio is natural Telugu speech.

### TEST 4 — Conversation context

1. Speak: *"What is RAG?"*
2. After the reply, speak: *"Why is it useful?"*
3. Expected: the assistant answers about RAG in the second reply without
   you having to re-explain what RAG is. The conversation history is sent
   to `/api/chat` automatically.

### TEST 5 — No microphone permission

1. In your browser, revoke microphone permission for the page.
2. Click the mic button.
3. Expected: red error banner:
   *"Microphone permission was denied. Allow mic access in your browser and try again."*

### TEST 6 — Missing API key

1. Stop the backend, edit `backend/.env`, blank out one of the keys
   (e.g. `GROQ_API_KEY=`), restart the backend.
2. Click the mic and speak.
3. Expected: a friendly message telling you exactly which key is missing
   and where to add it (e.g.
   *"The backend has no Groq API key configured. Add GROQ_API_KEY to backend/.env."*).
   The provider strip at the top will also show that provider as
   "not configured".

### TEST 7 — Invalid audio

1. Use the API docs at <http://127.0.0.1:8000/docs> to call `/api/stt`
   with a `.txt` file (not audio).
2. Expected: `{"success": false, "error_code": "stt_unsupported_format", ...}`.

### TEST 8 — API rate limit

1. Hammer the backend with `curl` in a tight loop:
   ```powershell
   for ($i=0; $i -lt 70; $i++) { curl http://127.0.0.1:8000/api/health }
   ```
2. Expected: after 60 requests in a minute, the backend returns
   `{"success": false, "error_code": "rate_limited", ...}` with HTTP 429.

---

## 13. Supported languages

Out of the box:

| Code | Language   | Flag |
| ---- | ---------- | ---- |
| en   | English   | 🇬🇧 |
| hi   | Hindi      | 🇮🇳 |
| te   | Telugu     | 🇮🇳 |
| ta   | Tamil      | 🇮🇳 |
| kn   | Kannada    | 🇮🇳 |
| ml   | Malayalam  | 🇮🇳 |
| bn   | Bengali    | 🇧🇩 |
| mr   | Marathi    | 🇮🇳 |
| gu   | Gujarati   | 🇮🇳 |
| pa   | Punjabi    | 🇮🇳 |
| ur   | Urdu       | 🇵🇰 |
| or   | Odia       | 🇮🇳 |
| es   | Spanish    | 🇪🇸 |
| fr   | French     | 🇫🇷 |
| de   | German     | 🇩🇪 |

Adding a new language is a one-line change in
`backend/app/services/language_service.py` — append a row to
`SUPPORTED_LANGUAGES`. The frontend catalogue in
`src/lib/languages.ts` should mirror it for instant UI rendering.

---

## 14. Common errors

| Symptom                                                  | Cause / Fix                                                                                                          |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| "Backend unreachable on port 8000…" in the provider strip | The FastAPI server isn't running. Start it: `cd backend && uvicorn app.main:app --port 8000 --reload`.            |
| `stt_no_api_key`                                          | `GROQ_API_KEY` is empty in `backend/.env`. Restart the backend after editing `.env`.                                |
| `llm_model_not_found`                                    | The model name in `GEMINI_MODEL` doesn't exist on your account. Try `gemini-2.0-flash` or `gemini-1.5-flash`.      |
| `tts_voice_not_found`                                    | `ELEVENLABS_VOICE_ID` is wrong, or that voice isn't on your account. Re-copy the Voice ID from the Voice Lab.      |
| `tts_rate_limit`                                          | You've used up the ElevenLabs free-tier monthly character quota. Wait for the next reset or upgrade.                |
| `mic_permission_denied`                                  | The browser blocked microphone access. Click the lock icon in the address bar and allow microphone.               |
| No audio plays in AI replies                             | Browser autoplay policy sometimes blocks the first play. Use the manual ▶ button on the inline audio player.      |
| Hot-reload picks up `.env` changes only after a restart | `uvicorn --reload` watches code, not env files. Ctrl-C and restart the backend when you change `backend/.env`.     |

---

## 15. Troubleshooting

* **`ModuleNotFoundError: No module named 'app'`** — you ran uvicorn from
  the wrong folder. Always start the backend from inside `backend/` so
  that `app.main` resolves.
* **CORS error in the browser console** — your frontend origin isn't in
  the allowlist. Add it to `BACKEND_CORS_ORIGINS` in `backend/.env` and
  restart the backend.
* **Whisper returns empty transcripts** — make sure the recording is
  longer than ~0.5 seconds. Very short clips can produce empty results.
  The UI will surface `stt_empty_result` with a friendly message.
* **Telugu/Hindi replies come back in English** — Gemini occasionally
  falls back to English when the system prompt is overridden by safety
  or other filters. Re-running the pipeline usually fixes it. If it
  persists, switch `GEMINI_MODEL` to `gemini-1.5-flash` (it tends to be
  stricter on instruction following for low-resource languages).
* **Recording time keeps increasing without audio capture** — your
  browser is likely denying mic permission silently. Check the
  permissions icon in the address bar.
* **Backend log shows stack traces but the UI shows a friendly
  message** — that's intentional. The backend logs the full exception
  for debugging; the API response carries a sanitised, redacted message.

---

## 16. Future improvements

* **Streaming STT** — switch from buffered upload to a WebSocket stream
  so the user sees partial transcripts while still speaking.
* **Streaming LLM** — use Gemini's streaming endpoint so the reply
  appears token-by-token.
* **Streaming TTS** — pipe the ElevenLabs streaming response directly
  into a `<audio>` MediaSource so speech starts before generation
  finishes. The architecture already isolates `synthesizeSpeech` so this
  is a contained change.
* **Persistent conversation memory** — move the in-memory
  `historyRef` into a server-side store (SQLite via Prisma is already
  available in the scaffold) so conversations survive refreshes.
* **Voice activity detection (VAD)** — automatically stop recording
  when the user pauses, so they don't need to click a second time.
* **Local/open-source fallbacks** — see the next section for which
  components are easy to swap out.
* **Authentication + multi-tenant** — each user gets their own history
  and provider quotas.
* **Mobile PWA** — add a manifest + service worker for installable,
  offline-capable mobile UX.
* **WebRTC for ultra-low-latency** — replace the current request/response
  pipeline with a WebRTC audio track for sub-second round-trips.

---

## 17. Replaceable components (open-source / local fallbacks)

If you don't want to rely on a hosted provider, every layer has a
well-tested open-source alternative. The service classes are intentionally
small and isolated, so swapping them is a contained change:

| Layer | Hosted (current)       | Local / open-source alternative                                |
| ----- | ---------------------- | ------------------------------------------------------------- |
| STT   | Groq Whisper           | `faster-whisper` running locally on CPU/GPU, or `whisper.cpp` |
| LLM   | Google Gemini          | `ollama` running `llama3.1:8b` or `qwen2.5:7b-instruct` locally; expose an OpenAI-compatible endpoint and rewrite `llm_service.py` |
| TTS   | ElevenLabs             | `piper` (fast local neural TTS, supports many languages), or `Coqui TTS` |

The interface between the route handler and the service is just a single
async method (`transcribe`, `generate`, `synthesise`), so each swap is
one file.

---

## 18. Manual API reference (curl)

Run these against a local backend on port 8000.

```bash
# Health check
curl http://127.0.0.1:8000/api/health

# List supported languages
curl http://127.0.0.1:8000/api/languages

# STT (replace recording.webm with a real audio file you recorded)
curl -X POST http://127.0.0.1:8000/api/stt \
  -F "file=@recording.webm;type=audio/webm"

# Chat
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What is AI?","language":"en","conversation_history":[]}'

# TTS
curl -X POST http://127.0.0.1:8000/api/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"AI is about teaching computers to do things that normally need human intelligence.","language":"en"}' \
  | python -c "import sys,json,base64; open('out.mp3','wb').write(base64.b64decode(json.load(sys.stdin)['audio_base64']))"
```

Interactive OpenAPI docs are at <http://127.0.0.1:8000/docs> when the
backend is running.

---

## 19. License

MIT — do whatever you want with this code. The third-party APIs you call
have their own terms; please respect them.
