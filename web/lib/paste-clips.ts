import { parseRange } from './paste-range';

export type ClipDraft = { name: string; start: number; end: number };
export type ClipRow = { line: number; text: string; clip?: ClipDraft; error?: string };

export function parseClips(text: string, duration: number): ClipRow[] {
  const lines = text.split(/\r?\n/).map((text, index) => ({ text: text.trim(), line: index + 1 }))
    .filter(row => row.text && !/^```(?:\w+)?$/.test(row.text));
  if (lines.length > 100) return [{ line: 1, text: '', error: 'Paste up to 100 clips at a time.' }];
  return lines.map(row => {
    try {
      const clean = row.text.replace(/^(?:[-*•]\s+|\d+[.)]\s+)/, '');
      const parts = clean.split('|');
      if (parts.length !== 2) throw new Error('Use Name | IN - OUT, one clip per line.');
      const name = parts[0].trim().replace(/^\*\*(.*?)\*\*$/, '$1');
      if (!name || name.length > 120) throw new Error('Name must contain 1–120 characters.');
      return { ...row, clip: { name, ...parseRange(parts[1], duration) } };
    } catch (error) {
      return { ...row, error: error instanceof Error ? error.message : 'Invalid clip.' };
    }
  });
}
