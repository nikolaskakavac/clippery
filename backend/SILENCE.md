# Clip silence removal

`ClipRequest.remove_silence` defaults to false. When enabled, the existing IN/OUT
pipeline first produces the bounded clip; only that file is analyzed and cut.
YouTube source selection, the five-minute limit and full downloads are unchanged.

FFmpeg detects audio below -35 dB for at least 0.6 seconds. Cuts retain at least
150 ms at both ends of a silent interval and are rounded outward to video frame
boundaries. Video and audio are trimmed together. A single additional H.264
CRF 16 / medium + AAC 192k encode joins the retained intervals without scaling.
The source's average frame rate is used for the constant-rate output. This is
an optional finishing pass; the existing precise IN/OUT path may already have
encoded the bounded source.

No audio, no qualifying silence, nearly all-silent audio or more than 80 retained
intervals leaves the clip unchanged, with an explanatory result message. Noise
or music can prevent detection; quiet speech can resemble silence. Preview the
result. This is volume-based detection, not speech recognition.

Jobs return `silence` with before/after durations and retained intervals relative
to the bounded clip. SRT exports intersect captions with these intervals and
shift them to the shortened timeline, including SRT files in ZIP downloads.
Original IN/OUT values remain unchanged. Toggle the option off and export again
to produce the original range. The bounded source and output share the existing
temporary-job cleanup lifecycle.

`DownloadRequest.filename` is optional and inherited by clip requests. Names are
sanitized for delivery only; disk paths remain generated internally. A single
`.mp4` extension is added, and direct SRT downloads use the same name stem.
