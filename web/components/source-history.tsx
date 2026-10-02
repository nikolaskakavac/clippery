'use client';

import { useEffect, useRef, useState } from 'react';
import { Video } from '@/lib/api';
import { HISTORY_KEY, parseHistory, rememberSource } from '@/lib/source-history';

export default function SourceHistory({ video, disabled, onSelect }: {
  video: Video | null; disabled: boolean; onSelect(video: Video): void;
}) {
  const [items, setItems] = useState<Video[]>([]);
  const [notice, setNotice] = useState('');
  const current = useRef<Video[]>([]);
  useEffect(() => {
    try { current.current = parseHistory(localStorage.getItem(HISTORY_KEY)); setItems(current.current); }
    catch { setNotice('Source history is unavailable in this browser.'); }
  }, []);

  function save(next: Video[]) {
    current.current = next; setItems(next);
    try { localStorage.setItem(HISTORY_KEY, JSON.stringify(next)); }
    catch { setNotice('Could not save source history locally.'); }
  }

  useEffect(() => {
    if (video) save(rememberSource(current.current, video));
  }, [video]);

  if (!items.length && !notice) return null;
  return <details className="source-history">
    <summary>Recent sources <span>{items.length}</span></summary>
    <div className="history-heading"><span>Stored in this browser. Export files are not restored.</span><button className="seek-button" disabled={disabled || !items.length} onClick={() => save([])}>Clear history</button></div>
    {notice && <p className="preview-status" role="status">{notice}</p>}
    <ul>{items.map(item => <li key={item.id}>
      <button className="history-source" disabled={disabled} onClick={() => onSelect(item)}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={item.thumbnail} alt=""/><span><strong>{item.title}</strong><small>{item.channel} · {item.durationFormatted}</small></span>
      </button>
      <button className="seek-button" aria-label={`Remove ${item.title} from history`} disabled={disabled} onClick={() => save(current.current.filter(entry => entry.id !== item.id))}>Remove</button>
    </li>)}</ul>
  </details>;
}
