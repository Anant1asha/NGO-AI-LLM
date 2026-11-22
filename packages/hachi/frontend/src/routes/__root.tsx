import React, { useEffect, useRef } from 'react'
import { createRootRoute, Outlet } from '@tanstack/react-router'
import { Sidebar } from '../components/shell/Sidebar'
import { GovernanceBar } from '../components/shell/GovernanceBar'
import { GlobalOverlays } from '../components/overlays'
import { useStore } from '../lib/store/store'
import { bootstrapLiveData } from '../lib/data/bootstrap'
import { useIsMobile } from '../lib/hooks/useMediaQuery'
import { useBodyScrollLock } from '../lib/hooks/useBodyScrollLock'

function RootLayout() {
  const theme = useStore((s) => s.theme)
  const dataMode = useStore((s) => s.dataMode)
  const isMobile = useIsMobile()

  // C5: any page-level overlay (CommandPalette / SetupWizard / KennelConsent) should
  // lock body scroll and make the app behind it inert — otherwise the page scrolls
  // behind the scrim, a mouse user can click background controls, and a screen-reader
  // virtual cursor walks straight into the page behind the "modal".
  const anyOverlayOpen = useStore(
    (s) => s.palette.open || s.setup.open || s.kennelConsent !== null || s.kennelBrowseOpen
  )
  useBodyScrollLock(anyOverlayOpen)
  const appRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = appRef.current
    if (!el) return
    // `inert` isn't in this project's React/DOM type defs yet — set it as a raw property.
    ;(el as unknown as { inert: boolean }).inert = anyOverlayOpen
  }, [anyOverlayOpen])

  useEffect(() => {
    if (theme === 'auto') {
      document.documentElement.removeAttribute('data-theme')
    } else {
      document.documentElement.setAttribute('data-theme', theme)
    }
  }, [theme])

  // Hydrate eager domains (config, sessions, spend) from the gateway on mount.
  // Each loader degrades to seeded fixtures on failure, so this never blanks the UI.
  useEffect(() => {
    if (dataMode === 'live') void bootstrapLiveData()
  }, [dataMode])

  return (
    <div
      data-theme={theme !== 'auto' ? theme : undefined}
      style={{
        display: 'flex',
        // On mobile the sidebar becomes an off-canvas drawer; the root
        // switches to column layout so the top-bar sits above <main>.
        flexDirection: isMobile ? 'column' : 'row',
        height: '100dvh',
        overflow: 'hidden',
        background: 'var(--hachi-canvas)',
        color: 'var(--hachi-ink)',
        fontFamily: 'var(--font-body)',
        fontSize: '14px',
      }}
    >
      {/* Everything except the overlay layer — made inert while a page-level
          overlay is open so background pointer/keyboard/AT interaction is blocked. */}
      <div
        ref={appRef}
        aria-hidden={anyOverlayOpen || undefined}
        style={{
          display: 'flex',
          flexDirection: isMobile ? 'column' : 'row',
          flex: 1,
          minWidth: 0,
          minHeight: 0,
          overflow: 'hidden',
        }}
      >
        {/* On mobile: Sidebar renders only the top-bar + drawer overlay.
            On desktop: Sidebar renders the fixed left panel. */}
        <Sidebar />
        <main
          style={{
            flex: 1,
            minWidth: 0,
            // On mobile full height minus the 52px top-bar rendered inside Sidebar
            minHeight: 0,
            position: 'relative',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
          }}
        >
          <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
            <Outlet />
          </div>
          <GovernanceBar />
        </main>
      </div>
      <GlobalOverlays />
    </div>
  )
}

export const Route = createRootRoute({
  component: RootLayout,
})
