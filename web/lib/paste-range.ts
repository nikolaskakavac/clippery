export function parseRange(text: string, duration: number): { start: number; end: number } {
  const clean = text.trim().replace(/[*`\[\]]/g, '');
  const time = '(\\d{1,4}:\\d{2}(?::\\d{2})?(?:[.,]\\d{1,3})?)';
  const match = clean.match(new RegExp(`^(?:(?:IN|START|OD)\\s*:?\\s*)?${time}\\s*(?:-->|→|[-–—]|\\bto\\b|\\bdo\\b|(?:\\r?\\n)+)\\s*(?:(?:OUT|END)\\s*:?\\s*)?${time}$`, 'i'));
  if (!match) throw new Error('Paste one range, e.g. 02:15 - 02:48 or IN: 00:02:15 / OUT: 00:02:48 on separate lines.');
  function seconds(value: string) {
    const parts = value.replace(',', '.').split(':').map(Number);
    const last = parts[parts.length - 1];
    if (last >= 60 || (parts.length === 3 && parts[1] >= 60)) throw new Error('Minutes and seconds must be valid timecodes.');
    return parts.length === 3 ? parts[0] * 3600 + parts[1] * 60 + last : parts[0] * 60 + last;
  }
  const start = seconds(match[1]), end = seconds(match[2]);
  if (end <= start) throw new Error('OUT must be after IN.');
  if (end > duration) throw new Error('The range extends beyond this source.');
  if (end - start > 300) throw new Error('Clips can be at most 5 minutes.');
  return { start, end };
}
