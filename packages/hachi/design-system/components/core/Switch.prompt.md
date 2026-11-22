Boolean toggle for settings and permissions — on-state fills Torii red.

```jsx
<Switch checked={onWatch} onChange={setOnWatch} label="Keep on watch" />
```

Controlled: pass `checked` and `onChange(next)`. Optional trailing `label`. Keyboard-accessible (space/enter).
