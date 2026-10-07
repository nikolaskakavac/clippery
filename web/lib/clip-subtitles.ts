import { timestamp, Transcript } from './api';

export function clipFilename(name: string): string {
  const clean = name.trim().replace(/[<>:"/\\|?*\x00-\x1f\x7f]/g, '_').replace(/^[ .]+|[ .]+$/g, '').replace(/\.mp4$/i, '').replace(/[ .]+$/g, '').slice(0, 120) || 'clip';
  return /^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$/i.test(clean) ? `_${clean}` : clean;
}

export function clipSrt(transcript: Transcript, start: number, end: number, kept?: { start: number; end: number }[]): string {
  if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end <= start) return '';
  const time = (ms: number) => `${timestamp(Math.floor(ms / 1000))},${String(ms % 1000).padStart(3, '0')}`;
  let offset = 0;
  return (kept ?? [{ start: 0, end: end - start }]).flatMap(range => {
    const lower = start + range.start, upper = Math.min(end, start + range.end);
    const cues = transcript.segments.flatMap(segment => {
      if (!Number.isFinite(segment.start) || !Number.isFinite(segment.end) || segment.end <= lower || segment.start >= upper) return [];
      const from = Math.round((offset + Math.max(0, segment.start - lower)) * 1000);
      const to = Math.round((offset + Math.min(upper - lower, segment.end - lower)) * 1000);
      const text = segment.text.trim().replace(/\r\n?/g, '\n').replace(/\n\s*\n/g, '\n');
      return to > from && text ? [{ from, to, text }] : [];
    });
    offset += range.end - range.start;
    return cues;
  }).sort((a, b) => a.from - b.from)
    .map((cue, index) => `${index + 1}\n${time(cue.from)} --> ${time(cue.to)}\n${cue.text}\n`)
    .join('\n');
}
