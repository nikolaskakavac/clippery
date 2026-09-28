export interface YouTubePlayer {
  getCurrentTime(): number;
  seekTo(seconds: number, allowSeekAhead: boolean): void;
  pauseVideo(): void;
  destroy(): void;
  getIframe(): HTMLIFrameElement;
}
interface PlayerOptions {
  videoId: string;
  width: string;
  height: string;
  playerVars: { autoplay: number; playsinline: number; origin: string; rel: number };
  events: {
    onReady(event: { target: YouTubePlayer }): void;
    onError(event: { data: number }): void;
  };
}
interface YouTubeAPI { Player: new (element: HTMLElement, options: PlayerOptions) => YouTubePlayer }
declare global {
  interface Window {
    YT?: YouTubeAPI;
    onYouTubeIframeAPIReady?: () => void;
  }
}
let loading: Promise<YouTubeAPI> | undefined;

/** Load YouTube's supported player API once, without a player dependency. */
export function loadYouTubeAPI(): Promise<YouTubeAPI> {
  if (window.YT?.Player) return Promise.resolve(window.YT);
  if (loading) return loading;
  loading = new Promise<YouTubeAPI>((resolve, reject) => {
    const script = document.createElement('script');
    const previous = window.onYouTubeIframeAPIReady;
    const restore = () => {
      clearTimeout(timeout);
      if (window.onYouTubeIframeAPIReady === ready) window.onYouTubeIframeAPIReady = previous;
    };
    const fail = () => { restore(); script.remove(); reject(new Error('YouTube preview could not load. Check your connection or content blocker.')); };
    const ready = () => {
      restore();
      if (window.YT?.Player) resolve(window.YT); else reject(new Error('YouTube preview is unavailable.'));
      previous?.();
    };
    const timeout = window.setTimeout(fail, 20000);
    window.onYouTubeIframeAPIReady = ready;
    script.src = 'https://www.youtube.com/iframe_api';
    script.async = true;
    script.onerror = fail;
    document.head.appendChild(script);
  }).catch(error => { loading = undefined; throw error; });
  return loading;
}
