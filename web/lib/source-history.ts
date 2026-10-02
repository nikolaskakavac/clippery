import { Video } from './api';
import { parseSession } from './session';

export const HISTORY_KEY = 'clippery:sources:v1';

export function parseHistory(raw: string | null): Video[] {
  try {
    const items: unknown = JSON.parse(raw || '[]');
    if (!Array.isArray(items)) return [];
    const seen = new Set<string>();
    return items.flatMap(item => {
      const video = parseSession(JSON.stringify({ version: 1, video: item }))?.video;
      if (!video || seen.has(video.id)) return [];
      seen.add(video.id);
      return [video];
    }).slice(0, 20);
  } catch { return []; }
}

export function rememberSource(items: Video[], video: Video): Video[] {
  return [video, ...items.filter(item => item.id !== video.id)].slice(0, 20);
}
