# Hachi TUI kit (Textual)

A recreation of Hachi's terminal UI (Textual). Always dark (`#16151A`), JetBrains Mono throughout,
the red `hachi ▸` prompt. Rounded panels with titles set into the border, a header showing live
budget, an output log, the leash dialog rendered as a TUI modal, and a key-binding footer.

## Files
- `index.html` — entry; renders `window.Tui` full-screen.
- `Tui.jsx` — the whole screen: header, runs panel, output log, `LeashDialog`, footer.

## Interaction
The leash dialog is shown on load. **Deny / Allow once / Always allow** dismiss it and append the
result to the output log. Click a run in the left panel to select it.

> Self-contained (dark-surface color literals live in the file); does not require the bundle, though
> it links `styles.css` for the mono font token.
