Represents one Hachi task. Status pill, thin Torii-red progress bar, and the always-visible budget line — cost is a feature, never hidden.

```jsx
<RunCard title="Refactor auth module" status="working" progress={0.4} spent={0.02} budget={1.0} />
<RunCard title="Generate test suite" status="done" progress={1} spent={0.18} budget={1.0} />
```

Statuses match `StatusPill`. The budget always reads "spent $X of $Y". Pass `onClick` to make it a link to the run detail.
