import { OutputMetadata, SilenceResult } from '@/lib/api';

export default function OutputDetails({ output, silence }: { output?: OutputMetadata | null; silence?: SilenceResult | null }) {
  if (!output && !silence) return null;
  const parts = [
    output?.width && output.height ? `${output.width}×${output.height}` : null,
    output?.fps && Number.isFinite(output.fps) ? `${output.fps} fps` : null,
    output?.codec === 'h264' ? 'H.264' : output?.codec?.toUpperCase(),
    output && Number.isFinite(output.sizeBytes) ? `${(output.sizeBytes / 1_000_000).toLocaleString('en-US', { maximumFractionDigits: 1 })} MB` : null,
  ].filter(Boolean);
  return <><p className="preview-status" aria-label="Actual export quality">{parts.join(' · ')}</p>{silence && <p className="preview-status">{silence.beforeDuration.toFixed(2)}s → {silence.afterDuration.toFixed(2)}s · {silence.message}</p>}</>;
}
