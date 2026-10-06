'use client';

import { useMemo, useState } from 'react';
import { editTime } from '@/lib/api';
import { ClipDraft, parseClips } from '@/lib/paste-clips';

export default function PasteClips({ duration, disabled, onAdd }: { duration: number; disabled: boolean; onAdd(clips: ClipDraft[]): void }) {
  const [text, setText] = useState('');
  const rows = useMemo(() => parseClips(text, duration), [text, duration]);
  const valid = rows.length > 0 && rows.every(row => row.clip);
  return <details className="paste-clips">
    <summary>Paste multiple clips</summary>
    <label className="field-label" htmlFor="paste-clips">NAME | IN - OUT — ONE CLIP PER LINE</label>
    <textarea id="paste-clips" rows={4} maxLength={25000} disabled={disabled} value={text} placeholder={'Hook | 00:12 - 00:38\nMain point | 02:15 - 03:05'} onChange={event => setText(event.target.value)}/>
    {rows.length > 0 && <ul aria-label="Clip import preview">{rows.map(row => <li key={row.line} className={row.error ? 'error' : ''}>
      {row.clip ? <><strong>{row.clip.name}</strong><span>{editTime(row.clip.start)} → {editTime(row.clip.end)} · LENGTH {editTime(row.clip.end - row.clip.start)}</span></> : <span>Line {row.line}: {row.error}</span>}
    </li>)}</ul>}
    {rows.some(row => row.error) && <p className="error" role="alert">Fix the marked lines before adding clips. Nothing has been added yet.</p>}
    <button className="seek-button" disabled={disabled || !valid} onClick={() => { if (!valid || disabled) return; onAdd(rows.map(row => row.clip!)); setText(''); }}>Add to Clips{valid ? ` (${rows.length})` : ''}</button>
  </details>;
}
