// ============================================================
// Hachi — browser Notification helpers (M10 MED-024)
// In-page Notification API only — no service worker / web-push.
// All exports gracefully no-op when Notification is unavailable
// (SSR, old browsers, or when permission is denied).
// ============================================================

/** Whether the Notification API exists in this environment. */
const NOTIF_AVAILABLE = typeof window !== "undefined" && typeof Notification !== "undefined";

/**
 * Lazily requests `Notification.permission` the first time it is called.
 * Returns `true` when permission is (now) granted, `false` otherwise.
 * Safe to call fire-and-forget; never throws.
 */
export async function ensureNotificationPermission(): Promise<boolean> {
  if (!NOTIF_AVAILABLE) return false;
  if (Notification.permission === "granted") return true;
  if (Notification.permission === "denied") return false;
  try {
    const result = await Notification.requestPermission();
    return result === "granted";
  } catch {
    return false;
  }
}

/**
 * Fire a browser notification that Hachi is blocked on an approval,
 * but ONLY when:
 *   1. `Notification.permission` is already "granted" (no re-prompt here), AND
 *   2. `document.hidden` is true — i.e. the user has switched away from the tab.
 *
 * Tag "hachi-approval" collapses repeated notifications into one.
 */
export function notifyApprovalPending(request: string): void {
  if (!NOTIF_AVAILABLE) return;
  if (Notification.permission !== "granted") return;
  if (!document.hidden) return;
  try {
    new Notification("Hachi needs your approval", {
      body: request,
      tag: "hachi-approval",
    });
  } catch {
    // Notification constructor can throw in some sandboxed environments — ignore.
  }
}
