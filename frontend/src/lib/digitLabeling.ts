/**
 * Digit label constants and hotkey helpers for digit labeling.
 * Labels: "0"-"9" for digits, "none" for artifact (not a digit).
 */

const DIGIT_LABELS = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'] as const;
const ARTIFACT_LABEL = 'none';

export function parseHotkeyToDigitLabel(
  key: string,
  _shiftKey: boolean,
  ctrlKey: boolean,
  altKey: boolean
): string | null {
  if (key === ' ' || key === 'Spacebar') return ARTIFACT_LABEL;
  if (ctrlKey || altKey) return null;
  if (key >= '0' && key <= '9') return key;
  return null;
}

export function getHotkeyForDigitLabel(label: string): string | null {
  if (label === ARTIFACT_LABEL) return 'Space';
  if (label >= '0' && label <= '9') return label;
  return null;
}

export function digitLabelToFriendlyLabel(label: string): string {
  if (label === 'unlabeled') return 'Unlabeled';
  if (label === ARTIFACT_LABEL) return 'Not a digit';
  return label;
}

export const BUTTON_GROUPS: { types: readonly string[] }[] = [
  { types: [ARTIFACT_LABEL] },
  { types: [...DIGIT_LABELS] },
];

/** Display order for verification: unlabeled first, then none, then 0-9. */
export const VERIFY_TYPE_ORDER: string[] = [
  'unlabeled',
  ARTIFACT_LABEL,
  ...DIGIT_LABELS,
];
