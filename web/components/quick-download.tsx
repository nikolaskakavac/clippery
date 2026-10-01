'use client';

import { useState } from 'react';
import { API } from '@/lib/api';

type Source = { url: string; title: string; creator: string; thumbnail: string | null; duration: number | null };

export default function QuickDownload() {
  const [url, setUrl] = useState('');
  const [source, setSource] = useState<Source | null>(null);
  const [busy, setBusy] = useState<'fetch' | 'download' | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function request(action: 'info' | 'download') {
    if (busy) return;
    setBusy(action === 'info' ? 'fetch' : 'download'); setError(''); setNotice('');
    if (action === 'info') setSource(null);
    try {
      const response = await fetch(`${API}/api/quick-download/tiktok/${action}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: action === 'download' ? source?.url : url }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(typeof data?.detail === 'string' ? data.detail : 'TikTok download is unavailable. Try again later.');
      }
      if (action === 'info') setSource(await response.json());
      else {
        const blobUrl = URL.createObjectURL(await response.blob());
        const contentType = response.headers.get('content-type') || '';
        const extension = contentType.includes('webm') ? 'webm' : contentType.includes('matroska') ? 'mkv' : contentType.includes('quicktime') ? 'mov' : 'mp4';
        const link = document.createElement('a'); link.href = blobUrl; link.download = `clippery-tiktok.${extension}`; link.click();
        setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
        setNotice('Download ready. Best available source quality, without re-encoding.');
      }
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not connect. Try again.'); }
    finally { setBusy(null); }
  }

  return <section className="quick-download" aria-label="TikTok Quick Download">
    <div className="panel-heading"><h2>Quick Download</h2><span className="format-badge">TIKTOK</span></div>
    <form className="quick-download-form" onSubmit={event => { event.preventDefault(); void request('info'); }}>
      <label className="field-label" htmlFor="tiktok-url">PUBLIC TIKTOK VIDEO</label>
      <div><input id="tiktok-url" type="url" required placeholder="Paste a TikTok video URL" value={url} disabled={!!busy} onChange={event => { setUrl(event.target.value); setSource(null); setError(''); setNotice(''); }}/><button className="primary" disabled={!!busy || !url.trim()}>{busy === 'fetch' ? 'Fetching…' : 'Fetch'}</button></div>
    </form>
    {source && <div className="quick-download-source">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      {source.thumbnail && <img src={source.thumbnail} alt="TikTok video thumbnail" referrerPolicy="no-referrer"/>}
      <div><strong>{source.title}</strong><p>{source.creator}{source.duration != null && ` · ${Math.round(source.duration)}s`}</p><span className="preview-status">Best available quality · Original resolution</span></div>
      <button className="primary" disabled={!!busy} onClick={() => request('download')}>{busy === 'download' ? 'Downloading…' : 'DOWNLOAD VIDEO'}</button>
    </div>}
    {error && <p className="error" role="alert">{error}</p>}
    {notice && <p className="preview-status" role="status">{notice}</p>}
  </section>;
}
