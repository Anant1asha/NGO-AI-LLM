Primary action control — use for any clickable command; Torii red is reserved for the single most important action on a view.

```jsx
<Button variant="primary" onClick={allow}>Allow once</Button>
<Button variant="secondary">Deny</Button>
<Button variant="ghost" size="sm">Always allow</Button>
<Button variant="danger">Delete run</Button>
```

Variants: `primary` (red fill, cream text) · `secondary` (navy outline) · `ghost` (muted text) · `danger` (#C0392B, distinct from brand). Sizes: `sm` (32px) · `md` (40px). Pass `icon` for a leading glyph. Labels are always sentence case.
