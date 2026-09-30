import { timestamp, Transcript } from './api';

export function clipFilename(name: string): string {
  return name.trim().replace(/[<>:"/\\|?*\x00-\x1f]/g, '_') || 'clip';
}

export function clipSrt(transcript: Transcript, start: number, end: number): string {
  if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end <= start) return '';
  const duration = Math.round((end - start) * 1000);
  const time = (ms: number) => `${timestamp(Math.floor(ms / 1000))},${String(ms % 1000).padStart(3, '0')}`;
  return transcript.segments.flatMap(segment => {
    if (!Number.isFinite(segment.start) || !Number.isFinite(segment.end) || segment.end <= start || segment.start >= end) return [];
    const from = Math.max(0, Math.round((segment.start - start) * 1000));
    const to = Math.min(duration, Math.round((segment.end - start) * 1000));
    const text = segment.text.trim().replace(/\r\n?/g, '\n').replace(/\n\s*\n/g, '\n');
    return to > from && text ? [{ from, to, text }] : [];
  }).sort((a, b) => a.from - b.from)
    .map((cue, index) => `${index + 1}\n${time(cue.from)} --> ${time(cue.to)}\n${cue.text}\n`)
    .join('\n');
}
