# ClipPer V0

A desktop-first personal video workspace: paste a YouTube URL once, then download a video, extract a short clip, or search and select captions. Next.js and FastAPI are separate applications. No accounts, database, payments, AI, or other platforms are included.

## Project structure

```
web/                         Next.js App Router, TypeScript, Tailwind CSS
  app/page.tsx               Shared video workspace and three tools
  app/globals.css            Responsive dark interface
  lib/api.ts                 API types, time formatting, TXT/SRT exports
backend/
  app/main.py                FastAPI, CORS, clean errors, cleanup lifecycle
  app/api/video.py           HTTP routes
  app/config.py              Central processing limits and environment
  app/models/video.py        Validated request models
  app/services/              Metadata, captions, processing, jobs, storage
  app/utils/                 URL and timestamp validation
  tests/                     Unit, API, and service tests
render.yaml                  Render Docker service definition
```

## Requirements

- Node.js 22+ and npm (also needed on the backend for yt-dlp's standard JavaScript support).
- Python 3.12+.
- Actual `ffmpeg` and `ffprobe` executables on PATH, with libx264/AAC encoding support. Installing a Python package called ffmpeg is not sufficient.
- yt-dlp and its default dependencies, installed by the backend requirements.

The backend Docker image includes Python, Node, FFmpeg, and yt-dlp. Current YouTube support uses the standard yt-dlp JavaScript components; see [yt-dlp dependencies](https://github.com/yt-dlp/yt-dlp#dependencies).

## Run locally

From the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock.txt
Copy-Item backend/.env.example backend/.env
Copy-Item web/.env.example web/.env.local
```

The lock file records the tested Python environment. `requirements.txt` defines upgrade ranges; when upgrading yt-dlp, regenerate the lock and rerun tests. On macOS/Linux, use `python3 -m venv .venv` and `.venv/bin/python` instead.

Terminal 1:

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --env-file .env --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
cd web
npm ci
npm run dev
```

Open http://localhost:3000. The API health endpoint is http://localhost:8000/health and interactive API docs are at http://localhost:8000/docs.

For this checkout, a local verification copy of FFmpeg was downloaded under `.tools/ffmpeg/ffmpeg-master-latest-win64-gpl/bin` (ignored by Git). You can prepend that directory to PATH in the backend terminal. It is not a dependency to commit or deploy.

### Environment variables

| Project | Variable | Default / purpose |
| --- | --- | --- |
| web | `NEXT_PUBLIC_API_URL` | `http://localhost:8000`; browser-visible API origin, set at build time |
| backend | `FRONTEND_ORIGIN` | `http://localhost:3000`; one exact allowed browser origin, no trailing slash |
| backend | `JOB_ROOT` | `./tmp/jobs`; temporary processing directory |
| backend | `JOB_TTL_SECONDS` | `3600`; completed job expiration |
| Render | `PORT` | Render provides this; Docker defaults to 8000 |

Backend `.env` is loaded by uvicorn's `--env-file` flag. Render injects environment variables directly. Do not commit `.env` files.

## Workflow and API

1. `POST /api/video/info` with `{ "url": "..." }` validates an exact YouTube host and video-ID route, then canonicalizes to an HTTPS watch URL before yt-dlp metadata extraction. Supports watch, Shorts, mobile YouTube, and youtu.be. Lists and arbitrary URLs are rejected. Returns only normalized video fields.
2. `POST /api/video/transcript` with the same body prefers creator subtitles, then automatic captions. English is preferred within each group; otherwise the first available language is used. Only the caption document is fetched. Responses contain language, source type, and timestamped segments. No speech-to-text fallback is implemented.
3. `POST /api/video/download` accepts `{ "url": "...", "quality": "1080" }`. Quality is `best`, `1080`, or `720`. Best is capped at 1080p. Resolution never exceeds the chosen ceiling and lower source resolutions are retained. AVC/AAC is preferred. Other codecs are converted only when required for H.264/AAC MP4 compatibility.
4. `POST /api/video/clip` also accepts numeric `start` and `end` in seconds. The UI accepts HH:MM:SS with optional milliseconds. yt-dlp asks FFmpeg for only that section. Stream copy is attempted first. The output is probed for duration and the first second is decoded to check usability. If a keyframe cut produces an inaccurate/unusable result, only the selected section is downloaded again with re-encoding. There is no full-source download fallback. Frame/audio packet rounding can cause a small duration difference.
5. Processing routes return HTTP 202 and a random job ID. `GET /api/video/jobs/{id}` reports Preparing, Downloading, Merging, Ready, or Failed. Byte percentages are approximate, may restart for multiple streams, and are indeterminate when FFmpeg does not expose byte totals.
6. `GET /api/video/jobs/{id}/file` delivers the generated MP4. Files are deleted after delivery, or expire after one hour if not downloaded. Active file responses are protected from the expiration sweep. Files are temporary and should be downloaded once; restarting or redeploying the backend invalidates in-memory jobs.

The frontend keeps a single analyzed video in memory. Switching tabs preserves it. Transcript search uses deferred input and memoized filtering; rendering is limited to 80 matching rows per page. Select a first row and then a last row to select the entire original consecutive range (including rows hidden by a filter). Clear selection starts over. A timestamp sets Clip start; Create clip from selection sets both boundaries without rounding away caption milliseconds. TXT/SRT export happens in the browser.

## V0 limits

Defined in `backend/app/config.py` and enforced by backend services:

| Limit | Value |
| --- | --- |
| Requested resolution | 1080p maximum |
| Full video download | 60 minutes |
| Clip source | 3 hours |
| Generated clip | 5 minutes |
| Simultaneous processing jobs | 1; additional requests are rejected |

Run exactly **one API worker and one Render instance**. The in-memory concurrency guard does not coordinate multiple processes. Metadata and caption requests do not occupy the processing slot. Frontend controls repeat limits for immediate feedback; backend validation is authoritative.

## Temporary storage and security

Jobs use random UUID directories and fixed internal filenames. Titles never become filesystem paths. API callers cannot provide output paths or FFmpeg flags. Processes are launched using argument arrays without a shell. User URLs are validated and replaced with canonical YouTube video URLs, so redirect endpoints and arbitrary hosts cannot be supplied. Upstream media URLs come only from the YouTube extractor. No cookies, login mechanisms, geo bypass, DRM workarounds, proxy rotation, or access-restriction bypass is configured. Restricted videos return clean errors.

A lifespan sweeper removes expired terminal jobs and stale orphan directories every minute. Failed jobs immediately remove partial files. The local storage adapter is separate from orchestration; a future object-storage adapter can upload outputs and supply signed delivery URLs. Do not assume Render disk persistence.

This is a personal V0 without authentication. CORS limits browser origins but is not authentication or server-side abuse protection. Keep deployment access appropriate to personal use. A public SaaS requires authentication, rate/usage limits, a persistent queue, and storage before scaling.

## Checks

```powershell
cd web
npm run lint
npm run typecheck
npm run build
cd ../backend
..\.venv\Scripts\python.exe -m pytest -q
```

On environments with a restricted system temp folder, use a fresh dedicated workspace directory: `python -m pytest -q --basetemp=./tmp/test-run`. Pytest owns and clears that directory; do not point it at any directory containing user files.

Tests cover supported hosts, SSRF-shaped URLs, malformed IDs, playlist rejection, timestamp parsing, finite numbers, duration boundaries, normalized API output, quality caps, caption preference, single-job concurrency, delivery cleanup, expiration, and early failure before downloading oversized requests. See `VERIFICATION.md` for the checks performed during implementation.

## Vercel frontend deployment

1. Import this repository into Vercel and select **web** as the root directory.
2. Use the Next.js preset, `npm ci`, and `npm run build`.
3. Set `NEXT_PUBLIC_API_URL` to the HTTPS Render backend origin before building.
4. Redeploy when that public environment variable changes.
5. Set the backend's `FRONTEND_ORIGIN` to the exact Vercel production origin. Preview deployments need their own matching backend origin configuration.

No production URL is hardcoded. The frontend does not proxy large video files through Vercel; the browser downloads them directly from Render.

## Render backend deployment

1. Create a Blueprint from `render.yaml`, or a Docker web service with root directory **backend** and Dockerfile **Dockerfile**.
2. Set `FRONTEND_ORIGIN` to the frontend HTTPS origin. Keep `JOB_ROOT=/tmp/jobs`.
3. Use one service instance. The Docker command starts one worker and binds Render's port.
4. Check `/health`, then test metadata, captions, and a short clip before relying on the deployment.
5. Allow sufficient RAM, CPU, temporary disk, and outbound bandwidth for FFmpeg. The supplied Blueprint selects a paid starter service; actual resource needs depend on source bitrate and whether encoding is necessary.

YouTube may deny requests from hosting-provider addresses even when videos work locally. The application reports those failures and does not attempt to bypass platform restrictions. No Render or Vercel deployment was performed as part of local implementation.

## Future architecture

Replace the in-memory job manager with a durable queue and worker when adding accounts or scale. Keep API request/response contracts stable. Replace LocalStorage and the file-delivery endpoint with an object store and signed URLs. Compose CaptionProvider with a future transcription provider while retaining the same transcript response. Add providers for other platforms only behind explicit URL validation and normalized metadata. Authentication, billing, history, and usage accounting can wrap the existing API without embedding video processing into Next.js.
