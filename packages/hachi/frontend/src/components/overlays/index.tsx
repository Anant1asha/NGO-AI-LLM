// ============================================================
// GlobalOverlays — renders all five app-level overlays.
// Each self-gates on its own store flag so there's no
// conditional logic here; just compose and render.
// Consumed by routes/__root.tsx.
// ============================================================

import React from 'react';
import { CommandPalette }     from './CommandPalette';
import { SetupWizard }        from './SetupWizard';
import { KennelConsent }      from './KennelConsent';
import { ReconnectingBanner } from './ReconnectingBanner';
import { ToastHost }          from './ToastHost';

// Re-export individual overlays for consumers who import them directly.
export { CommandPalette }     from './CommandPalette';
export { SetupWizard }        from './SetupWizard';
export { KennelConsent }      from './KennelConsent';
export { ReconnectingBanner } from './ReconnectingBanner';
export { ToastHost }          from './ToastHost';

/**
 * GlobalOverlays
 * Drop this once in __root.tsx outside the main scroll area.
 * Each child self-gates on its store open-flag and renders nothing
 * when closed, so there is zero overhead when all are inactive.
 */
export function GlobalOverlays() {
  return (
    <>
      <CommandPalette />
      <SetupWizard />
      <KennelConsent />
      <ReconnectingBanner />
      <ToastHost />
    </>
  );
}
