# Accessibility implementation check

Checked: 30 July 2026  
Updated: 2 August 2026 (keyboard feedback journeys, zoom reflow)

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
- A keyboard-only journey completes the whole translation feedback flow: flag
  verdict, passage verdict, correction text, and save — all with Enter, Tab,
  and typing.
- A reflow journey verifies no horizontal scrolling at 640px and 320px layout
  widths, approximating 200% and 400% browser zoom on a 1280px desktop screen.

The component suite contains 18 tests and the browser suite contains ten
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
  result (manual; the keyboard-only journeys cover the same paths without a
  screen reader);
- zoom and reflow review on a real browser using Ctrl/Cmd + plus keys;
- evaluation with at least one reader who uses assistive technology;
- captions and legible on-screen text in the two-minute submission video.
