'use client';

import { useState } from 'react';
import { API } from '@/lib/api';

export default function ExportPreview({ jobId, hasOriginal = false }: { jobId: string; hasOriginal?: boolean }) {
  const [open, setOpen] = useState(false);
  const [failed, setFailed] = useState(false);
  const [original, setOriginal] = useState(false);
  return <div className="export-preview">
    <button className="seek-button" aria-expanded={open} onClick={() => { setOpen(!open); setFailed(false); }}>{open ? 'Close preview' : 'Preview export'}</button>
    {open && <div>
      {hasOriginal && <div className="preview-capture" role="group" aria-label="Compare silence removal">
        <button aria-pressed={original} onClick={() => { setOriginal(true); setFailed(false); }}>Original</button>
        <button aria-pressed={!original} onClick={() => { setOriginal(false); setFailed(false); }}>Silence removed</button>
      </div>}
      <video key={`${jobId}-${original}`} controls playsInline preload="metadata" aria-label={original ? 'Original clip preview' : 'Exported clip preview'} src={`${API}/api/video/jobs/${jobId}/file?preview=true${original ? '&original=true' : ''}`} onError={() => setFailed(true)}/>
      {hasOriginal && <p className="preview-status">{original ? 'Original IN/OUT clip' : 'Silence removed'} · Switching starts from the beginning. Download uses the silence-removed version.</p>}
      {failed && <p className="error" role="alert">Preview unavailable. The file may have expired or playback may not be supported. Try downloading it, or export again.</p>}
    </div>}
  </div>;
}
