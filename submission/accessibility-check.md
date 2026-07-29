# Accessibility implementation check

Checked: 24 July 2026

This is a developer check of the current interface. It does not replace testing
with disabled readers or establish equivalent UX for everyone.

## Implemented and automatically verified

- A keyboard-visible skip link moves focus to the main content.
- Every interactive control is a native link, button, input, select, textarea,
  summary, or checkbox.
- Keyboard focus has a visible three-pixel outline.
- Input-method, language, warning-feedback, and passage-review toggles expose
  their selected state with `aria-pressed`.
- Empty or invalid article input exposes an alert and `aria-invalid`.
- Translation, claim-selection, and evidence-ready route changes have a polite
  status announcement.
- Translation and evidence progress expose named progress bars with current,
  minimum, and maximum values.
- Claim checkboxes are associated with both their claim text and explanation.
- Source and translation passages use their known EN, VI, or KO language tags.
- One Playwright journey starts with the keyboard, focuses the skip link, and
  verifies focus reaches the main region.

The component suite contains 12 tests and the browser suite contains six
journeys after this pass.

## Contrast probe

A local WCAG contrast calculation produced:

| Foreground/background | Ratio |
|---|---:|
| Main text / paper | 15.35:1 |
| Muted text / paper | 5.13:1 |
| Accent link / paper | 7.71:1 |
| White / primary button | 8.06:1 |
| Risk text / risk background | 6.02:1 |
| Note text / note background | 7.51:1 |

These sampled combinations exceed 4.5:1. They are not a full automated WCAG
audit. Disabled buttons are not included in this contrast claim.

## Still required before claiming equivalent UX

- VoiceOver review on macOS with a real completed translation and evidence
  result;
- keyboard-only completion of every feedback and error-recovery path;
- zoom and reflow review at 200% and 400%;
- evaluation with at least one reader who uses assistive technology;
- captions and legible on-screen text in the two-minute submission video.

