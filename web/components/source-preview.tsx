'use client';

import { useEffect, useRef, useState } from 'react';
import { loadYouTubeAPI, YouTubePlayer } from '@/lib/youtube-player';

type Props = {
  videoId: string;
  active: boolean;
  duration: number;
  startSeconds: number;
  endSeconds: number;
  rangeValid: boolean;
  seekRequest: { seconds: number; preview?: boolean } | null;
  onSetIn(seconds: number): void;
  onSetOut(seconds: number): void;
  onAvailable(available: boolean): void;
};

export default function SourcePreview({ videoId, active, duration, startSeconds, endSeconds, rangeValid, seekRequest, onSetIn, onSetOut, onAvailable }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const player = useRef<YouTubePlayer | null>(null);
  const [enabled, setEnabled] = useState(active);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState('');
  const [previewing, setPreviewing] = useState(false);
  const [loop, setLoop] = useState(false);
  const loopRef = useRef(loop);
  useEffect(() => { loopRef.current = loop; }, [loop]);
  // Range edits and external seeks exit preview mode; IN/OUT remain owned by the form.
  useEffect(() => { setPreviewing(false); }, [startSeconds, endSeconds, active, ready, seekRequest]);
  useEffect(() => {
    if (!previewing || !active || !ready || !rangeValid || !player.current) return;
    const target = player.current;
    let awaitingSeek = true;
    target.seekTo(startSeconds, true);
    target.playVideo();
    const timer = window.setInterval(() => {
      const seconds = target.getCurrentTime();
      const state = target.getPlayerState();
      // seekTo is asynchronous: don't mistake the previous position for OUT.
      if (awaitingSeek) {
        if (seconds >= startSeconds && seconds < endSeconds && state === 1) awaitingSeek = false;
        else return;
      }
      if ((state === 1 && seconds >= endSeconds) || state === 0) {
        if (loopRef.current) {
          awaitingSeek = true;
          target.seekTo(startSeconds, true);
          target.playVideo();
        } else {
          target.pauseVideo();
          setPreviewing(false);
        }
      }
    }, 50);
    return () => { window.clearInterval(timer); target.pauseVideo(); };
  }, [previewing, active, ready, rangeValid, startSeconds, endSeconds]);
  const activeRef = useRef(active);
  // Keep callbacks and timecode changes out of the player's creation lifecycle.
  const callbacks = useRef({ onSetIn, onSetOut, onAvailable });
  useEffect(() => { callbacks.current = { onSetIn, onSetOut, onAvailable }; }, [onSetIn, onSetOut, onAvailable]);
  useEffect(() => {
    activeRef.current = active;
    if (active) setEnabled(true);
    else player.current?.pauseVideo?.();
  }, [active]);

  useEffect(() => {
    if (!enabled || !host.current) return;
    let disposed = false;
    let timeout: ReturnType<typeof setTimeout>;
    const mount = document.createElement('div');
    host.current.appendChild(mount);
    const unavailable = (message: string) => {
      if (disposed) return;
      clearTimeout(timeout);
      setError(message);
      setReady(false);
      callbacks.current.onAvailable(false);
    };
    loadYouTubeAPI().then(YT => {
      if (disposed) return;
      timeout = setTimeout(() => unavailable('YouTube preview did not respond. You can still enter IN and OUT manually.'), 20000);
      player.current = new YT.Player(mount, {
        videoId, width: '100%', height: '100%',
        playerVars: { autoplay: 0, playsinline: 1, origin: window.location.origin, rel: 0 },
        events: {
          onReady: ({ target }) => {
            if (disposed) return;
            clearTimeout(timeout);
            target.getIframe().title = 'YouTube source preview';
            if (!activeRef.current) target.pauseVideo();
            setError(''); setReady(true); callbacks.current.onAvailable(true);
          },
          onError: () => unavailable('This source cannot be previewed on YouTube here. You can still enter IN and OUT manually.'),
        },
      });
    }).catch(error => unavailable(error instanceof Error ? error.message : 'YouTube preview is unavailable.'));
    return () => {
      disposed = true;
      clearTimeout(timeout);
      player.current?.destroy();
      player.current = null;
      mount.remove();
      callbacks.current.onAvailable(false);
    };
  }, [enabled, videoId]);

  useEffect(() => {
    if (ready && seekRequest && Number.isFinite(seekRequest.seconds)) {
      player.current?.seekTo(Math.max(0, Math.min(duration, seekRequest.seconds)), true);
      if (seekRequest.preview) setPreviewing(true);
    }
  }, [seekRequest, ready, duration]);

  function capture(field: 'in' | 'out') {
    if (!ready) return;
    const seconds = player.current?.getCurrentTime();
    if (seconds === undefined || !Number.isFinite(seconds)) return;
    // Millisecond precision, floored to avoid a rounded .1000 timecode.
    const value = Math.floor(Math.max(0, Math.min(duration, seconds)) * 1000) / 1000;
    (field === 'in' ? callbacks.current.onSetIn : callbacks.current.onSetOut)(value);
  }
  useEffect(() => {
    if (!active || !ready) return;
    function keydown(event: KeyboardEvent) {
      const target = event.target;
      if (event.defaultPrevented || event.repeat || event.isComposing || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
      if (target instanceof HTMLElement && (target.isContentEditable || target.closest('input, textarea, select, [contenteditable], [role="textbox"]'))) return;
      const key = event.key.toLowerCase();
      if (key !== 'i' && key !== 'o') return;
      const seconds = player.current?.getCurrentTime();
      if (seconds === undefined || !Number.isFinite(seconds)) return;
      event.preventDefault();
      const value = Math.floor(Math.max(0, Math.min(duration, seconds)) * 1000) / 1000;
      (key === 'i' ? callbacks.current.onSetIn : callbacks.current.onSetOut)(value);
    }
    window.addEventListener('keydown', keydown);
    return () => window.removeEventListener('keydown', keydown);
  }, [active, ready, duration]);

  return <div className="source-preview">
    <div className="preview-frame"><div ref={host} className="preview-host" /></div>
    {!ready && !error && <p className="preview-status" role="status">Loading YouTube preview…</p>}
    {error && <p className="preview-status" role="status">{error} <a href={`https://www.youtube.com/watch?v=${videoId}`} target="_blank" rel="noreferrer">Open on YouTube</a></p>}
    <div className="preview-toolbar">
      <div className="preview-capture"><button disabled={!ready || !active || !rangeValid} onClick={() => setPreviewing(value => !value)}>{previewing ? 'Stop Preview' : 'Preview Clip'}</button><button aria-pressed={loop} onClick={() => setLoop(value => !value)}>Loop {loop ? 'on' : 'off'}</button></div>
    </div>
    <div className="preview-toolbar">
      <div className="preview-capture"><button disabled={!ready} onClick={() => capture('in')}>Set IN</button><button disabled={!ready} onClick={() => capture('out')}>Set OUT</button></div>
      <span className="preview-shortcuts" title="Shortcuts work while Clip is active, outside text fields and the YouTube iframe."><kbd>I</kbd> Set IN <kbd>O</kbd> Set OUT</span>
    </div>
  </div>;
}
