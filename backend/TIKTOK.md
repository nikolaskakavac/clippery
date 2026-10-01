# TikTok Quick Download

Independent utility: POST `/api/quick-download/tiktok/info` and
POST `/api/quick-download/tiktok/download`, both accepting `{ "url": "..." }`.
Supports public video URLs and vm/vt/t share links. Profiles, photos, playlists,
non-TikTok URLs and off-domain share redirects are rejected.

Uses the installed yt-dlp TikTok extractor with independent options. Selects
`bv*+ba/b`, prioritizing resolution, frame rate and bitrate without a resolution
cap. No scaling or re-encoding; separate streams are merged when needed.
The original container is retained (MP4, WebM, MKV or MOV).

Metadata is optional where the extractor can still provide playable video.
Downloads use isolated temporary directories, removed after delivery or errors.
One TikTok download can be prepared at a time, independently of YouTube jobs.
No accounts, cookies, proxies, history, or persistence are added.

TikTok can block server IPs or require browser impersonation capabilities not
installed in the existing environment. Such failures retain detailed server
logs and return a concise safe error. The live smoke test in the implementation
environment received an IP-blocked response; successful live delivery was not
verified. Automated tests cover selection, delivery, cleanup and error handling.
