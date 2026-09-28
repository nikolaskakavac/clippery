# Verification

Verified locally on Windows on 2026-09-28.

## Automated checks

- Frontend ESLint: passed.
- Frontend TypeScript (`tsc --noEmit`): passed.
- Next.js production build: passed.
- Backend pytest: **61 passed**. One upstream Starlette warning deprecates its current httpx TestClient integration; it does not affect the app or test results.
- Backend test coverage includes URL/host validation, time and clip limits, clean API responses, normalized metadata, caption preference, concurrency, cleanup, expiration, and bounded section re-encoding fallback.

The Windows sandbox prevented Node build-file writes and normal network installation. These checks were rerun with authorized access. A system pytest temp directory also had conflicting Windows permissions; tests passed using an isolated workspace `--basetemp` directory.

## Live checks

Using the public 19-second YouTube video `jNQXAC9IVRw`:

- Metadata returned title, channel, duration, and thumbnail without raw extractor fields.
- Existing English creator captions loaded successfully.
- Browser search filtered to the matching transcript sentence.
- Selecting three consecutive lines transferred 00:00:01.200 to 00:00:12.616 into Clip.
- Full download returned a playable H.264/AAC MP4 at the original 320x240 resolution (no upscaling), with a measured duration of 19.064 seconds.
- A 00:00:05–00:00:10 request initially exposed a stream-copy keyframe issue. The implementation was corrected to probe the result and retry only that section with re-encoding. The corrected MP4 measured **5.039 seconds**, with H.264 video and AAC audio.
- File delivery returned the MP4 bytes and the job subsequently returned 404, confirming cleanup.
- The interface was inspected in the browser at narrow and desktop widths.

The old yt-dlp test video `BaW_jenozKc` was unavailable. The app returned a clean error; live verification continued using the accessible public video above.

## Limits of verification

- No Vercel or Render deployment was performed. Hosting-provider access to YouTube and production resource capacity must be checked after deployment.
- Multi-hour source processing, a maximum-length full download, and a five-minute output were not downloaded during verification; their boundary rules are covered by unit tests.
- Shorts/watch/youtu.be normalization is covered by tests. A distinct live Shorts source was not used for the media test.
- No attempt was made to bypass private, age/login-restricted, or otherwise inaccessible content.
- Browser clipboard/TXT/SRT file saving was implemented but was not manually checked against an external editor.

- The Docker image itself was not built locally; the running backend used the same locked Python environment and a local FFmpeg binary. Test MP4 copies were removed after verification.
