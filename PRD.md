# PRD: SocialMediaDownloader Bot

**Product Name:** 01Downloader  
**Version:** 1.0  
**Date:** April 2026  
**Status:** Draft → Ready for implementation  

## 1. Overview

A Telegram bot that lets users send **any social media link** (or direct MP3 link) and instantly receive the media back as video, audio (MP3), or document.

Supported sources (via yt-dlp + spotdl):
- Instagram (posts, reels, stories, IGTV, highlights)
- YouTube (videos, shorts, playlists, live)
- TikTok
- Facebook / Reels
- X (Twitter) posts & videos
- SoundCloud
- Spotify (tracks, albums, playlists)
- Vimeo
- VK (videos, audios)
- Pornhub
- XVideos
- **Any direct or redirecting MP3 link** (generic fallback)

## 2. Goals & Objectives

- **Primary:** 100% reliable download + delivery for the listed platforms.
- **Secondary:** Handle any MP3 source by following redirects and extracting the final audio file.
- Deliver media in the best possible quality while respecting Telegram limits (up to 2 GB).
- Be fast, user-friendly, and abuse-resistant.
- Open-source friendly and easy to self-host.

## 3. Target Users

- Individuals who want to save media without installing multiple apps.
- Content creators, researchers, archivists.
- Users in regions where certain platforms are blocked or have download restrictions.
- Adult content consumers (Pornhub/XVideos support is explicit requirement).

## 4. Core Features

### 4.1 User-Facing
- **Link Detection:** Bot reacts to any message containing a URL (private chat or group).
- **Download Modes** (auto-detected + manual override):
  - Video (best quality with audio)
  - Audio-only → MP3 (with metadata: title, artist, thumbnail, album art)
  - Document (for very large files or when user forces it)
- **Progress Feedback:** "Downloading… 45%" + thumbnail preview when possible.
- **Multiple Links:** Process all links in a single message.
- **Commands:**
  - `/start` – Welcome + quick guide
  - `/help` – Supported sites + examples
  - `/audio` – Force audio-only for next link
  - `/video` – Force video
  - `/stats` – User’s download count (if DB enabled)
  - `/settings` – Quality preferences, daily limit toggle
- **Generic MP3 Handler:** If yt-dlp fails, fallback to `requests` → follow redirects → check `Content-Type: audio/mpeg` → download & send as audio/document.
- **Error Handling:** Friendly messages ("This link is not supported yet", "File too large", "Rate limit reached", etc.).

### 4.2 Technical Features
- yt-dlp as primary engine with smart options:
  - `--extract-audio --audio-format mp3 --audio-quality 0` for audio
  - Best video+audio merge for video
  - Cookie support for age-restricted / logged-in content (optional)
- Spotify via spotdl integration.
- Automatic cleanup of temporary files.
- Rate limiting per user (configurable, default 50 downloads/day).
- Global concurrency limit (e.g., max 4 simultaneous yt-dlp processes).

## 5. User Stories

- As a user, I send a TikTok link → receive MP4 in <30 seconds.
- As a user, I send a Spotify track → receive high-quality MP3 with correct tags and cover art.
- As a user, I send a direct `.mp3` link or a page that redirects to MP3 → bot downloads the actual file.
- As a user, I send 5 links at once → bot processes all of them.
- As an admin, I can set daily limits and monitor usage via logs.

## 6. Technical Stack (Final Decision)

- **Language:** Python 3.12+
- **Bot:** aiogram 3.x (asyncio)
- **Downloader:** yt-dlp + spotdl
- **Processing:** FFmpeg
- **Async:** aiohttp + aiofiles
- **DB:** aiosqlite
- **Queue:** asyncio.Semaphore (Redis optional)
- **Config:** pydantic-settings
- **Deployment:** Docker + docker-compose
- **Hosting:** VPS with ≥4 cores / 8 GB RAM

## 7. High-Level Architecture

```
Telegram → aiogram (webhook or polling)
          ↓
   URL Parser + Queue
          ↓
   yt-dlp / spotdl (in subprocess or via Python API)
          ↓
   Temp folder → FFmpeg post-processing
          ↓
   Telegram sendVideo / sendAudio / sendDocument (up to 2 GB)
          ↓
   Cleanup + logging
```

- `handlers/` – message & command handlers
- `downloaders/` – wrapper around yt-dlp + generic MP3 fallback
- `utils/` – progress reporter, file cleaner, rate limiter
- `models/` – SQLAlchemy or raw aiosqlite models
- `config/` – settings

## 8. Non-Functional Requirements

- **Performance:** < 60 seconds for most videos (< 500 MB). Audio-only should be < 20 s.
- **Scalability:** Handle 100+ concurrent users with proper queuing.
- **Reliability:** Graceful degradation if a site breaks (yt-dlp updates are frequent).
- **Security:**
  - Validate URLs (no SSRF).
  - No storage of user media after sending.
  - Rate limiting & abuse protection.
- **Privacy:** No logging of personal data beyond necessary (user ID for limits).
- **Maintainability:** Clear code, comprehensive logging, easy to add new extractors.
- **Compliance:** Respect platform ToS (bot is for personal use).

## 9. Out of Scope (Phase 2+)

- Instagram login / private accounts (requires user cookies – complex).
- Bulk playlist downloads > 50 items.
- Web UI / admin dashboard.
- Payment / premium features.
- Support for every obscure adult site.

## 10. Risks & Mitigations

| Risk                          | Likelihood | Mitigation                          |
|-------------------------------|------------|-------------------------------------|
| Platform changes break yt-dlp | High       | Auto-update yt-dlp daily in Docker |
| High CPU usage                | Medium     | Semaphore + queue                   |
| Telegram 2 GB limit issues    | Low        | Use local Bot API server if needed  |
| Spotify quality complaints    | Low        | spotdl + fallback to yt-dlp         |

## 11. Implementation Phases

**Phase 1 (MVP – 2 weeks)**
- aiogram bot skeleton
- yt-dlp core integration
- Video + Audio modes
- Generic MP3 fallback
- Basic rate limiting

**Phase 2 (Polishing – 1 week)**
- Progress messages
- Metadata & thumbnails
- Spotify via spotdl
- Docker setup

**Phase 3 (Production)**
- Redis queue + DB
- Logging & monitoring
- Public repo + documentation



notes: we need to log all the users activities and downloads by username. and beside commands we need to have buttons, colored buttons. and it should have 2 languages, english and persian.
---

**Ready to build?**  
Clone this PRD into your repo as `PRD.md`, run `docker-compose up --build`, and you’ll have a production-grade social media downloader in record time.

Let me know if you want the full `docker-compose.yml`, project structure, or the initial `main.py` skeleton next!
