export interface AccuracyStatsProps {
  /** Fraction in 0–1 (e.g. 0.95 for 95%). Optional for backward compat. */
  accuracyWithin15Px?: number;
  accuracyWithin5Px?: number;
  accuracyWithin3Px?: number;
  /** Optional suffix for labels, e.g. " (estimate)". */
  labelSuffix?: string;
  className?: string;
}

function formatPct(value: number): string {
  return (value * 100).toFixed(2) + '%';
}

export function AccuracyStats({
  accuracyWithin15Px = 0,
  accuracyWithin5Px = 0,
  accuracyWithin3Px = 0,
  labelSuffix = '',
  className = '',
}: AccuracyStatsProps) {
  return (
    <ul className={className} role="status">
      <li>Accuracy within 15px{labelSuffix}: {formatPct(accuracyWithin15Px)}</li>
      <li>Accuracy within 5px{labelSuffix}: {formatPct(accuracyWithin5Px)}</li>
      <li>Accuracy within 3px{labelSuffix}: {formatPct(accuracyWithin3Px)}</li>
    </ul>
  );
}
