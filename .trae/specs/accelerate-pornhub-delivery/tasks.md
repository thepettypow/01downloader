# Tasks
- [x] Task 1: Add reliable Pornhub extractor defaults
  - [x] Add Pornhub-specific yt-dlp options (headers/referer/origin, age_limit, format preferences, retry policy)
  - [x] Validate Pornhub download works for a representative public link

- [x] Task 2: Make delivery strategy smart and fast by default
  - [x] Prefer “fast path” MP4 output without re-encode when possible
  - [x] Keep Telegram streaming compatibility (faststart, yuv420p when re-encoding)
  - [x] Improve status reporting (phase + percent) to the user message

- [x] Task 3: Add alternative delivery for oversize / failed uploads
  - [x] Implement chunked file delivery (split into <= telegram_max_upload_bytes parts, upload sequentially)
  - [x] Provide clear captions (title + “part X/Y”) and cleanup after sending
  - [x] Add config switches for max upload bytes, hard 2GB cap, compression enable, and delivery mode

- [x] Task 4: Improve Telegram upload robustness
  - [x] Implement retry/backoff on transient upload errors
  - [x] Ensure request timeouts are long enough for large uploads without breaking polling

- [x] Task 5: Verification
  - [x] Run unit tests for file chunking logic
  - [x] Verify Pornhub defaults + fast-path mp4 settings exist in code (grep-based)
  - [x] Verify upload fallback uses chunking with parts <= telegram_max_upload_bytes (grep-based)

- [x] Task 6: Improve quality selection menu (resolution + estimated size)
  - [x] Extract formats without downloading and build a per-link quality list
  - [x] Show video options (WxH + ~MB) and mark a recommended default
  - [x] Show audio bitrate options with estimated size when duration is known

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 can be done in parallel with Task 3
- Task 5 depends on Tasks 1–4
- Task 6 depends on Task 1
