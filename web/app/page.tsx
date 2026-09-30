'use client';
import Link from 'next/link';
import Image from 'next/image';
import SourcePreview from '@/components/source-preview';
import ClipList from '@/components/clip-list';
import OutputDetails from '@/components/output-details';
import ExportPreview from '@/components/export-preview';
import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react';
import { parseSession, SESSION_KEY } from '@/lib/session';
import { ArrowDownToLine, ArrowRight, Check, ChevronLeft, ChevronRight, Clock3, Copy, FileText, Film, Link2, Loader2, Scissors, Search, Youtube } from 'lucide-react';
import { API, api, ApiError, editTime, exportTranscript, Job, parseTime, Transcript, Video } from '@/lib/api';
type Tab = 'download' | 'clip' | 'transcript';
const tabs = [{ id: 'download' as Tab, label: 'Download', icon: ArrowDownToLine }, { id: 'clip' as Tab, label: 'Clip', icon: Scissors }, { id: 'transcript' as Tab, label: 'Transcript', icon: FileText }];
function message(e: unknown) { return e instanceof Error ? e.message : 'Could not connect to the API. Check that the backend is running.'; }
function Highlight({ text, query }: { text: string; query: string }) {
  if (!query) return <>{text}</>;
  const parts: React.ReactNode[] = []; let cursor = 0; let found = text.toLowerCase().indexOf(query.toLowerCase());
  while (found >= 0) { parts.push(text.slice(cursor, found), <mark key={found}>{text.slice(found, found + query.length)}</mark>); cursor = found + query.length; found = text.toLowerCase().indexOf(query.toLowerCase(), cursor); }
  parts.push(text.slice(cursor)); return <>{parts}</>;
}
export default function Home() {
  const [sessionReady, setSessionReady] = useState(false);
  const [sessionNotice, setSessionNotice] = useState('');
  const [url, setUrl] = useState(''); const [video, setVideo] = useState<Video | null>(null); const [tab, setTab] = useState<Tab>('download');
  const [analyzing, setAnalyzing] = useState(false); const [error, setError] = useState(''); const [quality, setQuality] = useState('1080');
  const [previewSeek, setPreviewSeek] = useState<{ seconds: number; preview?: boolean } | null>(null);
  const [batchBusy, setBatchBusy] = useState(false);
  const [previewReady, setPreviewReady] = useState(false);
  const [start, setStart] = useState('00:00:00'); const [end, setEnd] = useState('00:00:30');
  const [transcript, setTranscript] = useState<Transcript | null>(null); const [transcriptLoading, setTranscriptLoading] = useState(false); const [transcriptError, setTranscriptError] = useState('');
  const [query, setQuery] = useState(''); const deferredQuery = useDeferredValue(query.trim()); const [page, setPage] = useState(0);
  const [selection, setSelection] = useState<[number, number] | null>(null); const [copied, setCopied] = useState(false);
  const [job, setJob] = useState<Job | null>(null); const [jobKind, setJobKind] = useState<Tab>('download'); const [submitting, setSubmitting] = useState(false); const [pollError, setPollError] = useState('');
  const generation = useRef(0); const captionController = useRef<AbortController | null>(null);
  const processing = batchBusy || submitting || !!(job && !['Ready', 'Failed'].includes(job.state));
  const startSeconds = parseTime(start), endSeconds = parseTime(end), length = endSeconds - startSeconds;
  const clipError = !Number.isFinite(length) ? 'Enter timestamps as HH:MM:SS.' : startSeconds < 0 || length <= 0 ? 'OUT must be after IN.' : video && endSeconds > video.duration ? 'OUT must be within the source.' : length > 300 ? 'Clips can be at most 5 minutes.' : video && video.duration > 10800 ? 'Clip sources can be at most 3 hours.' : '';
  const matches = useMemo(() => transcript?.segments.map((s, index) => ({ ...s, index })).filter(s => s.text.toLowerCase().includes(deferredQuery.toLowerCase())) || [], [transcript, deferredQuery]);
  const totalPages = Math.max(1, Math.ceil(matches.length / 80)); const currentPage = Math.min(page, totalPages - 1);
  useEffect(() => {
    try {
      const saved = parseSession(localStorage.getItem(SESSION_KEY));
      if (saved) {
        setUrl(saved.url); setVideo(saved.video); setStart(saved.start); setEnd(saved.end);
        setTab(saved.tab); setQuality(saved.quality);
      }
    } catch { setSessionNotice('Session storage is unavailable. Keep this page open to retain your workspace.'); }
    setSessionReady(true);
  }, []);
  useEffect(() => {
    // Do not overwrite a saved session with the initial empty render.
    if (!sessionReady) return;
    try {
      localStorage.setItem(SESSION_KEY, JSON.stringify({ version: 1, url, video, start, end, tab, quality }));
    } catch { setSessionNotice('Could not save this session locally. Keep this page open to retain your workspace.'); }
  }, [sessionReady, url, video, start, end, tab, quality]);
  useEffect(() => {
    if (!job || ['Ready', 'Failed'].includes(job.state)) return;
    const controller = new AbortController(); let timer: ReturnType<typeof setTimeout>;
    const poll = async () => { try { const updated = await api<Job>(`/jobs/${job.id}`, undefined, controller.signal); setJob(updated); setPollError(''); if (!['Ready', 'Failed'].includes(updated.state)) timer = setTimeout(poll, 1200); } catch (e) { if (!controller.signal.aborted) { if (e instanceof ApiError && e.status === 404) { setJob({ ...job, state: 'Failed', error: e.message }); } else { setPollError(message(e)); timer = setTimeout(poll, 4000); } } } };
    timer = setTimeout(poll, 1000); return () => { controller.abort(); clearTimeout(timer); };
  }, [job]);
  async function analyze(e: React.FormEvent) {
    e.preventDefault(); const current = ++generation.current; captionController.current?.abort(); setTranscriptLoading(false); setAnalyzing(true); setError('');
    try { const result = await api<Video>('/info', { url }); if (current !== generation.current) return; setVideo(result); setPreviewSeek(null); setTranscript(null); setTranscriptError(''); setTranscriptLoading(false); setSelection(null); setQuery(''); setPage(0); setJob(null); setPollError(''); setStart('00:00:00'); setEnd(editTime(Math.min(30, result.duration))); setTab('download'); }
    catch (e) { setError(message(e)); } finally { setAnalyzing(false); }
  }
  const loadTranscript = useCallback(async () => {
    if (!video || transcriptLoading) return; const current = generation.current; const controller = new AbortController(); captionController.current = controller;
    setTranscriptLoading(true); setTranscriptError('');
    try { const result = await api<Transcript>('/transcript', { url: video.webpageUrl }, controller.signal); if (current === generation.current) setTranscript(result); }
    catch (e) { if (!controller.signal.aborted && current === generation.current) setTranscriptError(message(e)); }
    finally { if (current === generation.current) setTranscriptLoading(false); }
  }, [video, transcriptLoading]);
  useEffect(() => {
    if (sessionReady && !analyzing && tab === 'transcript' && video && !transcript && !transcriptLoading && !transcriptError) void loadTranscript();
  }, [sessionReady, analyzing, tab, video, transcript, transcriptLoading, transcriptError, loadTranscript]);
  function changeTab(next: Tab) { setTab(next); }
  async function createJob(kind: 'download' | 'clip') {
    if (!video) return; setSubmitting(true); setError(''); setJobKind(kind);
    try { setJob(await api<Job>(`/${kind}`, { url: video.webpageUrl, quality, ...(kind === 'clip' ? { start: startSeconds, end: endSeconds } : {}) })); }
    catch (e) { setError(message(e)); } finally { setSubmitting(false); }
  }
  function selectSegment(index: number) { setSelection(old => old ? [old[0], index] : [index, index]); }
  const firstSelected = selection ? Math.min(...selection) : -1, lastSelected = selection ? Math.max(...selection) : -1;
  function clipSelection() { if (!transcript || !selection) return; setStart(editTime(transcript.segments[firstSelected].start)); setEnd(editTime(transcript.segments[lastSelected].end)); setPreviewSeek({ seconds: transcript.segments[firstSelected].start }); setTab('clip'); }
  function adjust(field: 'start' | 'end', delta: number) { const current = parseTime(field === 'start' ? start : end); const value = editTime(Math.max(0, Math.min(video?.duration || 0, (Number.isFinite(current) ? current : 0) + delta))); (field === 'start' ? setStart : setEnd)(value); }
  return <div className="app-shell">
    <header className="topbar"><Link href="/" className="brand"><span className="brand-symbol"><Image src="/branding/clippery-logo.png" alt="" width={1034} height={621} priority /></span>Clippery<span className="version">BETA</span></Link><span className="header-note">Short-form editing utilities.</span></header>
    <main>
      {sessionNotice && <p className="preview-status" role="status">{sessionNotice}</p>}
      <div className="intro"><h1>From source to edit in seconds.</h1><p>Download footage, cut exact segments and pull timestamped transcripts — built for short-form editors and creators.</p></div>
      <label className="field-label source-label" htmlFor="source-url">SOURCE</label><form className="url-form" onSubmit={analyze}><Link2 size={20}/><input id="source-url" aria-label="YouTube video URL" type="url" required value={url} onChange={e => setUrl(e.target.value)} placeholder="Paste a YouTube or Shorts URL" disabled={analyzing || processing}/><button className="primary" disabled={analyzing || processing || !url.trim()}>{analyzing ? <><Loader2 className="spin" size={17}/>Analyzing</> : 'Analyze'}{!analyzing && <ArrowRight size={17}/>}</button></form>
      <div className="input-caption"><Youtube size={15}/><span>YouTube videos & Shorts</span></div>
      {error && <div className="error" role="alert">{error}</div>}
      {analyzing ? <div className="video-card skeleton" aria-label="Analyzing video"><div/><section><i/><i/><i/></section></div> : video ? <section className="video-card">
        {/* YouTube thumbnails are fixed to a trusted host by the backend. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <div className="thumbnail"><img src={video.thumbnail} alt="Video thumbnail"/><span>{video.durationFormatted}</span></div><div className="video-details"><div className="source"><Youtube size={15}/>YOUTUBE{video.isShort && <span>SHORT</span>}</div><h2>{video.title}</h2><p>{video.channel}<span>·</span><Clock3 size={14}/>{video.durationFormatted}</p><a href={video.webpageUrl} target="_blank" rel="noreferrer">Open original <ArrowRight size={13}/></a></div><span className="loaded"><Check size={13}/>Source loaded</span>
      </section> : <section className="empty-video"><div className="empty-icon"><Film size={28}/></div><div><h2>No source loaded</h2><p>Add a YouTube video or Short to start editing.</p></div></section>}
      <section className={`workspace ${!video ? 'inactive' : ''}`}><div className="tabs" role="tablist" aria-label="Video tools">{tabs.map(({ id, label, icon: Icon }) => <button key={id} id={`tab-${id}`} role="tab" aria-selected={tab === id} aria-controls={`panel-${id}`} onClick={() => changeTab(id)} disabled={!video || analyzing}><Icon size={17}/>{label}</button>)}<span className="workspace-label">{video ? 'SOURCE LOADED' : 'NO SOURCE'}</span></div>
      <div className="panel" role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
      {tab === 'download' && <><div className="panel-heading"><div><h2>Download source</h2></div><span className="format-badge">MP4</span></div><div className="field-label" id="quality-label">QUALITY</div><div className="quality-options" role="group" aria-labelledby="quality-label">{[{ value: 'best', title: 'Best', detail: 'Up to 1080p' }, { value: '1080', title: '1080p', detail: 'Full HD' }, { value: '720', title: '720p', detail: 'HD' }].map(q => <button key={q.value} aria-pressed={quality === q.value} className={quality === q.value ? 'quality selected' : 'quality'} disabled={!video || processing} onClick={() => setQuality(q.value)}><span className="radio">{quality === q.value && <span/>}</span><strong>{q.title}</strong><small>{q.detail}</small></button>)}</div><div className="action-row"><p>H.264 / AAC<span>·</span>No upscaling</p><button className="primary" disabled={!video || processing || video.duration > 3600} onClick={() => createJob('download')}><ArrowDownToLine size={17}/>DOWNLOAD VIDEO</button></div>{video && video.duration > 3600 && <p className="error">Full downloads are limited to 60 minutes. Open Clip to extract a shorter moment.</p>}</>}
      {video && <div hidden={tab !== 'clip'} className="clip-workspace"><div className="panel-heading"><div><h2>Clip range</h2><p>Set IN and OUT points. Maximum length 05:00.</p></div><span className="format-badge">MP4</span></div><div className="clip-editor"><SourcePreview key={video.id} videoId={video.id} duration={video.duration} startSeconds={startSeconds} endSeconds={endSeconds} rangeValid={!clipError} active={tab === 'clip'} seekRequest={previewSeek} onSetIn={seconds => setStart(editTime(seconds))} onSetOut={seconds => setEnd(editTime(seconds))} onAvailable={setPreviewReady} /><div className="clip-controls"><div className="time-grid">{(['start', 'end'] as const).map(field => <div className="time-field" key={field}><label className="field-label" htmlFor={field}>{field === 'start' ? 'IN' : 'OUT'}</label><div className="timecode-seek"><input id={field} value={field === 'start' ? start : end} onChange={e => (field === 'start' ? setStart : setEnd)(e.target.value)} spellCheck={false}/><button className="seek-button" aria-label={`Go to ${field === 'start' ? 'IN' : 'OUT'} point`} disabled={!previewReady || !Number.isFinite(field === 'start' ? startSeconds : endSeconds) || (field === 'start' ? startSeconds : endSeconds) > video.duration} onClick={() => setPreviewSeek({ seconds: field === 'start' ? startSeconds : endSeconds })}>Go</button></div><div className="nudges">{[-5, -1, 1, 5].map(delta => <button key={delta} onClick={() => adjust(field, delta)}>{delta > 0 ? '+' : ''}{delta}s</button>)}</div></div>)}</div><div className="clip-summary"><Scissors size={16}/><span>LENGTH</span><strong>{Number.isFinite(length) && length > 0 ? editTime(length) : '—'}</strong></div>{clipError && <p className="error" role="alert">{clipError}</p>}<div className="action-row"><p>MP4 export<span>·</span>Up to 1080p</p><button className="primary" disabled={!video || processing || !!clipError} onClick={() => createJob('clip')}><Scissors size={17}/>CREATE CLIP</button></div></div></div><ClipList key={video.id} transcript={transcript} video={video} start={startSeconds} end={endSeconds} valid={!clipError} busy={processing} quality={quality} onBusy={setBatchBusy} onSelect={(clipStart, clipEnd, preview) => { setStart(editTime(clipStart)); setEnd(editTime(clipEnd)); setPreviewSeek({ seconds: clipStart, preview }); }} /></div>}
      {tab === 'transcript' && <><div className="panel-heading"><div><h2>Transcript</h2><p>{transcript ? `${transcript.language.toUpperCase()} · ${transcript.isAutoGenerated ? 'Automatic captions' : 'Creator subtitles'}` : 'Timestamped source captions'}</p></div>{transcript && <div className="export-actions"><button title="Copy transcript" onClick={async () => { try { await navigator.clipboard.writeText(transcript.segments.map(s => s.text).join('\n')); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch { setTranscriptError('Clipboard access is unavailable. Export TXT instead.'); } }}><Copy size={15}/>{copied ? 'Copied' : 'Copy'}</button><button onClick={() => exportTranscript(transcript, 'txt')}>Export TXT</button><button onClick={() => exportTranscript(transcript, 'srt')}>Export SRT</button></div>}</div>
      {transcriptLoading && <div className="transcript-empty"><Loader2 className="spin"/>Loading captions…</div>}{transcriptError && <div className="error" role="alert">{transcriptError}<button className="text-button" onClick={loadTranscript}>Try again</button></div>}
      {transcript && <><div className="search-box"><Search size={18}/><input aria-label="Search transcript" placeholder="Search transcript…" value={query} onChange={e => { setQuery(e.target.value); setPage(0); }}/><span>{matches.length} lines</span></div><div className="selection-hint"><span>{selection && transcript ? <><strong>{lastSelected - firstSelected + 1} lines selected</strong><span className="selection-range">{editTime(transcript.segments[firstSelected].start)} — {editTime(transcript.segments[lastSelected].end)}</span><span className="selection-destination">Ready for Clip</span></> : 'Select the first and last line of a clip range.'}</span>{selection && <button onClick={() => setSelection(null)}>Clear selection</button>}</div><div className="segments">{matches.slice(currentPage * 80, currentPage * 80 + 80).map(s => <div key={s.index} className={`segment ${s.index >= firstSelected && s.index <= lastSelected ? 'segment-selected' : ''}`}><input type="checkbox" aria-label={`Select segment at ${s.startFormatted}`} checked={s.index >= firstSelected && s.index <= lastSelected} onChange={() => selectSegment(s.index)}/><button className="timestamp" title="Set Clip IN point" onClick={() => { setStart(editTime(s.start)); setEnd(editTime(Math.min(video!.duration, s.start + 30))); setPreviewSeek({ seconds: s.start }); setTab('clip'); }}>{s.startFormatted}</button><button className="segment-text" onClick={() => selectSegment(s.index)}><Highlight text={s.text} query={deferredQuery}/></button></div>)}{matches.length === 0 && <div className="transcript-empty">No matching lines. Try a different phrase.</div>}</div><div className="transcript-footer"><div className="pagination"><button aria-label="Previous transcript page" disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}><ChevronLeft size={16}/></button><span>{currentPage + 1} / {totalPages}</span><button aria-label="Next transcript page" disabled={currentPage >= totalPages - 1} onClick={() => setPage(currentPage + 1)}><ChevronRight size={16}/></button></div><button className="primary" disabled={!selection} onClick={clipSelection}><Scissors size={16}/>CREATE CLIP FROM SELECTION{selection && <span className="count">{lastSelected - firstSelected + 1}</span>}</button></div></>}
      </>}
      {job && <div className={`job job-${job.state.toLowerCase()}`} aria-live="polite"><div className="job-heading"><strong>{jobKind === 'clip' ? 'Clip' : 'Download'} · {job.state}</strong><span>{job.progress === null ? 'Working…' : `${Math.round(job.progress)}%`}</span></div><progress aria-label="Processing progress" max={100} value={job.progress ?? undefined}/>{job.error && <p className="error">{job.error}</p>}{pollError && <p className="error">{pollError} Retrying status…</p>}<OutputDetails output={job.output}/>{jobKind === 'clip' && job.state === 'Ready' && <ExportPreview key={job.id} jobId={job.id}/>}{job.state === 'Ready' && <div className="ready-row"><span>Export ready. Download before the file expires.</span><a className="primary" href={`${API}/api/video/jobs/${job.id}/file`}><ArrowDownToLine size={16}/>{jobKind === 'clip' ? 'Download clip' : 'Download file'}</a></div>}</div>}
      </div></section><footer><span>Short-form editing workspace</span><span>MP4 output <span> / </span> Up to 1080p <span> / </span> 5-minute clips</span></footer>
    </main></div>;
}



