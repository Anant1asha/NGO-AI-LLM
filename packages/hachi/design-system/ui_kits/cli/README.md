# Hachi CLI kit

A recreation of a Hachi command-line session in a window frame. Shows the scriptable run flow:
`hachi run`, the **inline text leash prompt** (`[d]eny [a]llow once [A]lways · you hold the leash`),
the allow, colorized output, the always-visible budget, and the "Hachi is resting" close.

## Files
- `index.html` — entry; renders `window.Cli`.
- `Cli.jsx` — the terminal transcript and window chrome.

> Self-contained; links `styles.css` for the warm canvas + mono font token.
