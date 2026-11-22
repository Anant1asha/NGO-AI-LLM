/** Returns true when running on a Mac (for ⌘ vs Ctrl shortcut labels). */
export function isMac(): boolean {
  return typeof navigator !== 'undefined' && /mac/i.test(navigator.platform)
}
