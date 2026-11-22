// SettingsNav — the section switcher for the Settings area.
// Renders as a vertical rail on desktop and a horizontal, scrollable tab strip
// on mobile. Mirrors the app sidebar's NavItem idiom (icon + label, brand-tint
// active state).

import { Icon } from '../icons/Icon';

export interface SettingsSection {
  key: string;
  label: string;
  icon: string;
}

export const SETTINGS_SECTIONS: SettingsSection[] = [
  { key: 'general', label: 'General', icon: 'settings' },
  { key: 'permissions', label: 'Permissions', icon: 'leash' },
  { key: 'spend', label: 'Spend', icon: 'dollar' },
  { key: 'models', label: 'AI & models', icon: 'brain' },
  { key: 'voice', label: 'Voice', icon: 'mic' },
];

function NavButton({
  section,
  active,
  horizontal,
  onSelect,
}: {
  section: SettingsSection;
  active: boolean;
  horizontal: boolean;
  onSelect: (k: string) => void;
}) {
  const color = active ? 'var(--hachi-brand)' : 'var(--hachi-ink)';

  return (
    <button
      type="button"
      className="hachi-settings-navbtn"
      aria-current={active ? 'page' : undefined}
      onClick={() => onSelect(section.key)}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 9,
        width: horizontal ? 'auto' : '100%',
        flexShrink: 0,
        padding: horizontal ? '8px 14px' : '9px 11px',
        borderRadius: 10,
        border: horizontal && active ? '0.5px solid var(--hachi-brand)' : '0.5px solid transparent',
        background: 'transparent',
        color,
        font: `${active ? 500 : 400} 13px var(--font-body)`,
        cursor: 'pointer',
        textAlign: 'left',
        whiteSpace: 'nowrap',
        transition: 'background var(--dur-fast) var(--ease)',
      }}
    >
      <span style={{ display: 'inline-flex', color: active ? 'var(--hachi-brand)' : 'var(--hachi-muted)' }}>
        <Icon name={section.icon} size={16} />
      </span>
      {section.label}
    </button>
  );
}

export function SettingsNav({
  active,
  onSelect,
  orientation,
}: {
  active: string;
  onSelect: (k: string) => void;
  orientation: 'vertical' | 'horizontal';
}) {
  const horizontal = orientation === 'horizontal';
  return (
    <nav
      aria-label="Settings sections"
      className={horizontal ? 'hachi-scroll' : undefined}
      style={
        horizontal
          ? {
              display: 'flex',
              gap: 8,
              overflowX: 'auto',
              padding: '10px 16px',
              borderBottom: '0.5px solid var(--hachi-line)',
              background: 'var(--hachi-canvas)',
            }
          : { display: 'flex', flexDirection: 'column', gap: 2 }
      }
    >
      {SETTINGS_SECTIONS.map((s) => (
        <NavButton
          key={s.key}
          section={s}
          active={active === s.key}
          horizontal={horizontal}
          onSelect={onSelect}
        />
      ))}
    </nav>
  );
}
