'use client';

import { useState } from 'react';
import { API } from '@/lib/api';

export default function ExportPreview({ jobId }: { jobId: string }) {
  const [open, setOpen] = useState(false);
  const [failed, setFailed] = useState(false);
  return <div className="export-preview">
    <button className="seek-button" aria-expanded={open} onClick={() => { setOpen(!open); setFailed(false); }}>{open ? 'Close preview' : 'Preview export'}</button>
    {open && <div>
      <video controls playsInline preload="metadata" aria-label="Exported clip preview" src={`${API}/api/video/jobs/${jobId}/file?preview=true`} onError={() => setFailed(true)}/>
      {failed && <p className="error" role="alert">Preview unavailable. The file may have expired or playback may not be supported. Try downloading it, or export again.</p>}
    </div>}
  </div>;
}
