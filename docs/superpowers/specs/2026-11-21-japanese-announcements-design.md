# Japanese announcements — Design

Date: 2026-11-21
Builds on: `2026-11-01-impro-announcer-design.md` (the announcer itself).
Hard deadline: unchanged, **2026-12-18**.

## 1. Intent

This year's ISSTT tournament has a Japanese theme. Every announcement can
carry a Japanese line next to the English one: the Japanese is spoken first,
then the English. It is atmosphere for a mostly non-Japanese audience, so it
must sound like real spoken Japanese, by a voice that can speak it (not a
voice spelling out "Japanese character, Japanese character"). It does not
have to satisfy a native speaker.

Tim compared Open JTalk, Kokoro, piper-plus and VOICEVOX by ear and picked
**Kokoro** with voice `jf_alpha` for Japanese. He then compared Kokoro's
English voices with the current Piper voice and wants Kokoro for English
too, so **Piper is removed**: one engine for both languages.

Success = on 18-20 December the start and end announcements go out as
「Japanese phrase」 + "English phrase" exactly as today's English-only
announcements do (on time, right halls, Spreken always released), and the
operator can type mixed announcements in the window.

## 2. Goals

1. One TTS engine, Kokoro (`kokoro-onnx`), for both languages, running
   locally on the laptop, offline.
2. Japanese is always spoken by `jf_alpha`.
3. English is spoken by `af_bella` or `jf_alpha` (a Japanese-accented
   English), selectable in the window.
4. Each announcement has an optional Japanese text and an optional English
   text. Playback order: Japanese, a pause, English, all within the one
   Spreken press of the session.
5. English and Japanese can each be switched on and off in the window.
6. The pause between the two parts and the speed of each language are set
   in the window.
7. Start/end messages get fixed Japanese phrases; the manual text page gets
   a Japanese text box, typed with Tim's Japanese keyboard input.
8. The usual messages are synthesised in advance (at startup and before
   each session) and cached on disk, like today.

## 3. Non-goals

- Placeholders (`{time}`, `{count}`, `{fields}`, `{halls}`) in Japanese
  messages. Japanese messages are fixed phrases.
- Translating English to Japanese, or detecting the language of a text.
  Each text box says which language it is.
- Mixing scripts inside one text and switching voice mid-sentence. A Latin
  word inside the Japanese text (like "ISSTT") is read however Kokoro's
  Japanese reading handles it; that is acceptable.
- Keeping Piper as a fallback.
- Other languages.

## 4. Anti-goals (failure even if it "works")

- **Spreken stuck pressed.** The Japanese part makes a session longer. It
  must stay inside the existing single press, with the existing release
  guarantees and the firmware max-hold. A session must never press Spreken
  twice for its two parts.
- An announcement that silently loses its English part, or plays English
  when English is switched off.
- A start/end announcement that goes out late because Japanese synthesis
  runs at the due time when it could have been done in advance.
- Breaking the offline guarantee: no network access at runtime, including
  dictionary downloads on first use.
- Changing the default English messages: they stay verbatim
  `Referees, you may start the matches.` / `Referees, you may end the matches.`

## 5. How it works (decided parts)

### 5.1 Engine

- `kokoro-onnx` with the v1.0 model files `kokoro-v1.0.onnx` (about 325 MB)
  and `voices-v1.0.bin` (about 28 MB), stored in `voices/` (untracked, like
  the Piper voice today).
- English text goes to Kokoro as text with `lang="en-us"`; kokoro-onnx turns
  it into phonemes with its bundled espeak-ng. This holds for both English
  voices, `af_bella` and `jf_alpha`.
- Japanese text is turned into phonemes with `misaki`'s `ja.JAG2P`, then
  passed to Kokoro with `is_phonemes=True`, `lang="ja"`, voice `jf_alpha`.
- **Dictionary pitfall (found in the test, 2026-11-21):** `misaki[ja]`
  pulls in the `unidic` package, whose dictionary is a separate ~500 MB
  download (`python -m unidic download`), and without it the Japanese
  tagger fails. The test made it work by uninstalling `unidic` and
  installing `unidic-lite`, which ships its dictionary in the wheel. The
  project must end up with the `unidic-lite` setup from a plain `uv sync`,
  with no runtime download. Verified on Python 3.13 (the project's version):
  `kokoro-onnx 0.6.1`, `misaki 0.9.4`, `fugashi 1.5.2`, `unidic-lite 1.0.8`,
  `pyopenjtalk 0.4.1` install from wheels and phonemise the start phrase
  correctly.
- Speed per language: Kokoro's `speed` parameter, one value for English and
  one for Japanese, set in the window and saved in the config (default 1.0).
- Measured on this laptop (Core Ultra 7 155H): model load about 4.5 s, then
  about 1 s per sentence. Load the model once and reuse it for both
  languages.
- Remove `piper-tts` from the dependencies and the Piper code. The README
  setup steps change from downloading the Piper voice to downloading the two
  Kokoro files.

### 5.2 Cache

Same on-disk WAV cache as today, in `cache/tts`. The cache key includes the
engine, the voice, the language, the speed and the text, so switching the
English voice or a speed never plays a stale file.

### 5.3 Configuration (`config.toml`)

Replace `[tts]`:

```toml
[tts]
model = "voices/kokoro-v1.0.onnx"
voices = "voices/voices-v1.0.bin"
cache_dir = "cache/tts"
english = true              # speak the English part
english_voice = "af_bella"  # "af_bella" or "jf_alpha"
english_speed = 1.0
japanese = true             # speak the Japanese part
japanese_voice = "jf_alpha"
japanese_speed = 1.0
pause_seconds = 0.5         # between the Japanese and the English part
```

`[messages]` gains two optional entries:

```toml
match_start_ja = ""   # fixed Japanese phrase, no placeholders
match_end_ja = ""
```

- Empty or missing means no Japanese part for that message.
- Validation rejects placeholders in `*_ja` messages and an
  `english_voice` other than the two allowed voices.
- The required English messages stay required, even when English is
  switched off.
- Old configs with the Piper `[tts]` keys are not supported and need no
  migration: `config.toml` is rewritten from `config.example.toml`.

The suggested Japanese phrases (Tim to confirm or change) go in
`config.example.toml`:

- `match_start_ja = "審判の皆さん、試合を開始してください。"`
- `match_end_ja = "審判の皆さん、試合を終了してください。"`

### 5.4 What an announcement plays

For each announcement in a session, the parts are, in order:

1. the Japanese text, if Japanese is on and the text is not empty;
2. a pause of `pause_seconds`, only if both parts play;
3. the English text, if English is on and the text is not empty.

Then the next announcement in the same session (merged sessions, see the
main design §5.6), with the same rule. All parts of all announcements play
inside the one Spreken press, between the chime and the tail, exactly where
today's audio plays (`sequencer.run_session`, step 4). The pause is silence
inside the press, not a release.

If both languages are off, or both texts are empty, the announcement has
nothing to say. That must not press any button. For a scheduled start/end
it is recorded with a clear status/detail so the operator sees why nothing
played. A manual text with nothing to say is refused in the window, like an
empty text today.

### 5.5 Window (NiceGUI)

- **Manual page:** two text boxes, "Japanese text" above "English text".
  Either or both may be filled. The Speak button queues one announcement
  with both parts.
- **Settings page:**
  - each message gets its Japanese phrase next to it, with a Preview
    button that plays Japanese, pause, English on the laptop speakers,
    like today's preview;
  - switches "Speak English" and "Speak Japanese";
  - a choice "English voice: af_bella / jf_alpha";
  - "English speed" and "Japanese speed" number fields;
  - "pause between Japanese and English (s)" number field.
  All saved to `config.toml` with the existing Save, which reloads the
  engine config.
- **Calibration page:** next to "Test full sequence", a Japanese test (a
  fixed Japanese test phrase plus the English one), so the voice can be
  checked through the desk on the replica.
- **Upcoming list and history** show the Japanese text as well where there
  is one.

### 5.6 Synthesis in advance

As today: placeholder-free messages are synthesised at startup, and the
next session's texts before it is due. Both languages count, so the
Japanese start/end phrases are ready at startup. Reloading the config
(voice, speed, switches) re-runs it for the new settings.

## 6. Testing

- Unit tests without the model, like the current `test_tts.py` with a fake
  voice: cache key per language/voice/speed/text; order Japanese, pause,
  English; each switch off; empty texts; nothing-to-say case presses
  nothing; config validation (placeholders in `*_ja`, unknown English
  voice).
- The rehearsal test (`tests/test_rehearsal.py`) still passes with mixed
  announcements and shows one Spreken press per session.
- A manual check on the laptop with the real model: the start and end
  messages in both languages, a typed mixed text, each English voice, both
  switches, and a run on the replica.

## 7. Left to the builder

- How the parts are passed from the engine to the sequencer (a list of
  WAVs plus pause, or one stitched WAV per announcement).
- Module layout of the Kokoro code and the GUI widgets.
- The Japanese test phrase for the calibration page.
- How to make `uv sync` end up with `unidic-lite` instead of `unidic`
  (for example a uv dependency override), as long as no runtime download is
  needed.
- Sample-rate handling (Kokoro outputs 24 kHz).

## 8. Open items for Tim

- Confirm the two Japanese phrases.
- Listen to the final voices through the desk on site; tune
  `english_speed`, `japanese_speed` and `pause_seconds` if needed.
