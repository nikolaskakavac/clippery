import { editTime, parseTime, Video } from './api';

export const SESSION_KEY = 'clippery:session:v1';
export type Session = {
  version: 1;
  url: string;
  video: Video | null;
  start: string;
  end: string;
  tab: 'download' | 'clip' | 'transcript';
  quality: string;
};

/** Treat browser storage as untrusted and restore only workspace data. */
export function parseSession(raw: string | null): Session | null {
  if (!raw) return null;
  try {
    const data = JSON.parse(raw);
    if (!data || data.version !== 1) return null;
    const saved = data.video;
    let video: Video | null = null;
    if (saved && typeof saved.id === 'string' && /^[\w-]{11}$/.test(saved.id) &&
        typeof saved.duration === 'number' && Number.isFinite(saved.duration) && saved.duration > 0 &&
        typeof saved.title === 'string' && typeof saved.channel === 'string') {
      video = {
        id: saved.id, title: saved.title.slice(0, 1000), channel: saved.channel.slice(0, 300),
        duration: saved.duration, durationFormatted: editTime(saved.duration), isShort: saved.isShort === true,
        thumbnail: `https://i.ytimg.com/vi/${saved.id}/hqdefault.jpg`,
        webpageUrl: `https://www.youtube.com/watch?v=${saved.id}`,
      };
    }
    const time = (value: unknown, fallback: number) => typeof value === 'string' && value.length <= 32 &&
      Number.isFinite(parseTime(value)) && parseTime(value) <= (video?.duration ?? 0) ? value : editTime(fallback);
    return {
      version: 1, video,
      url: typeof data.url === 'string' ? data.url.slice(0, 2048) : video?.webpageUrl ?? '',
      start: time(data.start, 0), end: time(data.end, Math.min(30, video?.duration ?? 30)),
      tab: video && ['download', 'clip', 'transcript'].includes(data.tab) ? data.tab : 'download',
      quality: ['best', '1080', '720'].includes(data.quality) ? data.quality : '1080',
    };
  } catch { return null; }
}
