# Tasks
- [x] Task 1: Research and choose the PO Token Provider approach
  - [x] Confirm yt-dlp PO Token guide recommended setup and choose provider (bgutil or alternative)
  - [x] Decide deployment mode: sidecar service (recommended) vs in-process script invocation
  - [x] Define minimal config surface (env vars) and safe defaults

- [x] Task 2: Add PO Token Provider to deployment
  - [x] Add required provider service to docker-compose (local-only access)
  - [x] Add required runtime deps (node/deno/docker image) without introducing secrets into images
  - [x] Add a health check / startup validation path

- [x] Task 3: Integrate PO Token Provider with yt-dlp calls
  - [x] Add config for selecting YouTube clients and PO-token-required clients (mweb/web_safari/etc.)
  - [x] Ensure both probe and download paths use the same YouTube settings
  - [x] Keep existing cookie rotation logic as fallback

- [x] Task 4: Make cookie pool operationally stable
  - [x] Define cookie directory structure and naming convention
  - [x] Add “cookie freshness” guidance (operator workflow) and rotation limits
  - [x] Add optional per-cookie metadata (last_used, last_failed) if needed

- [x] Task 5: Confirm OAuth is not used (as per yt-dlp YouTube extractor guidance)
  - [x] Ensure no OAuth flags are introduced into bot configuration
  - [x] Provide operator guidance to use cookie export workflow instead

- [x] Task 6: Error classification + user messaging
  - [x] Add explicit detection for YouTube bot-check vs PO-token missing vs cookie missing/expired
  - [x] Ensure errors do not leak tokens, cookies, proxies, or headers

- [ ] Task 7: Verification
  - [x] Add a minimal non-network unit test for rotation selection logic (cookies/proxy/provider ordering)
  - [ ] Run a manual smoke test against a known YouTube URL from the server environment (operator-only)

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Tasks 1–2
- Task 6 depends on Tasks 3–5
- Task 7 depends on Tasks 2–6
