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
render.yaml                  Native Python Render service definition
```

## Requirements

- Node.js 22+ and npm (also needed on the backend for yt-dlp's standard JavaScript support).
- Python 3.12+.
- Actual `ffmpeg` and `ffprobe` executables on PATH, with libx264/AAC encoding support. Installing a Python package called ffmpeg is not sufficient.
- yt-dlp and its default dependencies, installed by the backend requirements.

The deployed service remains native Python. `backend/build.sh` verifies Node,
yt-dlp-ejs, FFmpeg and ffprobe, and builds the pinned bgutil script generator.
Python is pinned to **3.12.14** (the locally tested version) and Node to **24.14.0**.
The previous Render Python 3.14 environment was not proven to cause the 403;
the pin removes environment drift, rather than claiming a fix for bot checks.
The legacy Dockerfile is not the deployment path for this configuration.

`yt-dlp[default]==2026.8.19` already matches the official stable release checked
on 2026-10-20; `yt-dlp-ejs==0.8.0` is explicitly pinned as well as supplied by that extra.
No speculative nightly upgrade or unsupported client switch is used.
The matching bgutil Python/script versions remain 2.0.0. Newer bgutil 2.0.1/2.0.2
release notes describe dependency security updates, not a documented fix for
this Render authentication failure; review those separately with their matching
source revision. See [yt-dlp releases](https://github.com/yt-dlp/yt-dlp/releases/latest)
and [bgutil releases](https://github.com/Brainicism/bgutil-ytdlp-pot-provider/releases).

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
| Render | `PORT` | Render provides this; used by the native start command |

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

Jobs use random UUID directories and fixed internal filenames. Titles never become filesystem paths. API callers cannot provide output paths or FFmpeg flags. Processes are launched using argument arrays without a shell. User URLs are validated and replaced with canonical YouTube video URLs, so redirect endpoints and arbitrary hosts cannot be supplied. Upstream media URLs come only from the YouTube extractor. Operator-provided YouTube cookies are optional and isolated from TikTok. No geo bypass, DRM workarounds, proxy rotation, or browser-profile access is configured. Restricted videos return clean errors.

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

Keep the existing **native Python** web service. Do not create another service or
switch to Docker. `render.yaml` now describes that architecture and uses the free
plan for new Blueprint deployments; it does not change your existing account by
itself. Free compute is not a performance or uptime guarantee for FFmpeg.

- Root Directory: `backend`
- Build Command: `bash build.sh`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`
- Health Check Path: `/health` (`/` returning 404 is expected)
- One instance / one worker: job state and concurrency limits are in memory.

Set these in the existing service's **Environment** settings:

| Variable | Value / action |
| --- | --- |
| `PYTHON_VERSION` | `3.12.14` (matches local testing) |
| `NODE_VERSION` | `24.14.0` (required at build **and runtime**) |
| `FRONTEND_ORIGIN` | Exact production Vercel HTTPS origin, no trailing slash |
| `JOB_ROOT` | `/tmp/jobs` |
| `JOB_TTL_SECONDS` | Optional; default `3600` |
| `YTDLP_DIAGNOSTICS` | `1` temporarily; `0` after investigation |
| `YOUTUBE_COOKIES_BASE64` | Optional secret; Base64-encoded Netscape export |
| `YOUTUBE_COOKIES_FILE` | **Do not set on Render**; local development only |

Render's environment variables override version files. Save and redeploy after
changing them. The build checks for Node >=22, EJS, FFmpeg and ffprobe and fails
clearly if any is absent; it does not silently deploy a broken toolchain or
install unverified binary downloads. Render's native runtime currently lists
FFmpeg among its tools. If your runtime lacks it, inspect that failure before
considering an infrastructure migration.

[Render runtimes](https://render.com/docs/native-runtimes),
[Node version](https://render.com/docs/node-version),
[Python version](https://render.com/docs/python-version).

### Optional YouTube cookie authentication

Public requests always start without configured cookies. Only an authentication,
bot-check or rejected-cookie error triggers one cookie retry. A transient network
failure gets at most one additional application retry, with a two-second delay
and IPv4 binding; total session attempts never exceed three. yt-dlp HTTP and
fragment retries are separately bounded at two, extractor retries at one, with
exponential HTTP/fragment delays capped at eight seconds. Requests have a
25-second socket timeout, one-second inter-request delay, and downloads a
five-to-ten-second delay. Rate limits and generic 403s do not trigger repeated
cookie attempts, identity rotation or proxy services.

The whole metadata/download/caption operation is retried. Download retries
re-resolve media URLs and remove only that job's partial source files. A caption
retry re-resolves its URL with the same cookie copy used for fetching captions.
FFmpeg quality, source ceilings, IN/OUT validation and export contracts are not
changed by authentication.

**Cookies are session credentials.** Export only from a browser session you own
and are authorized to use. Following the official YouTube extractor instructions,
log in in a fresh private/incognito window, visit `https://www.youtube.com/robots.txt`
in that session, export `youtube.com` cookies in **Netscape cookies.txt format**
with an exporter recommended by the yt-dlp FAQ, then close that private session.
Do not export unrelated browsing accounts. Do not send the file or Base64 value
in chat, publish it, or commit it. Base64 is encoding, not encryption.

[Official cookie export instructions](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies),
[yt-dlp cookie FAQ](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp).

For local development, place the export outside the repository and set an
absolute path in the backend process environment or ignored `backend/.env`:

```powershell
$env:YOUTUBE_COOKIES_FILE = 'C:\private\youtube-cookies.txt'
```

Start uvicorn with `--env-file .env` if using that file; the diagnostic CLI uses
its process environment. The source cookie file is validated and copied, never
modified by yt-dlp. On Render, file-based configuration is rejected.

To create the Render Base64 value on **Windows PowerShell** without printing it:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes('C:\private\youtube-cookies.txt')) | Set-Clipboard
```

Paste the clipboard value only into Render's secret `YOUTUBE_COOKIES_BASE64`
field, save/redeploy, and clear the clipboard afterward (`Set-Clipboard -Value ''`).

On **Linux/macOS**, create a private encoded file without printing its contents:

```bash
umask 077
base64 < /private/path/youtube-cookies.txt | tr -d '\n' > /private/path/youtube-cookies.b64
```

Copy that file's contents into Render Environment, then remove the encoded copy
when no longer needed. Never include either file in a Git commit. Cookie export
patterns are ignored by Git and excluded from the legacy Docker build context.

If both variables are set, Base64 takes precedence. Validation accepts Netscape
rows (including HttpOnly), limits input size, retains only youtube.com domains,
and rejects malformed or wholly expired exports. Successful parsing does **not**
prove that cookies contain login credentials or that YouTube still accepts them.
If authentication is rejected, export fresh cookies, replace the environment
value and redeploy. To disable authentication, remove both variables.

Each cookie attempt has an isolated temporary directory and a `0600` file on
POSIX; Windows relies on the current user's temp-directory ACL. The copy is
removed in `finally` after success/failure and after yt-dlp closes, including
ordinary exception unwinding. A forced process kill cannot run cleanup; ephemeral
host temp storage is not a credential vault. No cookie values, authentication
headers, signed media URLs or full upstream responses are logged or returned.

Using account cookies on hosted infrastructure can trigger account security
checks or account restrictions. This service has **no user authentication**:
all callers reaching it can trigger use of the operator's configured session.
Do not attach a valuable account to an unrestricted public deployment. CORS is
not an access-control mechanism. Cookies do not make restricted content public
and do not guarantee access when YouTube challenges a datacenter IP. Even the
referenced [issue #12045](https://github.com/yt-dlp/yt-dlp/issues/12045) reports
failures with cookies; it is not a guaranteed workaround.

### Diagnostics and deployed verification

From `backend`, with your virtual environment activated:

```bash
python -m app.diagnostics
python -m app.diagnostics --check-runtime
python -m app.diagnostics --url 'https://www.youtube.com/watch?v=j-2yfhRUQ64'
python -m app.diagnostics --url 'https://www.youtube.com/watch?v=j-2yfhRUQ64' --download
```

The last command downloads/processes a temporary five-second clip, then removes
it. Nothing runs against YouTube without `--url`. The report shows Python,
yt-dlp, EJS, Node and FFmpeg versions, and cookie-configured/parseable booleans
only. No cookie path/content is printed. `YTDLP_DIAGNOSTICS=1` additionally emits
this summary at application startup, so Render Shell is not required.

Server error categories distinguish bot detection, login requirements, rejected
cookies, rate limits, access denial, JavaScript challenges, network errors,
FFmpeg errors and unavailable videos. An extraction failure is not automatically
proof of an outdated version or blocked IP: the log reports evidence/categories,
not guesses. Runtime/package versions help compare with official releases.

On Render without Shell:
1. Deploy the updated commit with the variables above.
2. Check startup runtime diagnostics; no cookies is valid for public videos.
3. Analyze an authorized public video in the existing UI.
4. Download a short source and export a short clip. Check the delivered files,
   transcript and queue behavior. Logs alone are not end-to-end verification.
5. Set `YTDLP_DIAGNOSTICS=0` after collecting results.

**This change is not a verified Render fix until real metadata extraction and
video download both succeed from the deployed service.** If bot detection
continues with parseable cookies, replace expired cookies once, inspect the
sanitized failure category and stop repeated requests. Do not auto-rotate
accounts, proxies or tokens. A host/IP challenge can persist despite a current
yt-dlp and valid cookies; local operation can remain the fallback. Keep existing
URL validation and platform restrictions in place.

## Future architecture

Replace the in-memory job manager with a durable queue and worker when adding accounts or scale. Keep API request/response contracts stable. Replace LocalStorage and the file-delivery endpoint with an object store and signed URLs. Compose CaptionProvider with a future transcription provider while retaining the same transcript response. Add providers for other platforms only behind explicit URL validation and normalized metadata. Authentication, billing, history, and usage accounting can wrap the existing API without embedding video processing into Next.js.
