The dark mono terminal surface — `#16151A`, JetBrains Mono, the red `hachi ▸` prompt with a blinking caret. Use for TUI/CLI output blocks.

```jsx
<Terminal
  prompt="run build --watch"
  lines={[
    { text: "hachi ▸ on watch · spent $0.02 of $1.00", tone: "muted" },
    { text: "✓ compiled in 1.2s", tone: "success" },
  ]}
/>
```

Each line takes an optional `tone` (`muted`/`brand`/`working`/`success`/`danger`). The prompt line is fixed at the bottom with the caret.
