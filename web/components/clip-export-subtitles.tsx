'use client';

import { useState } from 'react';
import { api, Job, Transcript } from '@/lib/api';
import { clipFilename, clipSrt } from '@/lib/clip-subtitles';

export default function ClipExportSubtitles({ job, url, transcript }: { job: Job; url: string; transcript: Transcript | null }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  if (!job.clipRange || job.state !== 'Ready') return null;
  async function download() {
    if (loading) return;
    setLoading(true); setError('');
    try {
      const source = transcript ?? await api<Transcript>('/transcript', { url });
      const text = clipSrt(source, job.clipRange!.start, job.clipRange!.end, job.silence?.segments);
      if (!text) throw new Error('No captions overlap the exported clip.');
      const blobUrl = URL.createObjectURL(new Blob([text], { type: 'application/x-subrip;charset=utf-8' }));
      const link = document.createElement('a'); link.href = blobUrl;
      link.download = `${clipFilename(job.filename || 'clip')}.srt`; link.click();
      setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not download subtitles.'); }
    finally { setLoading(false); }
  }
  return <div><button className="seek-button" disabled={loading} onClick={download}>{loading ? 'Loading SRT…' : 'Download SRT'}</button>{error && <p className="error" role="alert">{error}</p>}</div>;
}
