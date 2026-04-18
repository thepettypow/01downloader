# Accelerate Pornhub Delivery Spec

## Why
Pornhub downloads are slow/unreliable and large files frequently fail to upload to Telegram, leading to a poor user experience and stalled “Downloading…” states.

## What Changes
- Improve Pornhub extraction reliability by adding site-specific yt-dlp options (headers, geo/age handling) and clearer phase/progress reporting.
- Reduce end-to-end time by defaulting to “fast path” outputs (prefer MP4/H.264 sources and avoid full re-encode unless required).
- Improve the download menu so users can choose from real available qualities per-link (resolution + estimated size), with a recommended default.
- Add an automatic “delivery strategy” that chooses the best way to deliver results:
  - Upload directly to Telegram when file size is within configured limits.
  - If too large or upload fails, use an alternative delivery method (configurable; default: chunked delivery in Telegram as multiple parts).
- Add explicit timeouts and fallback behavior so users always get a result (file, parts, or alternative link) or a clear error.

## Impact
- Affected specs: Download performance, Pornhub support, Telegram delivery reliability, Large file handling
- Affected code:
  - bot/downloaders/ytdlp_wrapper.py
  - bot/handlers/download.py
  - bot/utils/telegram_compress.py
  - bot/config/settings.py
  - docker-compose.yml / .env

## ADDED Requirements
### Requirement: Fast Delivery Strategy
The system SHALL select a delivery strategy based on file size limits and observed upload failures.

#### Scenario: Direct upload (success)
- **WHEN** a download completes and the output file size is <= `telegram_max_upload_bytes`
- **THEN** the bot uploads the file to Telegram with streaming enabled for MP4 videos.

#### Scenario: Oversize file (fallback)
- **WHEN** a download completes and the output file size is > `telegram_max_upload_bytes`
- **THEN** the bot SHALL attempt compression if enabled, and if still oversize SHALL use an alternative delivery method.

#### Scenario: Upload failure (fallback)
- **WHEN** Telegram upload fails with transient/network errors (e.g., “Cannot write to closing transport”)
- **THEN** the bot SHALL retry and, if the retry fails, switch to an alternative delivery method.

### Requirement: Alternative Delivery Method
The system SHALL support an alternative method when direct upload is impossible.

#### Default Alternative: Chunked Telegram Delivery
- **WHEN** alternative delivery is needed
- **THEN** the bot SHALL split the file into multiple parts <= `telegram_max_upload_bytes` and upload parts sequentially as documents, with a part index in the caption.

#### Optional Alternative: External Download Link (**Optional**)
- **WHEN** configured with `delivery_mode=link` and `public_base_url` is provided
- **THEN** the bot SHALL store the file under a temporary token and send a time-limited HTTPS download link.

### Requirement: Pornhub Reliability
The system SHALL download Pornhub URLs reliably without requiring the user to manually add headers/cookies in normal cases.

#### Scenario: Adult gating
- **WHEN** a Pornhub video requires age confirmation
- **THEN** the bot SHALL attempt extraction using `age_limit=18` and proper referer/origin headers.

### Requirement: Quality Menu
The system SHALL present a quality selection menu that reflects the media’s available formats.

#### Scenario: Video options shown
- **WHEN** the user sends a URL and the bot can extract format metadata without downloading
- **THEN** the bot shows a list of video options as “WIDTHxHEIGHT, ~SIZE MB” and marks a recommended option.

#### Scenario: Audio options shown
- **WHEN** the user sends a URL
- **THEN** the bot shows audio MP3 bitrate options with approximate size based on duration (when known).

## MODIFIED Requirements
### Requirement: Video Output
The system SHALL deliver videos as Telegram-streamable MP4:
- Prefer selecting MP4/H.264 sources when available.
- Ensure `moov` atom is at the beginning (faststart) for streaming.
- Only re-encode if remux/faststart is insufficient or if compression is required.

### Requirement: Performance Target
The system SHOULD deliver typical Pornhub videos within 30 seconds under normal network conditions.
- If not achievable (large source, slow network, forced re-encode), the bot SHALL provide progress/phase updates and a deterministic fallback path (lower quality suggestion, compression, or alternative delivery).

## REMOVED Requirements
### Requirement: Single-file-only Playlist Behavior
**Reason**: Large multi-entry downloads and single-file assumptions cause timeouts and leftover artifacts.
**Migration**: Keep playlist limiting by default; future playlist support can be added as a separate spec.
