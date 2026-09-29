# YouTube PO-token script provider

`../build.sh` fetches the official bgutil 2.0.0 source at commit
`37169ee2656e08c5c2e5dc9df4c598c0cb4c88a8` into
`bgutil-ytdlp-pot-provider/`, installs its locked npm dependencies and builds
`server/build/generate_once.js`. The checkout, dependencies and build output are
ignored by Git, but must remain in the deployed build artifact.

Python plugin: `bgutil-ytdlp-pot-provider==2.0.0`.
yt-dlp: `2026.8.19` (existing installed version, now pinned).
No provider code is modified. Upstream source and license remain in the checkout.

## Native Python Render service

- Root Directory: `backend`
- Build Command: `bash build.sh`
- Environment: `NODE_VERSION=22.22.3`
- Start Command (unchanged): `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Render supplies Node/npm in native Python builds and at runtime. Node 22+ must
remain on PATH: the plugin invokes the generator on demand during extraction.
No additional service, port, credentials or provider environment variables are
needed. The upstream plugin may probe its default localhost HTTP provider before
falling back to the configured script; this setup starts no HTTP token server.

The shared yt-dlp options select `mweb` and an absolute `server_home`, so every
extraction path uses the same configuration. Warnings and underlying extraction
errors stay in server logs; public error messages remain unchanged.

PO tokens do not guarantee access from a blocked Render IP or resolve every
YouTube LOGIN_REQUIRED response. On-demand generation also adds latency.

Official references:
- https://github.com/Brainicism/bgutil-ytdlp-pot-provider/tree/2.0.0#script
- https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide
- https://render.com/docs/native-runtimes
- https://render.com/docs/node-version
