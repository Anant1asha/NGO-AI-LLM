// Settings shell — /settings
//
// A sectioned settings area: a side menu (vertical rail on desktop, a horizontal
// tab strip on mobile) switches between focused panels. Each section is a
// self-contained component that reads/writes the store and gateway directly, so
// every change saves on its own — there is no page-level "Save".

import { useEffect, useState } from 'react';
import { createFileRoute } from '@tanstack/react-router';
import { loadConfig } from '../lib/data/domains/config';
import { useIsMobile } from '../lib/hooks/useMediaQuery';
import { SettingsNav, SETTINGS_SECTIONS } from '../components/settings/SettingsNav';
import GeneralSection from '../components/settings/sections/GeneralSection';
import PermissionsSection from '../components/settings/sections/PermissionsSection';
import SpendSection from '../components/settings/sections/SpendSection';
import ProviderSettings from '../components/settings/ProviderSettings';
import VoiceSettings from '../components/settings/VoiceSettings';

const VALID_SECTIONS = new Set(SETTINGS_SECTIONS.map((s) => s.key));

function initialSection(): string {
  if (typeof window === 'undefined') return 'general';
  const hash = window.location.hash.replace('#', '');
  return VALID_SECTIONS.has(hash) ? hash : 'general';
}

function renderSection(section: string) {
  switch (section) {
    case 'permissions':
      return <PermissionsSection />;
    case 'spend':
      return <SpendSection />;
    case 'models':
      return <ProviderSettings />;
    case 'voice':
      return <VoiceSettings />;
    case 'general':
    default:
      return <GeneralSection />;
  }
}

function Settings() {
  const isMobile = useIsMobile();
  const [section, setSection] = useState<string>(initialSection);

  // Load config from gateway on mount (idempotent — also runs on app boot).
  useEffect(() => {
    void loadConfig();
  }, []);

  function selectSection(key: string) {
    setSection(key);
    if (typeof window !== 'undefined') {
      window.history.replaceState(null, '', `#${key}`);
    }
  }

  const header = (
    <div
      className="hachi-settings-header"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        padding: '0 32px',
        height: 68,
        flexShrink: 0,
        borderBottom: '0.5px solid var(--hachi-line)',
      }}
    >
      <h1
        style={{
          margin: 0,
          fontFamily: 'var(--font-display)',
          fontWeight: 500,
          fontSize: 22,
          lineHeight: '26px',
        }}
      >
        Settings
      </h1>
    </div>
  );

  if (isMobile) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        {header}
        <div className="hachi-scroll" style={{ flex: 1, overflow: 'auto' }}>
          <div style={{ position: 'sticky', top: 0, zIndex: 2 }}>
            <SettingsNav active={section} onSelect={selectSection} orientation="horizontal" />
          </div>
          <div className="hachi-settings-body" style={{ padding: '20px 16px 64px' }}>
            {renderSection(section)}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {header}
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        <aside
          className="hachi-scroll"
          style={{
            width: 208,
            flexShrink: 0,
            borderRight: '0.5px solid var(--hachi-line)',
            padding: '18px 14px',
            overflowY: 'auto',
          }}
        >
          <SettingsNav active={section} onSelect={selectSection} orientation="vertical" />
        </aside>
        <div
          className="hachi-scroll hachi-settings-body"
          style={{ flex: 1, overflow: 'auto', padding: '28px 32px 64px' }}
        >
          <div style={{ maxWidth: 760, margin: '0 auto' }}>{renderSection(section)}</div>
        </div>
      </div>
    </div>
  );
}

export const Route = createFileRoute('/settings')({
  component: Settings,
});
