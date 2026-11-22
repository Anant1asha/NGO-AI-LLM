Status indicator for runs and tasks — the four canonical Hachi states, lowercase, tinted bg with same-family text.

```jsx
<StatusPill status="working" />
<StatusPill status="on-watch" />
<StatusPill status="done" />
<StatusPill status="blocked" />
```

Statuses: `working` (amber) · `on-watch` (navy) · `done` (green) · `blocked` (red). Default labels match the status; override with `label`. Never ALL CAPS.
