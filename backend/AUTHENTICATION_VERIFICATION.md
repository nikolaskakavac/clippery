# YouTube authentication implementation — 2026-10-20

## Result and limits

Implemented optional operator-supplied Netscape cookies, anonymous-first bounded
fallback, shared metadata/download/caption behavior, sanitized diagnostics and
native Render configuration. No frontend or API schema changes were made for
this task. No real account cookies were obtained, stored in the repo, or tested.
Nothing was committed, pushed or deployed during this implementation task.

This is **not yet a verified fix on Render**. Success requires a real metadata
request and delivered video from that deployed service. Cookies cannot guarantee
resolution of a datacenter/IP challenge.

## Architecture inspected

- `video_service.py`: shared options, metadata and duration/availability checks.
- `download_service.py`: quality-aware adaptive selection, range downloading,
  quality guard, FFmpeg remux/precise cut, output probing and cleanup.
- `clip_service.py`: validates IN/OUT, five-minute clip and source-duration limits.
- `transcript_service.py`: metadata, caption selection and JSON3 fetching.
- `jobs.py` / `storage.py`: one in-memory processing slot, safe public errors,
  per-job directories, one-hour expiration, download-reader lifecycle.
- `tiktok_service.py`: separate yt-dlp configuration, deliberately unchanged.
- `main.py`, API routes/models: CORS, validation, lifecycle, public contracts.
- Render/build/runtime manifests, Python dependency files and legacy Dockerfile.

The original Render failure occurs before token-generator invocation. Earlier
matching-version local extraction succeeded. That evidence suggests an
environment-specific denial, not proof that an account login is sufficient.

## Files changed in this task

| File | Change |
| --- | --- |
| `.gitignore` | Ignore cookie exports/encoded files |
| `README.md` | Native deployment, cookie setup/rotation, risks, diagnostic commands |
| `render.yaml` | Match existing native Python architecture and runtime pins |
| `backend/.python-version` | Pin locally tested Python 3.12.14 |
| `backend/.dockerignore` | Exclude credential exports from legacy Docker context |
| `backend/.env.example` | Optional cookie variable names, no values |
| `backend/requirements.txt` | Explicit `yt-dlp-ejs==0.8.0` pin |
| `backend/build.sh` | Fail-fast toolchain check |
| `backend/vendor/README.md` | Correct Node pin and reference optional auth |
| `backend/app/main.py` | Opt-in startup runtime/cookie-parseability summary |
| `backend/app/diagnostics.py` | CLI runtime check, optional public metadata/clip test |
| `backend/app/services/youtube_auth.py` | Strict cookie parsing, private temporary copies and cleanup |
| `backend/app/services/youtube_errors.py` | Safe failure categories and public messages |
| `backend/app/services/video_service.py` | Anonymous-first cookie/network retry runner, safe logger |
| `backend/app/services/download_service.py` | Use shared retry runner; re-resolve source on session retry |
| `backend/app/services/transcript_service.py` | Carry same cookie copy through metadata and caption fetch |
| `backend/tests/test_youtube_auth.py` | Cookie lifecycle, fallback, download/clip/transcript regressions |
| `backend/tests/test_runtime_diagnostics.py` | Runtime report and credential-log protection tests |
| `backend/tests/test_youtube_diagnostics.py` | Sanitized provider logging assertions |
| `backend/tests/test_youtube_provider.py` | Shared safe logger and classified failures |
| `backend/tests/test_services.py` | Adapt caption mocks to explicit session options |
| `backend/AUTHENTICATION_VERIFICATION.md` | This report |

Pre-existing uncommitted changes remain in `backend/app/config.py`,
`backend/app/utils/time.py`, `backend/tests/test_validation.py`,
`web/app/page.tsx`, `web/components/clip-list.tsx`, and
`backend/tests/test_clip_quality.py`. The pre-existing local precise-cut change
in `download_service.py` was retained. Desktop launchers/assets remain untracked
and untouched. These are not new authentication changes.

## Dependencies and preservation

- yt-dlp remains `2026.8.19`, the official latest stable release checked during
  this task; already installed with `[default]`.
- EJS is explicitly pinned to `0.8.0`, matching the existing lock/environment.
- bgutil remains matching plugin/script `2.0.0`, immutable source commit
  `37169ee2656e08c5c2e5dc9df4c598c0cb4c88a8`; no HTTP provider service added.
- Node remains `24.14.0`; Python now pinned to the locally tested `3.12.14`.
  Python 3.14 was not proven to cause the Render failure.
- CRF 16/medium for Best, CRF 18/medium for other clips, AAC 192k, 1080p ceiling,
  no upscaling/frame-rate conversion, five-minute clips, four-hour source limit
  and 60-minute full-download limit remain as in the working tree.

## Verification

From `backend`, with local FFmpeg on PATH:

```text
..\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=./tmp/auth-release-tests
158 passed, 1 existing Starlette deprecation warning (17.98 seconds)

..\.venv\Scripts\python.exe -m compileall -q app
Passed

..\.venv\Scripts\python.exe -m pip check
No broken requirements found
```

`bash -n backend/build.sh`, Render YAML parse, sensitive-file ignore checks and
`git diff --check` passed. The native Linux build itself was not executed here.
Frontend lint/build were not rerun because this task changes no frontend code.

Actual local test, no cookies configured:

```text
python -m app.diagnostics --check-runtime --url https://www.youtube.com/watch?v=j-2yfhRUQ64 --download
Python 3.12.14; Node 24.14.0; yt-dlp 2026.8.19; EJS 0.8.0; bgutil 2.0.0
metadata_ok=true; source duration=1525 seconds
download_ok=true; five-second processed output=713467 bytes
```

The temporary diagnostic clip was removed afterward. Real cookie authentication
and deployed Render extraction/download remain untested; cookie tests use
synthetic credentials and mocked YouTube responses.

## Manual deployment

After reviewing/publishing the changes, retain `backend` as Root Directory,
`bash build.sh` as Build Command, and use:

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
```

Render variables:

- `PYTHON_VERSION=3.12.14`
- `NODE_VERSION=24.14.0`
- `FRONTEND_ORIGIN=<exact Vercel origin>`
- `JOB_ROOT=/tmp/jobs`
- `JOB_TTL_SECONDS=3600` (optional default)
- `YTDLP_DIAGNOSTICS=1` temporarily
- `YOUTUBE_COOKIES_BASE64=<secret Base64 Netscape export>` only if opting in
- Do not configure `YOUTUBE_COOKIES_FILE` on Render; that method is local only.

Redeploy after environment changes. Check `/health`, startup diagnostics, real
Analyze, download, clip and transcript workflows. If YouTube still challenges
the session, do not repeatedly retry or assume a more expensive server fixes it.
Check parseability, replace expired credentials once, and inspect safe categories.
Cookies and upgrades alone may not resolve a server-IP restriction. See README
for account-security risks and the existing unauthenticated public API limitation.
