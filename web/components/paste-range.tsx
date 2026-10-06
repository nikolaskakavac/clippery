'use client';

import { useState } from 'react';
import { parseRange } from '@/lib/paste-range';

export default function PasteRange({ duration, disabled, onApply }: { duration: number; disabled: boolean; onApply(start: number, end: number): void }) {
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  const [applied, setApplied] = useState(false);
  function apply(value: string) {
    if (disabled) return;
    setError(''); setApplied(false);
    try { const range = parseRange(value, duration); onApply(range.start, range.end); setApplied(true); }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Invalid range.'); }
  }
  return <div className="paste-range">
    <label className="field-label" htmlFor="paste-range">PASTE RANGE</label>
    <div><textarea id="paste-range" rows={2} maxLength={500} placeholder="02:15 - 02:48" disabled={disabled} value={text} onChange={event => { setText(event.target.value); setError(''); setApplied(false); }} onPaste={event => { event.preventDefault(); const value = event.clipboardData.getData('text').slice(0, 500); setText(value); apply(value); }}/><button className="seek-button" disabled={disabled || !text.trim()} onClick={() => apply(text)}>Set IN/OUT</button></div>
    {error && <p className="error" role="alert">{error}</p>}
    {applied && <p className="preview-status" role="status">IN/OUT updated. Review the range before creating your clip.</p>}
  </div>;
}
