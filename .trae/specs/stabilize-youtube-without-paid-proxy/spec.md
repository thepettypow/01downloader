# Stabilize YouTube Without Paid Proxy Spec

## Why
YouTube frequently blocks downloads from datacenter IPs with “Sign in to confirm you’re not a bot”, causing daily operational failures and requiring manual cookie refreshes.

## What Changes
- Add a first-class “YouTube anti-bot mitigation” stack that does not depend on paid residential proxies:
  - PO Token Provider integration (recommended by yt-dlp) to satisfy YouTube’s PO Token enforcement and reduce bot-check failures.
  - Cookie pool support (multiple cookies.txt files) with rotation on YouTube bot-check errors.
- Add config knobs to enable/disable each mechanism and control retry/rotation behavior.
- Add deployment support (docker-compose) to run any required local services for PO token generation.

## Impact
- Affected specs: YouTube extraction reliability, authentication/session handling, deployment configuration
- Affected code:
  - bot/downloaders/ytdlp_wrapper.py
  - bot/downloaders/quick_ytdlp.py
  - bot/config/settings.py
  - docker-compose.yml

## ADDED Requirements
### Requirement: PO Token Provider Support
The system SHALL support using a PO Token Provider plugin to supply YouTube PO tokens automatically.

#### Scenario: Provider enabled
- **WHEN** YouTube extraction requires a PO token for the selected client
- **THEN** yt-dlp SHALL obtain PO tokens via an installed provider plugin instead of failing with HTTP 403 / bot-check errors.

#### Scenario: Provider unavailable
- **WHEN** the provider plugin/service is missing or unhealthy
- **THEN** the bot SHALL fall back to cookie pool rotation and surface a clear error indicating PO-token provider is unavailable.

### Requirement: Cookie Pool Rotation
The system SHALL support multiple cookie files and rotate them automatically on YouTube bot-check failures.

#### Scenario: Cookie directory configured
- **WHEN** `YTDLP_COOKIE_DIR` is set and contains multiple `*.txt` files
- **THEN** the bot SHALL try cookies in a deterministic order and retry YouTube extraction on “confirm you’re not a bot” failures.

#### Scenario: No cookies available
- **WHEN** cookie pool is not configured
- **THEN** the bot SHALL still attempt extraction (PO token provider + hardened client) and return a clear “needs auth” error if blocked.

### Requirement: Safe Failure Messaging
The system SHALL distinguish between:
- YouTube bot-check / datacenter-IP blocks
- Missing PO token provider
- Missing/expired cookies
and present a targeted remediation hint for each category.

## MODIFIED Requirements
### Requirement: YouTube Download Flow
The YouTube download flow SHALL attempt mechanisms in this order (configurable):
1) PO token provider + hardened YouTube client selection
2) Cookie pool rotation retries
3) Fail with a targeted remediation message

## REMOVED Requirements
### Requirement: OAuth Device-Code Login
**Reason**: yt-dlp documents that YouTube restrictions have made OAuth login ineffective; cookie-based authentication is required.
**Migration**: Do not implement OAuth; guide operators to use cookie export workflow instead.
