// useBodyScrollLock — prevents the page behind a modal from scrolling while it's open.
// Used alongside inert-ing the background app root (see __root.tsx) so an open overlay
// fully owns the viewport: no background scroll, no background pointer/AT interaction.

import { useEffect } from 'react';

export function useBodyScrollLock(locked: boolean) {
  useEffect(() => {
    if (!locked) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [locked]);
}
