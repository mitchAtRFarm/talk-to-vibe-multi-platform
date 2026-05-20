# PRD: Fast and Polished Profiles

## Summary

Add a profile system that lets users switch between two transcription modes from the tray or menu bar app:

- `Fast`
- `Polished`

Each profile has its own provider and model selection. The install/configure wizard must guide the user through setting up `Fast` first and `Polished` second, with recommended defaults but no hard restrictions. The active profile must be switchable at runtime from a submenu in the macOS menu bar app and Linux tray app.

This work also introduces `xAI` as a new first-class provider. `xAI` is the recommended default for `Fast`. The existing OpenRouter Gemini path is the recommended default for `Polished`.

## Goals

- Let users think in terms of outcomes instead of providers.
- Support low-latency transcription on systems that cannot run local Whisper well.
- Preserve a promptable, cleanup-oriented mode for polished dictation.
- Make mode switching available from the tray/menu UI without requiring re-running setup.
- Keep setup cross-platform by using the same Python wizard from both macOS and Linux installers.

## Non-Goals

- Do not limit which provider can be used for `Fast` or `Polished`.
- Do not add a third mode in this phase.
- Do not add automatic provider benchmarking or latency-based dynamic routing in this phase.
- Do not redesign terminal mode UX beyond making it honor the active profile.

## User Problem

Users currently configure a single provider for the whole app. That forces a tradeoff:

- fast, lower-resource transcription
- more polished, prompt-driven output

The product needs to support both workflows cleanly.

Examples:

- On a low-resource machine, a user may want `Fast` to use xAI STT or Groq.
- On the same machine, the same user may want `Polished` to use Gemini via OpenRouter for cleaner dictation.
- On a capable machine, `Fast` may use local Whisper while `Polished` uses Gemini.

## User Experience

### Install / Setup Wizard

The wizard should change from "pick one provider" to "set up your two modes".

Recommended flow:

1. Explain the two modes.
2. Configure `Fast`.
3. Configure `Polished`.
4. Ask which mode should be active by default.
5. Continue with global app settings like push-to-talk, microphone preference, and auto-enter.

Mode descriptions:

- `Fast`: prioritize low latency and lightweight transcription.
- `Polished`: prioritize cleanup, formatting, and higher-quality dictation output.

### Tray / Menu Bar Runtime UX

Add a submenu titled `Mode` with mutually exclusive options:

- `Fast`
- `Polished`

Selecting a mode should:

1. Update the active profile in config.
2. Rebuild the effective provider from the selected profile.
3. Refresh the tray/menu UI.
4. Apply to the next transcription immediately.

If transcription is currently in progress, the switch should be deferred until processing completes.

### Provider Info Display

Update provider info to include:

- `Mode`
- `Provider`
- `Model`
- existing global fields like push-to-talk and auto-enter

## Defaults

Recommended defaults during setup:

- `Fast`
  - provider: `xai`
- `Polished`
  - provider: `openrouter`
  - model: `google/gemini-3.1-flash-lite-preview`

Users can override these defaults and choose any provider for either mode.

## Functional Requirements

### Profiles

Add two built-in profiles:

- `fast`
- `polished`

Add an `active_profile` setting.

Each profile must support at least:

- `provider`
- `model`

Later phases may add profile-specific prompt or cleanup settings, but they are not required for this phase.

### Provider Configuration Split

Separate profile-level and provider-level responsibilities.

Profile-level:

- which provider this profile uses
- which model this profile uses

Provider-level:

- API keys
- base URLs
- transport-specific shared settings

This keeps secrets centralized while allowing each profile to pick a different provider/model pair.

### xAI Provider

Add xAI as a new provider option.

Requirements:

- first-class provider key, recommended name: `xai`
- direct xAI STT integration, not routed through OpenRouter
- handle xAI-specific API contract separately from OpenAI/OpenRouter providers

The xAI provider is distinct because it uses its own STT API shape and request parameters.

### Wizard Behavior

For each profile, the wizard must:

1. Ask the user to choose a provider.
2. Recommend a provider first, but allow any supported provider.
3. Ask for the model if the selected provider uses models.
4. Ask for credentials if required and missing.
5. Ask for provider-specific settings only when relevant.

Guardrail behavior:

- no hard restrictions
- recommended options appear first for each mode

### Runtime Profile Resolution

The runtime must resolve the active provider from the active profile instead of directly reading a single global `config.provider`.

The resolved provider should be used consistently in:

- terminal mode
- macOS menu bar app
- Linux tray app

### Linux Local Whisper Installer Logic

Current Linux setup installs local Whisper only if the single configured provider is `local_whisper`.

With profiles, setup must inspect both profiles. If either profile uses `local_whisper`, Linux setup should trigger the existing local Whisper installer flow.

## Proposed Config Shape

Illustrative shape:

```yaml
active_profile: fast

profiles:
  fast:
    provider: xai
    model: ""
  polished:
    provider: openrouter
    model: google/gemini-3.1-flash-lite-preview

providers:
  xai:
    api_key: xai-...
    base_url: https://api.x.ai/v1/stt

  openrouter:
    api_key: sk-or-...
    base_url: https://openrouter.ai/api/v1/chat/completions

  groq:
    api_key: gsk_...
    model: whisper-large-v3-turbo

  openai:
    api_key: sk-...
    model: whisper-1

  openai_compatible:
    base_url: http://localhost:8000/v1
    api_key: ""
    model: whisper-1

  local_whisper:
    model_size: large-v3-turbo
    device: auto
    compute_type: auto
```

Notes:

- `xai` may not need a model field at the profile level if the STT endpoint is effectively model-less.
- Profile schema should still permit a `model` field for consistency, but the wizard may skip it for providers that do not need it.

## Design Details

### Recommended Naming

UI label:

- `Mode`

Options:

- `Fast`
- `Polished`

These names should be used in:

- wizard copy
- tray/menu UI
- provider info UI
- docs

### Runtime Switching Semantics

If the user changes mode while idle:

- switch immediately

If the user changes mode while recording or processing:

- save the selected active profile
- apply the new provider after the current transcription finishes

This avoids state corruption or mid-request provider swaps.

### Error Handling

If a profile points to an invalid or unconfigured provider:

- show a useful error in the current platform surface
- preserve the selected mode in config
- suggest re-running setup

Do not silently fall back to another provider in this phase.

## Cross-Platform Implications

### macOS

Impacted areas:

- `setup_macos.sh` uses the Python wizard and should inherit the new profile flow automatically
- menu bar app needs the `Mode` submenu
- provider info alert must include mode details

No extra macOS-only provider setup logic is expected beyond xAI credential entry in the wizard.

### Linux

Impacted areas:

- `setup_linux.sh` uses the Python wizard and should inherit the new profile flow automatically
- tray app needs the `Mode` submenu
- provider info notification must include mode details
- local Whisper install trigger must inspect both profiles instead of one global provider

Wayland/X11 behavior is unchanged by this feature.

## Implementation Plan

### 1. Config Model

Files likely impacted:

- `talk_to_vibe/config/models.py`
- `talk_to_vibe/config/loader.py`
- `talk_to_vibe/config/constants.py`

Add:

- `active_profile`
- `profiles.fast`
- `profiles.polished`
- `xai` provider config section

### 2. Provider Resolution

Files likely impacted:

- `talk_to_vibe/providers/factory.py`
- `talk_to_vibe/cli.py`

Add:

- helper to resolve the effective provider/model from the active profile
- support for xAI provider creation

### 3. xAI Provider

Files likely impacted:

- `talk_to_vibe/providers/xai_stt.py`
- tests for request building and response parsing

Expected responsibilities:

- send xAI STT request
- parse transcript response
- surface meaningful provider errors

### 4. Wizard

Files likely impacted:

- `talk_to_vibe/config/wizard.py`

Changes:

- profile-oriented setup flow
- configure `Fast` first, then `Polished`
- recommendations without restrictions
- request credentials only when needed

### 5. Tray and Menu Bar UI

Files likely impacted:

- `talk_to_vibe/tray.py`
- `talk_to_vibe/menubar.py`

Changes:

- add `Mode` submenu
- radio-style profile selection
- persist `active_profile`
- rebuild active provider
- update provider info display

### 6. Linux Setup Script Logic

Files likely impacted:

- `setup_linux.sh`

Changes:

- inspect both profiles when deciding whether to install local Whisper support

### 7. Tests

Files likely impacted:

- `tests/test_config_loader.py`
- `tests/test_provider_factory.py`
- `tests/test_tray.py`
- `tests/test_menubar.py`
- new xAI provider tests

Test coverage should include:

- config round-trip for profiles
- active profile resolution
- xAI provider request/response parsing
- tray/menu mode switching
- provider info includes mode
- Linux local Whisper setup logic covers both profiles

## Risks

### Config Migration Complexity

Moving from one global provider to profiles adds config migration complexity. Existing configs must continue to load cleanly and be mapped into the new profile model.

### Runtime Provider Rebuild Bugs

Switching modes at runtime introduces the risk of stale provider objects or inconsistent UI state.

### Wizard Scope Creep

The wizard can become too long if every provider-specific option is surfaced during initial setup. The first version should focus on the minimum fields required for a usable configuration.

## Open Questions

1. How should existing single-provider configs be migrated into the new two-profile format?
2. Should xAI expose a model field at all, or be treated as model-less in the profile schema?
3. Should the wizard always require both profiles to be configured, or auto-fill one with defaults if the user wants the shortest path?

## Recommended Answers

1. Migrate existing configs by assigning the current provider/model to `polished` and seeding `fast` with xAI defaults if unset.
2. Treat xAI as a first-class provider that may not need a model prompt in the wizard.
3. Require both profiles, but provide smart defaults and allow Enter-to-accept paths.

## Acceptance Criteria

- Users can configure `Fast` and `Polished` during setup on both macOS and Linux.
- `Fast` defaults to xAI and `Polished` defaults to Gemini via OpenRouter.
- Users can choose any supported provider/model for either profile.
- Tray/menu UI exposes a `Mode` submenu with `Fast` and `Polished`.
- Switching mode updates the active runtime provider for subsequent transcriptions.
- Terminal mode uses the active profile.
- Linux local Whisper installer logic works if either profile uses `local_whisper`.
- Tests cover config, provider resolution, xAI provider behavior, and UI switching.
