'use client';

import { useEffect, useRef, useState } from 'react';
import { API, api, editTime, Job, Transcript, Video } from '@/lib/api';
import { clipFilename, clipSrt } from '@/lib/clip-subtitles';
import OutputDetails from '@/components/output-details';
import ExportPreview from '@/components/export-preview';
import PasteClips from '@/components/paste-clips';

type Clip = { id: string; name: string; start: number; end: number; removeSilence?: boolean };
type Result = { state: string; job?: Job; error?: string };
type Props = {
  video: Video; start: number; end: number; valid: boolean; busy: boolean; quality: string; removeSilence: boolean;
  transcript: Transcript | null;
  onBusy(value: boolean): void;
  onSelect(start: number, end: number, preview: boolean): void;
};

export default function ClipList({ video, start, end, valid, busy, quality, removeSilence, transcript, onBusy, onSelect }: Props) {
  const [clips, setClips] = useState<Clip[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [zipLoading, setZipLoading] = useState(false);
  const [includeSrt, setIncludeSrt] = useState(false);
  const zipRunning = useRef(false);
  const [loaded, setLoaded] = useState(false);
  const [notice, setNotice] = useState('');
  const [editing, setEditing] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, Result>>({});
  const running = useRef(false);
  const mounted = useRef(true);
  const stop = useRef(false);
  const captions = useRef<Transcript | null>(null);
  const captionRequest = useRef<AbortController | null>(null);
  const [srtLoading, setSrtLoading] = useState<string | null>(null);
  const storageKey = `clippery:clips:v1:${video.id}`;
  useEffect(() => {
    mounted.current = true;
    try {
      const saved: unknown = JSON.parse(localStorage.getItem(storageKey) || '[]');
      if (Array.isArray(saved)) setClips(saved.filter((item): item is Clip =>
        item && typeof item.id === 'string' && typeof item.name === 'string' &&
        Number.isFinite(item.start) && Number.isFinite(item.end) && item.start >= 0 &&
        item.end > item.start && item.end <= video.duration && item.end - item.start <= 300));
    } catch { setNotice('Local storage is unavailable. Keep this page open to retain your clips.'); }
    setLoaded(true);
    return () => { mounted.current = false; stop.current = true; captionRequest.current?.abort(); };
  }, [storageKey, video.duration]);
  useEffect(() => {
    if (!loaded) return;
    try { localStorage.setItem(storageKey, JSON.stringify(clips)); }
    catch { setNotice('Could not save clips locally. Keep this page open to retain them.'); }
  }, [clips, loaded, storageKey]);

  function saveRange() {
    if (!valid || busy || !loaded) return;
    if (editing) {
      setClips(items => items.map(item => item.id === editing ? { ...item, start, end } : item));
      setResults(items => { const next = { ...items }; delete next[editing]; return next; });
      setEditing(null);
    } else setClips(items => [...items, { id: crypto.randomUUID(), name: `Clip ${items.length + 1}`, start, end, removeSilence }]);
  }

  function duplicateClip(clip: Clip) {
    if (busy || !loaded) return;
    const duplicate = { ...clip, id: crypto.randomUUID(), name: `${(clip.name || 'Clip').slice(0, 113)} (copy)` };
    setClips(items => items.flatMap(item => item.id === clip.id ? [item, duplicate] : [item]));
  }

  const selectedClips = clips.filter(clip => selectedIds.has(clip.id));
  const selectionReady = selectedClips.length > 0 && selectedClips.every(clip => results[clip.id]?.state === 'Ready');
  const remaining = clips.filter(clip => !results[clip.id] || ['Failed', 'Not exported'].includes(results[clip.id].state));
  const saving = Object.values(results).some(result => result.state === 'Saving');

  async function exportClips(selected: Clip[]) {
    if (busy || running.current || !selected.length || video.duration > 10800 || selected.some(clip => results[clip.id]?.state === 'Saving')) return;
    running.current = true; stop.current = false; onBusy(true);
    setNotice('');
    const selectedIds = new Set(selected.map(clip => clip.id));
    setResults(items => ({ ...items, ...Object.fromEntries(selected.map(clip => [clip.id, { state: 'Queued' }])) }));
    try {
      for (const clip of selected) {
        if (stop.current || !mounted.current) break;
        let submitted = false;
        try {
          setResults(items => ({ ...items, [clip.id]: { state: 'Preparing' } }));
          let job = await api<Job>('/clip', { url: video.webpageUrl, quality, start: clip.start, end: clip.end, filename: clip.name, remove_silence: clip.removeSilence === true });
          submitted = true;
          while (mounted.current) {
            setResults(items => ({ ...items, [clip.id]: { state: job.state, job } }));
            if (job.state === 'Ready' || job.state === 'Failed') break;
            await new Promise(resolve => setTimeout(resolve, 1200));
            if (!mounted.current) break;
            job = await api<Job>(`/jobs/${job.id}`);
          }
          if (!mounted.current) break;
        } catch (error) {
          if (!mounted.current) break;
          setResults(items => ({ ...items, [clip.id]: { state: 'Failed', error: error instanceof Error ? error.message : 'Export failed.' } }));
          // A failed poll can leave a backend job running. Never submit another blindly.
          if (submitted) { stop.current = true; setNotice('Status check failed. Verify the current export has finished before retrying.'); }
        }
      }
    } finally {
      running.current = false;
      if (mounted.current) {
        setResults(items => Object.fromEntries(Object.entries(items).map(([id, result]) => [id, selectedIds.has(id) && result.state === 'Queued' ? { state: 'Not exported' } : result])));
        onBusy(false);
      }
    }
  }

  async function download(clip: Clip, job: Job) {
    setResults(items => ({ ...items, [clip.id]: { state: 'Saving', job } }));
    try {
      const response = await fetch(`${API}/api/video/jobs/${job.id}/file`);
      if (!response.ok) throw new Error('File unavailable or expired. Export this range again.');
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = url;
      link.download = `${clipFilename(clip.name)}.mp4`;
      link.click(); setTimeout(() => URL.revokeObjectURL(url), 60000);
      setResults(items => ({ ...items, [clip.id]: { state: 'Downloaded', job } }));
    } catch (error) {
      setResults(items => ({ ...items, [clip.id]: { state: 'Failed', error: error instanceof Error ? error.message : 'Download failed.' } }));
    }
  }

  const readyClips = clips.filter(clip => results[clip.id]?.state === 'Ready');

  async function downloadZip(requested: Clip[]) {
    if (busy || saving || zipRunning.current || !requested.length || requested.some(clip => results[clip.id]?.state !== 'Ready')) return;
    zipRunning.current = true; setZipLoading(true); onBusy(true); setNotice('');
    try {
      if (requested.length > 100) throw new Error('ZIP downloads support up to 100 ready clips at a time.');
      const source = includeSrt ? transcript ?? captions.current ?? await api<Transcript>('/transcript', { url: video.webpageUrl }) : null;
      if (source) captions.current = source;
      const response = await fetch(`${API}/api/video/archive`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ clips: requested.map(clip => ({ job_id: results[clip.id].job!.id, name: clipFilename(clip.name), srt: source ? clipSrt(source, clip.start, clip.end, results[clip.id].job?.silence?.segments) : null })) }),
      });
      if (!response.ok) throw new Error(response.status === 404 ? 'A clip has expired. Export it again before downloading the ZIP.' : 'Could not prepare the ZIP. Try again.');
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = url; link.download = `${clipFilename(video.title)}-clips.zip`;
      link.click(); setTimeout(() => URL.revokeObjectURL(url), 60000);
      if (mounted.current) setNotice(`ZIP downloaded with ${requested.length} clips.${source ? ' SRT files included where captions overlap.' : ''}`);
    } catch (error) {
      if (mounted.current) setNotice(error instanceof Error ? error.message : 'ZIP download failed. Try again.');
    } finally {
      zipRunning.current = false;
      if (mounted.current) { setZipLoading(false); onBusy(false); }
    }
  }

  async function downloadSrt(clip: Clip) {
    if (captionRequest.current) return;
    if (clip.removeSilence === true && !results[clip.id]?.job?.silence) {
      setNotice('Export this clip first so its subtitles can follow the silence cuts.'); return;
    }
    const controller = new AbortController();
    captionRequest.current = controller;
    setSrtLoading(clip.id); setNotice('');
    try {
      const source = transcript ?? captions.current ?? await api<Transcript>('/transcript', { url: video.webpageUrl }, controller.signal);
      if (controller.signal.aborted || !mounted.current) return;
      captions.current = source;
      const text = clipSrt(source, clip.start, clip.end, results[clip.id]?.job?.silence?.segments);
      if (!text) { setNotice(`No captions overlap “${clip.name || 'clip'}”.`); return; }
      const url = URL.createObjectURL(new Blob([text], { type: 'application/x-subrip;charset=utf-8' }));
      const link = document.createElement('a');
      link.href = url; link.download = `${clipFilename(clip.name)}.srt`;
      link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      if (!controller.signal.aborted && mounted.current) setNotice(error instanceof Error ? error.message : 'Could not download subtitles. Try again.');
    } finally {
      captionRequest.current = null;
      if (mounted.current) setSrtLoading(null);
    }
  }

  return <section className="clip-list" aria-label="Saved clips">
    <div className="clip-list-heading"><div><h2>Clips <span>{clips.length}</span></h2><p>Saved locally for this source. Export files expire; download them when ready.</p></div>
      <div className="preview-capture"><button disabled={!loaded || !valid || busy || (editing !== null && results[editing]?.state === 'Saving')} onClick={saveRange}>{editing ? 'Save Range' : 'Add Clip'}</button>{editing && <button disabled={busy} onClick={() => setEditing(null)}>Cancel Edit</button>}<button disabled={!clips.length || busy || saving || video.duration > 10800} onClick={() => exportClips(clips)}>Export All</button><button disabled={!remaining.length || busy || video.duration > 10800} onClick={() => exportClips(remaining)}>Export Remaining{remaining.length > 0 && ` (${remaining.length})`}</button><button disabled={busy || saving || zipLoading || !readyClips.length} onClick={() => downloadZip(readyClips)}>{zipLoading ? 'Preparing ZIP…' : `Download All ZIP (${readyClips.length})`}</button><label><input type="checkbox" checked={includeSrt} disabled={busy || zipLoading} onChange={event => setIncludeSrt(event.target.checked)}/> Include SRT</label>{running.current && <button onClick={() => { stop.current = true; setNotice('Queue will stop after the current clip finishes.'); }}>Stop Queue</button>}</div>
    </div>
    {clips.length > 0 && <div className="clip-selection">
      <span>{selectedClips.length} selected</span>
      <button className="seek-button" disabled={busy || saving || selectedClips.length === clips.length} onClick={() => setSelectedIds(new Set(clips.map(clip => clip.id)))}>Select All</button>
      <button className="seek-button" disabled={busy || saving || !selectedClips.length} onClick={() => setSelectedIds(new Set())}>Clear Selection</button>
      <button className="seek-button" disabled={busy || saving || !selectedClips.length || video.duration > 10800} onClick={() => exportClips(selectedClips)}>Export Selected</button>
      <button className="seek-button" disabled={busy || saving || zipLoading || !selectionReady || selectedClips.length > 100} onClick={() => downloadZip(selectedClips)}>Download Selected ZIP</button>
      {selectedClips.length > 0 && !selectionReady && <small>Export all selected clips before downloading their ZIP.</small>}
      {selectedClips.length > 100 && <small>Select up to 100 clips for one ZIP.</small>}
    </div>}
    <PasteClips duration={video.duration} disabled={busy || !loaded} onAdd={drafts => { const added = drafts.map(draft => ({ ...draft, id: crypto.randomUUID() })); setClips(items => [...items, ...added]); setNotice(`${added.length} clips added. Review or export them from the list.`); }}/>
    {notice && <p className="preview-status" role="status">{notice}</p>}
    {!clips.length && <p className="preview-status">Choose IN and OUT, then add your first clip.</p>}
    {clips.map(clip => <div className={`saved-clip ${editing === clip.id ? 'saved-clip-editing' : ''}`} key={clip.id}>
      <input className="clip-select" type="checkbox" aria-label={`Select ${clip.name || 'clip'} at ${editTime(clip.start)}`} checked={selectedIds.has(clip.id)} disabled={busy || saving} onChange={event => { const checked = event.target.checked; setSelectedIds(previous => { const next = new Set(previous); if (checked) next.add(clip.id); else next.delete(clip.id); return next; }); }}/>
      <input aria-label={`Name for ${editTime(clip.start)} clip`} maxLength={120} value={clip.name} disabled={busy} onChange={event => setClips(items => items.map(item => item.id === clip.id ? { ...item, name: event.target.value } : item))}/>
      <label className="silence-toggle"><input type="checkbox" checked={clip.removeSilence === true} disabled={busy || results[clip.id]?.state === 'Saving'} onChange={event => { const checked = event.target.checked; setClips(items => items.map(item => item.id === clip.id ? { ...item, removeSilence: checked } : item)); setResults(items => { const next = { ...items }; delete next[clip.id]; return next; }); }}/> Remove silence</label>
      <span className="saved-clip-time">{editTime(clip.start)} → {editTime(clip.end)}<small>LENGTH {editTime(clip.end - clip.start)}</small></span>
      <button className="seek-button" disabled={srtLoading !== null} onClick={() => downloadSrt(clip)}>{srtLoading === clip.id ? 'Loading SRT…' : 'Download SRT'}</button>
      <OutputDetails output={results[clip.id]?.job?.output} silence={results[clip.id]?.job?.silence}/>{results[clip.id]?.state === 'Ready' && <ExportPreview key={results[clip.id].job!.id} jobId={results[clip.id].job!.id}/>}
      <button className="seek-button" disabled={busy || results[clip.id]?.state === 'Saving' || video.duration > 10800} onClick={() => exportClips([clip])}>{results[clip.id]?.state === 'Failed' ? 'Retry' : 'Export Clip'}</button>
      <div className="preview-capture"><button onClick={() => onSelect(clip.start, clip.end, true)}>Preview</button><button disabled={busy} onClick={() => { setEditing(clip.id); onSelect(clip.start, clip.end, false); }}>Edit</button><button disabled={busy || !loaded} onClick={() => duplicateClip(clip)}>Duplicate</button><button disabled={busy || results[clip.id]?.state === 'Saving'} onClick={() => { setClips(items => items.filter(item => item.id !== clip.id)); setSelectedIds(previous => { const next = new Set(previous); next.delete(clip.id); return next; }); if (editing === clip.id) setEditing(null); }}>Remove</button></div>
      {results[clip.id] && <div className="saved-clip-result" role="status">{results[clip.id].state}{results[clip.id].job?.progress != null && !['Ready', 'Downloaded', 'Saving'].includes(results[clip.id].state) && ` · ${Math.round(results[clip.id].job!.progress!)}%`}{(results[clip.id].error || results[clip.id].job?.error) && <p className="error">{results[clip.id].error || results[clip.id].job?.error}</p>}{results[clip.id].state === 'Ready' && <button disabled={zipLoading} className="seek-button" onClick={() => download(clip, results[clip.id].job!)}>Download</button>}</div>}
    </div>)}
  </section>;
}
