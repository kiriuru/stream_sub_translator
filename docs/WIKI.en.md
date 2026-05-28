# SST Desktop — WIKI

This WIKI is written as an operational guide for each UI element:
**what it is**, **why it exists**, **how it works**, **what it affects**, and **when to use it**.

---

## 0. Version and Updates

### Element: replacing `Stream Subtitle Translator.exe`
- **What it does:** updates the app binary to a newer release.
- **Why it matters:** brings bug fixes, stability improvements, and new UI/runtime behavior.
- **How it works:** at launch, the bootstrap/runtime layer validates local runtime components and restores missing pieces when needed.
- **What it affects:** feature availability, startup behavior, and compatibility of saved settings with new fields.
- **Example:** a new translation option appears only after binary update; old profile still loads, new option gets default value.

### Element: `Repair Runtime` / `Reset Runtime`
- **What it does:** fixes or recreates local runtime environment.
- **When to use:** update succeeded but app fails to start, crashes at boot, or runtime dependencies are broken.
- **Operational rule:** use repair first, reset only if repair does not resolve the issue.
- **Impact:** first start after reset can be longer because runtime files are rebuilt.

---

## 1. Quick Start

### Element: startup profile
- **What it does:** applies a pre-defined startup path (Web Speech, NVIDIA, CPU, etc.).
- **Why it exists:** avoids manual setup across multiple panels before first run.
- **Impact:** pre-selects runtime assumptions and may lock/unlock some recognition paths depending on profile.

### Element: `Recognition method`
- **What it does:** selects the ASR path (`local`, browser worker, experimental browser worker).
- **How to choose:**
  - laptop / no CUDA -> browser path;
  - desktop with CUDA -> local Parakeet path.

### Element: `Recognition language` + microphone input
- **What it does:** defines ASR language model context and audio source device.
- **Why critical:** wrong language or wrong mic typically hurts quality more than advanced tuning values.

---

## 2. What to Check If Something Is Not Working

### Scenario: no text appears at all
- Confirm runtime is actually started.
- Confirm correct microphone device is selected.
- Confirm microphone permissions (especially for browser worker window).
- Check diagnostics panel to verify audio frames are arriving.

### Scenario: source text appears, translation does not
- Confirm `Translate recognized speech` is enabled.
- Confirm at least one translation line is enabled.
- Check `Translated Results` for provider errors (key, endpoint, quota, timeout, network).

### Scenario: OBS shows no subtitles
- Confirm Browser Source points to `/overlay`.
- Confirm relevant visibility toggles are enabled.
- Verify subtitle TTL values are not too short (text may appear then vanish quickly).

---

## 3. Startup Profiles

### Element: `Quick Start (Web Speech)`
- **Goal:** fastest first run without local AI model path.
- **How it works:** opens dedicated browser worker window and uses browser speech recognition APIs.
- **Important:** local AI mode can remain temporarily profile-locked until next start with NVIDIA/CPU profile.

### Element: `NVIDIA GPU (CUDA)`
- **Goal:** best local recognition speed and stability when CUDA is available.
- **Impact:** lower latency to final text, higher GPU usage.

### Element: `CPU-only`
- **Goal:** fallback for systems without usable CUDA.
- **Impact:** slower ASR, higher latency, and potentially chattier partial updates.

### Element: `Remote Controller` / `Remote Worker`
- **Goal:** split controller/worker runtime over LAN.
- **Order requirement:** start worker first, then controller.
- **Constraint:** worker path is local AI runtime, not browser speech mode.

---

## 4. Recognition

### Element: `Recognition method`
- **Purpose:** selects architecture for audio-to-text.
- **Modes:**
  - local runtime ASR;
  - browser worker ASR;
  - experimental browser worker ASR.
- **Impact:** changes latency profile, dependency surface, and troubleshooting path.

### Element: `Recognition language`
- **Purpose:** defines language context for decoding.
- **Practical rule:** pick dominant spoken language, then handle multilingual audience via translation lines.

### Element: `Worker browser (desktop)`
- **Purpose:** chooses browser engine for worker window.
- **Use case:** if one browser path is unstable on a machine, switch browser and retest worker diagnostics.

### Element: `Backend ASR provider` (local path)
- **Purpose:** selects Parakeet local provider variant.
- **Impact:** low-latency profile responds faster, standard profile may behave calmer in some speech patterns.

---

## 5. Translation

### 5.1 Main toggles

#### Element: `Translate recognized speech`
- **What it does:** enables/disables translation pipeline.
- **Important:** disabling translation does not disable recognition; source-only flow remains valid.

#### Element: `Reuse translation cache (skip duplicate API calls)`
- **What it does:** deduplicates repeated translation requests.
- **Why useful:** reduces provider cost and repeated latency.
- **Example:** repeated catchphrase gets near-instant cached output instead of new API call.

#### Element: `Save translation cache to disk between sessions`
- **What it does:** persists cache across restarts.
- **Trade-off:** old cached phrasing may conflict with newly changed model prompt/style goals.

### 5.2 Translation Lines

#### Element: adding/removing lines
- **What it does:** manages target language slots (up to 5).
- **Impact:** each enabled line adds translation workload and output surface.

#### Element: line-level `Enabled`
- **What it does:** toggles a slot without deleting it.
- **Why useful:** quick A/B testing of language sets during stream.

#### Element: per-line provider
- **What it does:** lets each line use different provider/model strategy.
- **Example:** Translation 1 for speed with default provider; Translation 2 for style via LLM provider.

### 5.3 Provider Settings

#### Element: `Default provider for new lines`
- **What it does:** pre-fills provider when creating new lines.
- **Why useful:** keeps workflow consistent for repeated setup changes.

#### Element: auth/endpoint/model fields
- **What it does:** controls request routing and provider authentication.
- **Failure mode:** invalid values surface as explicit errors in `Translated Results`.

#### Element: `Custom prompt override` (LLM paths)
- **What it does:** overrides translation style instructions.
- **Impact:** directly changes tone, verbosity, and output format.
- **Example prompt intent:** "Subtitle style only, concise, no commentary."

### 5.4 `Translated Results`
- **What it shows:** successful translations and runtime provider errors.
- **Why operationally important:** first place to identify whether issue is in provider layer vs ASR layer.
- **Note:** delayed translation is not always a failure; stale/superseded protection can skip outdated outputs by design.

---

## 6. Subtitle Output

### 6.1 Element: `Overlay layout preset`
- **`Single line`:** most compact, least readable for multi-language output.
- **`Dual line`:** practical default for source + one translation.
- **`Stacked`:** best readability for multiple lines, uses more vertical space.

### 6.2 Element: `Use tighter overlay spacing`
- **What it does:** reduces spacing between rows.
- **When to use:** tight OBS composition or small subtitle area.

### 6.3 Visibility elements
- **`Show the original spoken text`:** toggles source text visibility.
- **`Show translated lines`:** toggles translation visibility.
- **`Maximum translated lines on screen`:** caps rendered translation rows.
- **Behavior detail:** enabled lines can exceed visible cap; rendering follows current line order.

### 6.4 Timing and replacement elements
- **Completed source TTL:** how long finalized source remains.
- **Completed translation TTL:** how long finalized translation remains.
- **Sync source with visible translation:** keeps source visible while translation is still active.
- **Immediate replacement on next final:** aggressively replaces current block after next finalized phrase.

**Lifecycle intent:** completed translation should stay visible while next phrase is still partial; replacement happens when the new phrase is finalized and enters translation flow.

### 6.5 Element: ordering (`Move Up` / `Move Down`)
- **What it does:** reorders source/translation display lines.
- **Shared effect surface:** dashboard preview, OBS overlay rendering, and OBS CC `First visible line` mode.

---

## 7. Subtitle Style

### Element: preset selection
- **What it does:** applies a style baseline quickly.
- **Why useful:** fast switching between stream scenes/backgrounds.

### Element: style controls (font, size, color, stroke, shadow, background)
- **How it works:** single styling system drives both preview and overlay output.
- **Best practice:** optimize readability first (contrast/outline), aesthetics second.

### Element: per-slot styling (`source`, `translation_1..translation_5`)
- **What it does:** gives separate visual identity to source and each translation line.
- **Example:** source in white, translation_1 in yellow, translation_2 in cyan.

### Element: saving preset + saving config/profile
- **Important:** unsaved config/profile can lose style changes on restart.

---

## 8. OBS Closed Captions

### 8.1 Element: `Send captions to OBS Closed Captions`
- **What it does:** enables caption stream publishing to OBS websocket path.
- **Why use it:** delivers native CC stream instead of only visual overlay text.

### 8.2 Connection fields (`host`, `port`, `password`)
- **What they do:** establish OBS websocket session.
- **Typical failure:** correct host/port but wrong password -> no caption delivery.

### 8.3 Element: `Output mode`
- **Options:** disabled, source live, source final, translation 1..5, first visible line.
- **Selection guidance:**
  - lowest delay -> source live;
  - cleaner captions -> source final;
  - multilingual audience -> translation slot or first visible line.

### 8.4 Timing, smoothing, and dedupe controls
- **Minimum gap:** reduces update spam.
- **Minimum text delta:** ignores tiny text changes.
- **Final replacement delay:** smooths rapid transitions.
- **Auto clear timeout:** controls stale tail text behavior in OBS.
- **Avoid duplicate text:** prevents redundant identical sends.

### 8.5 Element: debug mirror to OBS text source
- **Why it exists:** troubleshooting visibility when CC path behavior is unclear.
- **When useful:** verify data is being emitted even if final player path is inconsistent.

### 8.6 Twitch compatibility note
- Twitch uses CEA-708/EIA-608 compatible caption ingestion path.
- Plain text is usually most compatible.
- Some complex Unicode rendering can vary by player/platform.

---

## 9. Recognition Feel (Tuning)

### Element: `How quickly text appears`
- **Effect:** earlier display vs higher chance of partial revisions.

### Element: `How quickly speech is considered finished`
- **Effect:** faster finalization can over-segment; slower finalization can feel laggy.

### Element: update stability control
- **Effect:** controls how chatty partial updates are during speech.

### Element: `RNNoise noise reduction (experimental)` + strength
- **Use only when needed:** noisy rooms can improve; clean signal can degrade if over-applied.

### Element: `Parakeet latency preset`
- **Purpose:** safe preset-level tuning before advanced manual changes.

After tuning, save config/profile and restart runtime (`Stop` -> `Start`).

---

## 10. Advanced Recognition & Diagnostics

This section is for fine-grained adaptation to mic quality, room noise, and speaking rhythm.

### Group: sensitivity and thresholds
- Controls VAD/noise gating behavior.
- If thresholds are too high: quiet speech gets dropped.
- If thresholds are too low: noise triggers false speech activity.

### Group: partial/final emission behavior
- Controls update frequency, minimum change, and coalescing.
- Stream use case often prefers fewer, more stable partial updates over maximum update rate.

### Group: phrase segmentation
- Pause/finalization limits define final phrase boundaries.
- These boundaries influence translation timing and subtitle block readability.

### Group: chunk window / overlap
- Controls ASR context windowing and boundary continuity.
- Bad balance can add latency or reduce stability at phrase edges.

**Best practice:** change one setting at a time and validate in live preview before saving profile.

---

## 11. Word replacement (before translation)

### Element: `Enable word replacement`
- **What it does:** applies replacement rules before translation and subtitle output.
- **Why useful:** moderation, brand term normalization, repeated ASR correction.

### Element: built-in profanity list
- **What it does:** quickly enables RU+EN baseline filtering.
- **Impact:** translation receives already replaced text, not original raw token.

### Element: matching rules (`Case-insensitive`, `Whole words only`)
- Case-insensitive catches casing variants.
- Whole-word mode prevents accidental inside-word replacements.

### Element: dictionary controls (`Word or phrase`, `Replace with`, `Add`, `Remove selected`)
- **Example:** replace `discord` with `Discord` to keep consistent casing in source and translation outputs.

---

## 12. Tools & Data

### Element: `Deep Runtime Detail` -> `Runtime Diagnostics`
- **What it provides:** latency metrics, ASR diagnostics, translation diagnostics, queue/runtime state, worker state, OBS CC state, log path hints.
- **Why it matters:** lets you localize failures to the exact stage instead of guessing.

### Element: `Local Config`, `Profiles`, diagnostics export
- **Local Config:** current active runtime config state.
- **Profiles:** reusable saved presets for specific streaming setups.
- **Diagnostics export:** package for reproducible troubleshooting.

---

## 13. Local Parakeet

### Element: `Local Parakeet` / `Official EU Parakeet Low Latency`
- **What it is:** local AI recognition path.
- **When to use:** when you need predictable local ASR behavior and especially when CUDA is available.

Model reference:
- [NVIDIA Parakeet model card](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2)

---

## 14. Web Speech

### Element: worker page (`/google-asr` and edge variant)
- **What it does:** runs speech recognition in dedicated browser worker window and forwards results to runtime.
- **UI blocks:** start/stop, partial/final behavior controls, websocket counters, live/final text diagnostics.
- **Operational value:** if dashboard shows no text, worker page helps isolate browser-side recognition vs backend ingest issues.

---

## 15. Web Speech (Experimental)

### Element: experimental worker page (`/google-asr-experimental` and edge variant)
- **What it does:** uses experimental startup path for browser recognition.
- **Why available:** fallback path for systems where classic worker behavior is unstable.
- **Behavior note:** can revert to normal start behavior when experimental path is not supported.

---

## 16. Help

### Element: built-in help topics
- **What it does:** provides in-app guidance for startup, recognition, translation, subtitle output/style, OBS, and diagnostics.
- **Why useful:** reduces time-to-fix for common setup and runtime problems.

---

## 17. Glossary

- **`partial`:** in-progress text that may still change.
- **`final`:** finalized phrase text.
- **`translation slot`:** one target translation line (`translation_1..translation_5`).
- **`overlay`:** `/overlay` page used in OBS Browser Source.
- **`OBS Closed Captions`:** caption stream pushed to OBS websocket.

