# Vidya voice (speech-to-speech)

Vidya speaks. The home composer has an optional voice capsule: push to talk, and
Vidya replies in spoken audio. It is calm and optional — typing always works.

## Why this shape

The provider key's tier exposes **TTS** models and **audio-capable multimodal**
models, but **not** the realtime WebSocket Live (native-audio-dialog) API. So the
same speech-to-speech experience is composed from REST, which this tier supports:

```
mic audio  ─►  gemini-2.5-flash            (understand the learner + reply, plain language)
           ─►  gemini-2.5-flash-preview-tts (speak the reply)   ─►  spoken audio
```

Both steps retry transient provider errors (429/503/404 under load) and fall back
across models (`gemini-flash-latest`, `gemini-2.0-flash`; `gemini-3.1-flash-tts-preview`).
If the tier later gains the Live model, the capsule upgrades to the WebSocket path
with no env change.

## The security boundary

- The provider key is read **server-side only** from `CLSS_AIFABRIC_DEV_GEMINI_API_KEY`.
  It never reaches the browser, never becomes a `NEXT_PUBLIC_` var, never appears in
  a response body or log (the error path masks it).
- The browser talks only to our route `POST /api/voice/converse`, which brokers the
  call. With no key set (or a provider failure) the route returns a clean `503`
  and the UI degrades to "voice unavailable" — never a crash, never a leak.
- **Production path:** in production this broker calls the AI fabric *through the
  gateway* (the wall that holds the credential and runs generate-and-verify). The
  current route is the dev broker that calls the provider directly server-side so
  the surface is runnable now; the boundary (key server-only) is identical.

## Files

| File | Role |
|------|------|
| `surfaces/web/app/api/voice/converse/route.ts` | server broker — STT+reason → TTS, retry/fallback, key never leaves the server |
| `surfaces/web/app/api/voice/token/route.ts` | availability/health check (used by the production ephemeral-token path) |
| `surfaces/web/lib/voiceConverse.ts` | browser client — mic capture, WAV encode, post, play |
| `surfaces/web/app/_components/VoiceCapsule.tsx` | the push-to-talk UI (mic + waveform), graceful degradation |
| `spine/ai-fabric/app/voice.py` | the canonical AI-fabric voice capability (gateway-mediated, generate-and-verify) |

## Tests

- `surfaces/web/lib/__tests__/voiceConverse.test.ts` — the transport degrades calmly
  on 503 and network error (never throws), a successful turn returns reply + audio,
  and the WAV encoder writes a valid RIFF/WAVE container.
- `spine/ai-fabric` voice suite — the degraded path (no key → `provider_available=false`),
  the key never present in any result, the confidence gate, and the permission rung.

## Trying it

The key is in the local, gitignored `.env.local`. Start the app
(`npm run dev`), open the home, tap the mic beside the composer, speak, tap again
to send. Vidya replies aloud. Rotate the key for production and place it in
Infisical under `clss.aifabric.dev.gemini_api_key`.
