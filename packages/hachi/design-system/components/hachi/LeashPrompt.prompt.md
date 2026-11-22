**The signature Hachi component.** The permission prompt — a calm card that asks before Hachi acts. Must feel clear and trustworthy, never like an error or alarm.

```jsx
<LeashPrompt
  request="Hachi wants to run a command"
  action="npm install"
  why="Install the dependencies for your build"
  onDeny={deny}
  onAllowOnce={allowOnce}
  onAlwaysAllow={alwaysAllow}
/>
```

Anatomy: mascot + plain request, one-line `why:`, the exact action in mono with the red `hachi ▸` prompt, three choices `[Deny] [Allow once] [Always allow]`, and the caption "you hold the leash". Keep copy plain and unalarming.
