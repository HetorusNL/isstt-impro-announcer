# Japanese Announcements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every announcement can carry a Japanese phrase, spoken first by Kokoro's `jf_alpha`, then the English by `af_bella` or `jf_alpha`. Kokoro replaces Piper.

**Architecture:**
- A pure function turns an announcement's English and Japanese text into its spoken parts: Japanese first, then English, honouring the per-language switches.
- A Kokoro-backed `Tts.synth(text, lang)` caches one WAV per part.
- The engine builds the session's audio list: part, pause (as seconds), part. `run_session` plays WAVs and sleeps the pauses inside the one Spreken hold.
- The GUI edits the new `[tts]` settings and the `*_ja` messages.

**Tech Stack:** Python 3.13, uv, `kokoro-onnx` (≥0.6.1), `misaki[ja]` (≥0.9.4) with `unidic-lite` (≥1.0.8), NiceGUI, pytest + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-11-21-japanese-announcements-design.md`

## Global Constraints

- Hard deadline **2026-12-18**.
- **Spreken must be released under all circumstances.** All parts of a session play inside the existing single hold in `sequencer.run_session` (between chime and tail). Never a second hold per part.
- Default English messages verbatim: `Referees, you may start the matches.` / `Referees, you may end the matches.`
- Offline at runtime: no network access, no dictionary downloads. Use `misaki.ja.JAG2P()` with its default (`cutlet` + `fugashi` + `unidic-lite`), never `version="pyopenjtalk"`: that path downloads the Open JTalk dictionary on first use.
- `uv sync` must not install `unidic` (its dictionary is a separate download). Use `[tool.uv] override-dependencies = ["unidic; sys_platform == 'never'"]` (verified 2026-11-21).
- Model files `voices/kokoro-v1.0.onnx` and `voices/voices-v1.0.bin` from `https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/`, untracked.
- English voices: exactly `af_bella` and `jf_alpha`. Japanese voice `jf_alpha`. Kokoro `speed` must be within 0.5..2.0.
- Old configs with Piper `[tts]` keys are not supported and get no migration.
- Commits are GPG-signed. Before every commit run `gpg-connect-agent "keyinfo --list" /bye | grep -c "8F2048.* 1 P"`. If it prints 0, stop and ask Tim to run `! ~/scripts/gpg/unlock.sh`. Never `--no-gpg-sign`.
- Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- `master` is public: ask Tim before pushing.

## Review Focus

1. **Both languages off, or both texts empty, at a scheduled start.** No button is pressed, the announcement is recorded `skipped` with a detail saying why, and the engine keeps running. Test: `test_nothing_to_say_presses_nothing` (Task 3).
2. **Whitespace-only Japanese, including the full-width space 「　」.** Treated as empty, so there is no Japanese part and no pause. Test: `test_parts_whitespace_is_empty` (Task 1).
3. **Switching the English voice or a speed and saving.** The next playback uses the new voice, not a cached WAV of the old one. Test: `test_cache_key_changes_with_voice_and_speed` (Task 2).
4. **A brace in a Japanese message (`{` or `}`).** Rejected at load/save with a message naming the key, not a crash at announce time. Test: `test_ja_message_with_placeholder_rejected` (Task 1).
5. **Latin letters inside the Japanese text ("ISSTT 2026").** Synthesis does not raise; whatever Kokoro makes of it is played. Test: `test_japanese_with_latin_letters` (Task 2), plus the manual check in Task 5.

---

### Task 1: Config and spoken parts

**Files:**
- Modify: `src/announcer/config.py` (`Tts` dataclass, `validate`, new `ja_key`)
- Create: `src/announcer/speech.py`
- Modify: `config.example.toml`
- Test: `tests/test_config.py`, `tests/test_speech.py` (new)

**Interfaces:**
- Produces, in `announcer.config`:
  ```python
  ENGLISH_VOICES = ("af_bella", "jf_alpha")
  @dataclass
  class Tts:
      model: str = "voices/kokoro-v1.0.onnx"
      voices: str = "voices/voices-v1.0.bin"
      cache_dir: str = "cache/tts"
      english: bool = True
      english_voice: str = "af_bella"
      english_speed: float = 1.0
      japanese: bool = True
      japanese_voice: str = "jf_alpha"
      japanese_speed: float = 1.0
      pause_seconds: float = 0.5
  def ja_key(kind: str) -> str  # "match_start" -> "match_start_ja"
  ```
- Produces, in `announcer.speech`:
  ```python
  Lang = Literal["en", "ja"]
  Part = tuple[Lang, str]
  def spoken_parts(tts: TtsConfig, en: str, ja: str) -> list[Part]
  ```
  Returns `[("ja", ja.strip()), ("en", en.strip())]`, dropping a part whose switch is off or whose stripped text is empty.

- [ ] **Step 1: Write the failing tests**

In `tests/test_speech.py`:
- `test_parts_order_japanese_first`: `spoken_parts(Tts(), "Hello.", "こんにちは。") == [("ja", "こんにちは。"), ("en", "Hello.")]`
- `test_parts_english_off`: with `english=False` → `[("ja", "こんにちは。")]`
- `test_parts_japanese_off`: with `japanese=False` → `[("en", "Hello.")]`
- `test_parts_both_off`: both switches off → `[]`
- `test_parts_whitespace_is_empty`: `spoken_parts(Tts(), "Hello.", "　 \n") == [("en", "Hello.")]`

In `tests/test_config.py`:
- `test_ja_message_with_placeholder_rejected`: `messages["match_start_ja"] = "試合{time}"` → `ConfigError` whose message contains `match_start_ja`
- `test_ja_message_with_lone_brace_rejected`: `"試合{"` → `ConfigError`
- `test_ja_messages_optional`: a config without `*_ja` keys validates
- `test_unknown_english_voice_rejected`: `english_voice = "am_michael"` → `ConfigError`
- `test_speed_out_of_range_rejected`: parametrize `english_speed` / `japanese_speed` in `(0.4, 2.1)` → `ConfigError`
- `test_negative_pause_rejected`: `pause_seconds = -0.1` → `ConfigError`
- `test_example_config_loads` (existing) also asserts `cfg.messages["match_start_ja"] == "審判の皆さん、試合を開始してください。"`
- `test_old_piper_tts_keys_rejected`: a `[tts]` with `voice_model` → `ConfigError` (the existing unknown-key check; this pins it)

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_speech.py tests/test_config.py -q`
Expected: failures for the new tests (missing module/fields).

- [ ] **Step 3: Implement**

`config.py`:
- Replace `Tts` as above.
- In `validate`:
  - Messages whose key ends in `_ja` must have no replacement fields. Any `field_name is not None` from `string.Formatter().parse`, or a `ValueError` from parsing, raises `ConfigError` naming the key ("Japanese messages are fixed phrases").
  - All other messages keep `_check_template`.
  - `english_voice` must be in `ENGLISH_VOICES`.
  - Both speeds must be in 0.5..2.0.
  - `pause_seconds` must be in 0..5.

`speech.py`: `spoken_parts` as specified.

`config.example.toml`:
- Replace `[tts]` with the new keys and their defaults, each commented.
- Add these to `[messages]` with a comment "fixed Japanese phrases, no placeholders; empty = no Japanese":
  - `match_start_ja = "審判の皆さん、試合を開始してください。"`
  - `match_end_ja = "審判の皆さん、試合を終了してください。"`

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `uv run pytest tests/test_speech.py tests/test_config.py -q`
Expected: all pass. Other suites may fail on the removed `voice_model` until Task 2 and Task 3; that is expected here.

- [ ] **Step 5: Commit**

```bash
git add src/announcer/config.py src/announcer/speech.py config.example.toml tests/test_config.py tests/test_speech.py
git commit -m "feat: config for Kokoro voices and Japanese messages"
```

---

### Task 2: Kokoro TTS replaces Piper

**Files:**
- Modify: `src/announcer/audio/tts.py` (rewrite)
- Modify: `src/announcer/main.py:15-18,73-74,142` (factory)
- Modify: `pyproject.toml`, `uv.lock`
- Modify: `README.md` (first-run steps, the "Piper TTS" wording)
- Test: `tests/test_tts.py` (rewrite), `tests/test_main.py` if it references `piper_tts`

**Interfaces:**
- Consumes: `announcer.config.Tts`, `announcer.speech.Lang` (Task 1).
- Produces, in `announcer.audio.tts`:
  ```python
  class Tts:
      def __init__(self, cfg: TtsConfig) -> None
      def cache_path(self, text: str, lang: Lang) -> Path
      async def synth(self, text: str, lang: Lang) -> Path
      # test seams, like today's _load_voice:
      def _load_kokoro(self) -> Any      # returns kokoro_onnx.Kokoro(cfg.model, cfg.voices)
      def _load_g2p(self) -> Any         # returns misaki.ja.JAG2P()
  ```
- Produces, in `announcer.main`: `def kokoro_tts(tts_cfg: TtsConfig) -> Synth`, replacing `piper_tts`, passed as `tts_factory`.

- [ ] **Step 1: Write the failing tests** (`tests/test_tts.py`, with a `FakeKokoro` recording `create(text, voice, speed, lang, is_phonemes)` calls and returning `(np.zeros(2400, float32), 24000)`, and a `FakeG2P` returning `("PHONEMES:" + text, None)`; inject both through the seams)

- `test_english_uses_english_voice`: `synth("Hello.", "en")` → one `create` call with `voice="af_bella"`, `lang="en-us"`, `is_phonemes=False`, `speed=1.0`
- `test_english_voice_jf_alpha`: with `english_voice="jf_alpha"` → `voice="jf_alpha"`, `lang="en-us"`
- `test_japanese_goes_through_g2p`: `synth("試合", "ja")` → `create("PHONEMES:試合", voice="jf_alpha", lang="ja", is_phonemes=True, speed=cfg.japanese_speed)`
- `test_cache_hit_does_not_resynthesise`: same text and lang twice → one `create` call, same path
- `test_cache_key_changes_with_voice_and_speed`: the paths differ for each of these changes:
  - `english_voice`
  - `english_speed`
  - lang (same text as `"en"` vs `"ja"`)
  - text
- `test_models_load_lazily_and_once`: no load at construction; after an `en` and a `ja` synth, `_load_kokoro` was called once and `_load_g2p` once
- `test_japanese_with_latin_letters`: `synth("ようこそ、ISSTT 二千二十六へ。", "ja")` returns an existing WAV
- `test_wav_is_24k_mono`: the written file reads back with `soundfile` as 24000 Hz, 1 channel

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_tts.py -q`
Expected: FAIL (constructor signature).

- [ ] **Step 3: Implement**

`tts.py`:
- The cache key is `f"kokoro|{model}|{voice}|{lang}|{speed}|{text}"`, sha256-hashed as today.
- The voice and speed come from `english_*` for `"en"` and `japanese_*` for `"ja"`.
- Synthesis runs in `asyncio.to_thread` under the existing lock. The write is atomic via a `.tmp` file, as today.
- Write with `soundfile` (PCM_16).
- Keep the `__main__` helper, taking `[lang] text`.

`main.py`: `kokoro_tts` replaces `piper_tts`. Remove the Piper imports.

`pyproject.toml`:
- Remove `piper-tts`.
- Add `kokoro-onnx>=0.6.1`, `misaki[ja]>=0.9.4`, `unidic-lite>=1.0.8`.
- Add:
  ```toml
  [tool.uv]
  override-dependencies = ["unidic; sys_platform == 'never'"]
  ```
- Run `uv lock`, then `uv sync`. Check that `uv pip list` shows `unidic-lite` and no `unidic`.

`README.md`:
- The intro says Kokoro TTS instead of Piper.
- The first-run block downloads the two model files into `voices/`:
  ```sh
  mkdir -p voices
  curl -L -o voices/kokoro-v1.0.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
  curl -L -o voices/voices-v1.0.bin https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
  ```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `uv run pytest tests/test_tts.py tests/test_main.py -q`
Expected: all pass.

- [ ] **Step 5: Check it for real, offline**

Download the two model files as in the README, then run:

```bash
unshare -rn uv run --offline python -m announcer.audio.tts ja "審判の皆さん、試合を開始してください。"
unshare -rn uv run --offline python -m announcer.audio.tts en "Referees, you may start the matches."
```

Expected: each prints a WAV path and a duration of 1.5 to 4 s, with no network error. If `unshare -rn` is not permitted, say so in the report and run without it.

- [ ] **Step 6: Commit**

```bash
git add src/announcer/audio/tts.py src/announcer/main.py pyproject.toml uv.lock README.md tests/test_tts.py tests/test_main.py
git commit -m "feat: Kokoro speaks English and Japanese, Piper removed"
```

---

### Task 3: Engine and sequencer play Japanese, pause, English

**Files:**
- Modify: `src/announcer/model.py` (`Announcement.text_ja`)
- Modify: `src/announcer/sequencer.py` (`run_session` audio items)
- Modify: `src/announcer/engine.py` (`Synth`, `_desk`, `_text`, `_prewarm`, `_presynth_next`, `_spawn_synth`, `_synth_all`, `_audio`, `manual_text`, `_run_desk`)
- Test: `tests/test_engine.py`, `tests/test_sequencer.py`, `tests/test_rehearsal.py` (fakes take `lang`)

**Interfaces:**
- Consumes: `spoken_parts`, `Part`, `Lang` (Task 1), `Tts.synth(text, lang)` (Task 2), `ja_key` (Task 1).
- Produces:
  - `Announcement.text_ja: str | None = None` (manual texts only).
  - `class Synth(Protocol): async def synth(self, text: str, lang: Lang) -> Path`
  - `run_session(..., audio: Sequence[Path | float])`: a `float` is a pause of that many seconds via `clock.sleep`, inside the hold.
  - `Engine.manual_text(halls, text, text_ja="")`
  - `Engine.parts(ann: Announcement) -> list[Part]`, public so the GUI can show and preview them. Scheduled kinds use `render_message(cfg.messages[kind], ann)` for English and `cfg.messages.get(ja_key(kind), "")` for Japanese. `manual_text` uses `ann.text` and `ann.text_ja`.
  - `NOTHING_TO_SAY = "nothing to say: English and Japanese are off or empty"` (history detail).

- [ ] **Step 1: Write the failing tests**

`tests/test_sequencer.py`:
- `test_pause_item_sleeps_inside_hold`: audio `[wav1, 0.5, wav2]` → the controller log shows exactly one SPREKEN hold and one release, both WAVs played between them in order, and clock time between the two plays ≥ 0.5 s.

`tests/test_engine.py` (`FakeTts.synth(text, lang)` records `(lang, text)`; `by_path` maps to `(lang, text)`):
- `test_start_plays_japanese_then_english`: with `cfg.messages["match_start_ja"] = "試合を開始してください。"`, the played sequence for a start is `[("ja", "試合を開始してください。"), ("en", START_MSG)]`, in one SPREKEN hold.
- `test_no_japanese_message_plays_english_only`: without `match_start_ja` → `[("en", START_MSG)]`, and no pause.
- `test_japanese_off_plays_english_only`: `cfg.tts.japanese = False` with a `_ja` message set → English only.
- `test_nothing_to_say_presses_nothing`: both switches off → no controller actions for that session. The history entry is `skipped` with detail `NOTHING_TO_SAY`. The next start in the schedule still plays (the engine keeps running).
- `test_manual_text_mixed`: `manual_text(["SC1"], "Hello.", "こんにちは。")` plays `[("ja", "こんにちは。"), ("en", "Hello.")]`.
- `test_prewarm_synthesises_japanese_messages`: after `start()`, `("ja", "試合を開始してください。")` was synthesised before the first start is due. A placeholder-free English message is synthesised too.
- `test_prewarm_respects_switches`: with `japanese=False`, no `"ja"` synth happens at startup.
- `test_reload_with_new_voice_resynthesises`: after `reload_config` with a different `english_voice`, the next start synthesises again (`_audio` cleared, new factory called).

`tests/test_rehearsal.py`:
- `SilentTts.synth(text, lang)`.
- The existing rehearsal assertions keep passing with the example config, which now has Japanese messages, so update the expected played texts to include the Japanese part.
- Add an assertion that each session has exactly one SPREKEN hold.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_sequencer.py tests/test_engine.py tests/test_rehearsal.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

- `_audio`, `_synth_pending` and `_synth_failed` are keyed by `Part` instead of `str`.
- `_desk` builds the audio list per announcement from `self.parts(ann)`, using the cached path or `await self._tts.synth(text, lang)`. When an announcement has both parts, `cfg.tts.pause_seconds` goes between them. If the whole session has no parts, it raises `NothingToSay` (a module-level exception) before `run_session`, so no button moves.
- `_run_desk` records a `NothingToSay` failure as `skipped` with detail `NOTHING_TO_SAY`, not `failed`.
- `_prewarm` synthesises `("en", t)` for placeholder-free messages whose key does not end in `_ja`, and `("ja", t)` for non-empty `*_ja` messages. It honours the switches through `spoken_parts`.
- `_presynth_next` uses `self.parts(ann)`.

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `uv run pytest -q`
Expected: the whole suite passes.

- [ ] **Step 5: Commit**

```bash
git add src/announcer/model.py src/announcer/sequencer.py src/announcer/engine.py tests/test_engine.py tests/test_sequencer.py tests/test_rehearsal.py
git commit -m "feat: announcements speak Japanese, a pause, then English"
```

---

### Task 4: Window

**Files:**
- Modify: `src/announcer/gui/app.py` (manual page, settings page, calibration "Full sequence" card, upcoming/history/queued rendering)
- Modify: `src/announcer/gui/view.py` (`TEST_PHRASE_JA`, `queued_label`, preview helper)
- Test: `tests/test_engine.py` (where the `view` tests live) or a new `tests/test_view.py`

**Interfaces:**
- Consumes: `Engine.parts`, `Engine.manual_text(halls, text, text_ja)`, `spoken_parts`, `ja_key`, the `Tts` config fields, `Tts.synth(text, lang)`.
- Produces, in `view`:
  - `TEST_PHRASE_JA = "これはテストのアナウンスです。"`
  - `queued_label(session)` showing `「ja」 en` when both are present
  - `async def play_preview(tts: Synth, player: Player, parts: Sequence[Part], pause: float) -> None`, which plays the parts on the given player with `asyncio.sleep(pause)` between Japanese and English

- [ ] **Step 1: Write the failing tests**

- `test_queued_label_shows_both`: a manual session with text `"Hello."` and text_ja `"こんにちは。"` → the label contains `こんにちは。` and `Hello.`.
- `test_queued_label_japanese_only`: text `""` and text_ja `"こんにちは。"` → the label contains `こんにちは。`.
- `test_play_preview_order_and_pause`: with a fake TTS and a `MockPlayer`, parts `[("ja", "a"), ("en", "b")]` play in order. Pause 0 still works.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -k "queued_label or play_preview" -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

- **Manual page:**
  - A "Japanese text" textarea above the existing one, which is renamed "English text".
  - Speak requires halls and at least one non-empty text. It calls `manual_text(halls, en, ja)`.
- **Settings page:**
  - For each English message key (keys not ending in `_ja`), an input for `ja_key(key)` directly under it.
  - Preview plays `spoken_parts(edited tts settings, rendered en, ja)` through `play_preview` on the laptop speakers, with the existing `preview_refusal` checks.
  - A "Speech" card with these controls, all written in `edit(c)`:
    - switches "Speak English" and "Speak Japanese"
    - a select "English voice" with `ENGLISH_VOICES`
    - number fields "English speed" and "Japanese speed" (min 0.5, max 2.0, step 0.05)
    - "Pause between Japanese and English (s)" (min 0, max 5, step 0.1)
  - An empty Japanese input saves as `""`.
- **Calibration "Full sequence" card:** a "Test Japanese" button next to "Test full sequence" that queues `manual_text(halls, view.TEST_PHRASE, view.TEST_PHRASE_JA)`.
- **Upcoming and history:** where an announcement's text is shown, show the Japanese part too, via `engine.parts(ann)`.

- [ ] **Step 4: Run the tests, then the app**

Run: `uv run pytest -q`, expected all pass. Then run `uv run announcer --mock` and check by hand:
- The manual page has both boxes and queues a mixed text.
- On the settings page:
  - each switch, the voice select, the speeds and the pause save to `config.toml`;
  - Preview plays Japanese, then English.
- The Test Japanese button queues.

- [ ] **Step 5: Commit**

```bash
git add src/announcer/gui/app.py src/announcer/gui/view.py tests/
git commit -m "feat: Japanese text, voices, speeds and pause in the window"
```

---

### Task 5: Docs and the real-voice check

**Files:**
- Modify: `README.md` (config section: the `[tts]` keys and `*_ja` messages, one short paragraph)
- Modify: `docs/onsite-checklist.md` (any Piper or voice download line now refers to the Kokoro files, plus a line: "listen to the Japanese and English start message through the desk; tune the speeds and pause on the settings page")

- [ ] **Step 1: Update the two docs as listed.**

- [ ] **Step 2: Real-voice check with Tim**

Run `uv run announcer --mock` with the real model and audio speed 1. Then:
- On the settings page, preview the start and end messages with `af_bella` and with `jf_alpha` as the English voice.
- Queue a manual text with 「ようこそ、ISSTT 二千二十六へ。」 and "Welcome."

Expected: Japanese, a pause, then English, at a natural speed. Tim confirms the Japanese phrases and the voice. Record any speed/pause changes in `config.example.toml`.

- [ ] **Step 3: Run the whole suite**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/onsite-checklist.md config.example.toml
git commit -m "docs: Kokoro setup and Japanese announcements"
```
