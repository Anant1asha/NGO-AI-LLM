// ============================================================
// Integrations screen — /integrations
// Shows: connected accounts/tools w/ health/status, MCP servers,
// tool inventory (operator-only), add-MCP affordance.
// ============================================================
import React, { CSSProperties, useEffect, useReducer, useRef, useState } from 'react'
import { createFileRoute } from '@tanstack/react-router'
import { useStore } from '../lib/store/store'
import { Icon } from '../components/icons/Icon'
import { ConnectorLogo } from '../components/icons/ConnectorLogo'
import { Switch } from '../components/ui/Switch'
import { ConfirmButton } from '../components/ui/ConfirmButton'
import { Button } from '../components/ui/Button'
import { Modal } from '../components/ui/Modal'
import { PendingCard } from '../components/ui/PendingCard'
import type { Integration, McpServer, McpTool } from '../lib/data/types'
import type { IntegrationExtended, McpServerExtended } from '../lib/data/domains/integrations'
import {
  loadIntegrations,
  connectIntegration,
  disconnectIntegration,
  submitCredentials,
  testCredentials,
  addMcpServer,
  enableMcpServer,
  disableMcpServer,
  deleteMcpServer,
  validateMcpServerInput,
  subscribeActionStatus,
  getConnectStatus,
  getDisconnectStatus,
  ALLOWED_MCP_COMMANDS,
} from '../lib/data/domains/integrations'
import type { McpCommand, McpTransport, CredentialFieldSpec, CredentialTestResult } from '../lib/data/domains/integrations'

// ---- status meta --------------------------------------------------------

interface StatusMeta {
  bg: string
  fg: string
  dot: string
  text: string
}

const intMeta: Record<string, StatusMeta> = {
  connected: {
    bg: 'var(--hachi-success-tint)',
    fg: 'var(--hachi-success-fg)',
    dot: 'var(--hachi-success)',
    text: 'connected',
  },
  degraded: {
    bg: 'var(--hachi-working-tint)',
    fg: 'var(--hachi-working-fg)',
    dot: 'var(--hachi-working)',
    text: 'degraded',
  },
  none: {
    bg: 'var(--hachi-cream)',
    fg: 'var(--hachi-muted)',
    dot: 'var(--hachi-muted)',
    text: 'not connected',
  },
}

const mcpMeta: Record<string, StatusMeta> = {
  connected: {
    bg: 'var(--hachi-success-tint)',
    fg: 'var(--hachi-success-fg)',
    dot: 'var(--hachi-success)',
    text: 'connected',
  },
  loading: {
    bg: 'var(--hachi-trust-tint)',
    fg: 'var(--hachi-trust)',
    dot: 'var(--hachi-trust)',
    text: 'loading',
  },
  starting: {
    bg: 'var(--hachi-working-tint)',
    fg: 'var(--hachi-working-fg)',
    dot: 'var(--hachi-working)',
    text: 'starting',
  },
  // BB-16: registered but not connected this session (e.g. a TOML server before
  // the first conversation, or a stopped server). Distinct from "starting" so it
  // doesn't read as a boot that never finishes.
  pending: {
    bg: 'var(--hachi-muted-tint, rgba(120,120,130,.12))',
    fg: 'var(--hachi-muted)',
    dot: 'var(--hachi-muted)',
    text: 'needs restart',
  },
  blocked: {
    bg: 'var(--hachi-danger-tint)',
    fg: 'var(--hachi-danger-fg)',
    dot: 'var(--hachi-danger)',
    text: "can't reach",
  },
}

function getIntMeta(status: string): StatusMeta {
  return intMeta[status] ?? intMeta.none
}

function getMcpMeta(status: string): StatusMeta {
  return mcpMeta[status] ?? mcpMeta.starting
}

// ---- sub-components -----------------------------------------------------

interface StatusDotProps {
  bg: string
  size?: number
}
function StatusDot({ bg, size = 7 }: StatusDotProps) {
  return (
    <span
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        background: bg,
        flexShrink: 0,
        display: 'inline-block',
      }}
    />
  )
}

interface StatusChipProps {
  bg: string
  fg: string
  dot: string
  text: string
  dotSize?: number
  padding?: string
  fontSize?: number
}
function StatusChip({ bg, fg, dot, text, dotSize = 7, padding = '5px 11px', fontSize = 12 }: StatusChipProps) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding,
        borderRadius: 999,
        background: bg,
        color: fg,
        fontSize,
        fontWeight: 500,
        whiteSpace: 'nowrap',
        flexShrink: 0,
      }}
    >
      <StatusDot bg={dot} size={dotSize} />
      {text}
    </span>
  )
}

// ---- Credential dialog --------------------------------------------------

interface CredentialDialogProps {
  connectorId: string
  connectorName: string
  fields: CredentialFieldSpec[]
  /** Where existing credentials live — "vault" | "env" | null (not configured). */
  connectorSource?: "vault" | "env" | null
  onClose: () => void
  onSaved: () => void
}

function CredentialDialog({ connectorId, connectorName, fields, connectorSource, onClose, onSaved }: CredentialDialogProps) {
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(fields.map((f) => [f.key, '']))
  )
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({})
  // Test connection state: null = not tested / unavailable, "testing" = in-flight, result otherwise.
  const [testResult, setTestResult] = useState<CredentialTestResult | null | 'testing'>(null)
  // Whether the test endpoint is available (404 means hide the button).
  const [testAvailable, setTestAvailable] = useState<boolean | null>(null)

  // Probe once on open whether the test endpoint is available (404 → hide button).
  useEffect(() => {
    let cancelled = false
    testCredentials(connectorId).then((result) => {
      if (cancelled) return
      // null means 404 (not available); non-null means endpoint exists.
      setTestAvailable(result !== null)
    }).catch(() => {
      if (!cancelled) setTestAvailable(true) // non-404 error → endpoint exists
    })
    return () => { cancelled = true }
  }, [connectorId])

  async function handleTestConnection() {
    setTestResult('testing')
    try {
      const result = await testCredentials(connectorId)
      if (result === null) {
        setTestAvailable(false)
        setTestResult(null)
      } else {
        setTestResult(result)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Test failed'
      setTestResult({ ok: false, message: msg })
    }
  }

  function validate(): boolean {
    const errors: Record<string, string> = {}
    for (const field of fields) {
      if (!field.optional && !values[field.key]?.trim()) {
        errors[field.key] = `${field.label} is required.`
      }
    }
    setFieldErrors(errors)
    return Object.keys(errors).length === 0
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (submitting) return
    if (!validate()) return

    setSubmitting(true)
    setSubmitError(null)

    // Only submit non-empty values.
    const payload: Record<string, string> = {}
    for (const field of fields) {
      const v = values[field.key]?.trim()
      if (v) payload[field.key] = v
    }

    try {
      await submitCredentials(connectorId, payload)
      onSaved()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to save credentials — try again.'
      setSubmitError(msg)
      setSubmitting(false)
    }
  }

  const fieldWrapStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 5 }
  const labelStyle: CSSProperties = { fontSize: 12, fontWeight: 500, color: 'var(--hachi-muted)' }

  function inputStyle(hasError: boolean): CSSProperties {
    return {
      height: 36,
      padding: '0 10px',
      borderRadius: 8,
      border: hasError ? '0.5px solid var(--hachi-danger)' : '0.5px solid var(--hachi-line)',
      background: 'var(--hachi-canvas)',
      color: 'var(--hachi-ink)',
      font: '13px var(--font-body)',
      width: '100%',
      boxSizing: 'border-box' as CSSProperties['boxSizing'],
      fontFamily: 'var(--font-mono)',
    }
  }

  return (
    <Modal
      onClose={() => { if (!submitting) onClose() }}
      titleId="cred-dialog-title"
      dirtyGuard={submitting || Object.values(values).some((v) => v.length > 0)}
      width={480}
    >
        {/* Header */}
        <div style={{ padding: '20px 22px 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div id="cred-dialog-title" style={{ fontFamily: 'var(--font-display)', fontWeight: 500, fontSize: 18 }}>
              Configure {connectorName}
            </div>
            <div style={{ fontSize: 12, color: 'var(--hachi-muted)', marginTop: 2 }}>
              Enter your credentials to enable this integration.
            </div>
          </div>
          <button
            type="button"
            onClick={submitting ? undefined : onClose}
            disabled={submitting}
            aria-label="Close dialog"
            style={{
              width: 30, height: 30, borderRadius: 8, border: 'none',
              background: 'transparent', color: 'var(--hachi-muted)',
              cursor: submitting ? 'not-allowed' : 'pointer',
              display: 'grid', placeItems: 'center', flexShrink: 0,
            }}
          >
            <Icon name="x" size={16} />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} noValidate>
          <div style={{ padding: '16px 22px', display: 'flex', flexDirection: 'column', gap: 14 }}>

            {/* Currently configured hint */}
            {connectorSource === 'vault' && (
              <div
                style={{
                  display: 'flex', alignItems: 'center', gap: 7, fontSize: 12,
                  color: 'var(--hachi-success-fg)', background: 'var(--hachi-success-tint)',
                  padding: '7px 10px', borderRadius: 8,
                }}
              >
                <Icon name="key" size={13} style={{ flexShrink: 0 }} />
                Credentials already configured — enter new values to update.
              </div>
            )}
            {connectorSource === 'env' && (
              <div
                style={{
                  display: 'flex', alignItems: 'center', gap: 7, fontSize: 12,
                  color: 'var(--hachi-trust)', background: 'var(--hachi-trust-tint)',
                  padding: '7px 10px', borderRadius: 8,
                }}
              >
                <Icon name="terminal" size={13} style={{ flexShrink: 0 }} />
                Credentials loaded from environment — set here to override.
              </div>
            )}

            {fields.map((field) => {
              const hasError = Boolean(fieldErrors[field.key])
              const isSecret = field.secret
              const showPlain = showSecrets[field.key] ?? false
              // When a secret is already configured, show masked placeholder until user types.
              const maskedPlaceholder = isSecret && connectorSource != null ? '••••••••' : field.placeholder
              return (
                <div key={field.key} style={fieldWrapStyle}>
                  <label htmlFor={`cred-${field.key}`} style={labelStyle}>
                    {field.label}
                    {!field.optional && (
                      <span aria-hidden="true" style={{ color: 'var(--hachi-danger)', marginLeft: 3 }}>*</span>
                    )}
                    {field.optional && (
                      <span style={{ color: 'var(--hachi-muted)', fontWeight: 400, marginLeft: 4 }}>(optional)</span>
                    )}
                    {connectorSource === 'env' && (
                      <span
                        style={{
                          marginLeft: 6, fontSize: 10, fontWeight: 500,
                          color: 'var(--hachi-trust)', background: 'var(--hachi-trust-tint)',
                          padding: '1px 6px', borderRadius: 999,
                        }}
                      >
                        from environment
                      </span>
                    )}
                  </label>
                  <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                    <input
                      id={`cred-${field.key}`}
                      type={isSecret && !showPlain ? 'password' : 'text'}
                      value={values[field.key] ?? ''}
                      onChange={(e) => {
                        setValues((prev) => ({ ...prev, [field.key]: e.target.value }))
                        if (hasError) setFieldErrors((prev) => ({ ...prev, [field.key]: '' }))
                      }}
                      placeholder={maskedPlaceholder}
                      disabled={submitting}
                      aria-invalid={hasError}
                      aria-describedby={hasError ? `cred-err-${field.key}` : undefined}
                      style={{ ...inputStyle(hasError), paddingRight: isSecret ? 38 : 10 }}
                      autoComplete={isSecret ? 'off' : 'on'}
                      spellCheck={false}
                    />
                    {isSecret && (
                      <button
                        type="button"
                        onClick={() => setShowSecrets((prev) => ({ ...prev, [field.key]: !showPlain }))}
                        aria-label={showPlain ? 'Hide value' : 'Show value'}
                        style={{
                          position: 'absolute', right: 8, border: 'none',
                          background: 'transparent', color: 'var(--hachi-muted)',
                          cursor: 'pointer', padding: '2px 4px', borderRadius: 4, lineHeight: 1,
                        }}
                      >
                        <Icon name={showPlain ? 'eye-off' : 'eye'} size={14} />
                      </button>
                    )}
                  </div>
                  {hasError && (
                    <span id={`cred-err-${field.key}`} style={{ fontSize: 11.5, color: 'var(--hachi-danger)' }} role="alert">
                      {fieldErrors[field.key]}
                    </span>
                  )}
                  {field.help_text && (
                    <span style={{ fontSize: 11, color: 'var(--hachi-muted)' }}>{field.help_text}</span>
                  )}
                </div>
              )
            })}

            {/* Test connection */}
            {testAvailable && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <button
                  type="button"
                  onClick={() => void handleTestConnection()}
                  disabled={submitting || testResult === 'testing'}
                  style={{
                    alignSelf: 'flex-start',
                    display: 'inline-flex', alignItems: 'center', gap: 6,
                    height: 32, padding: '0 12px', borderRadius: 8,
                    border: '0.5px solid var(--hachi-line)',
                    background: 'var(--hachi-canvas)', color: 'var(--hachi-ink)',
                    font: '500 12.5px var(--font-body)',
                    cursor: submitting || testResult === 'testing' ? 'not-allowed' : 'pointer',
                    opacity: submitting || testResult === 'testing' ? 0.65 : 1,
                  }}
                >
                  <Icon name="zap" size={13} />
                  {testResult === 'testing' ? 'Testing…' : 'Test connection'}
                </button>
                {testResult !== null && testResult !== 'testing' && (
                  <div
                    style={{
                      display: 'flex', alignItems: 'flex-start', gap: 7, fontSize: 12,
                      color: testResult.ok ? 'var(--hachi-success-fg)' : 'var(--hachi-danger-fg)',
                      background: testResult.ok ? 'var(--hachi-success-tint)' : 'var(--hachi-danger-tint)',
                      padding: '7px 10px', borderRadius: 8,
                    }}
                    role="status"
                  >
                    <Icon
                      name={testResult.ok ? 'check' : 'alert'}
                      size={13}
                      style={{ marginTop: 1, flexShrink: 0 }}
                    />
                    {testResult.message}
                  </div>
                )}
              </div>
            )}

            {submitError && (
              <div
                style={{
                  display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 12.5,
                  color: 'var(--hachi-danger-fg)', background: 'var(--hachi-danger-tint)',
                  padding: '10px 12px', borderRadius: 8,
                }}
                role="alert"
              >
                <Icon name="alert" size={14} style={{ marginTop: 1, flexShrink: 0 }} />
                {submitError}
              </div>
            )}
          </div>

          {/* Actions */}
          <div style={{ display: 'flex', gap: 10, padding: '0 22px 22px' }}>
            <Button variant="secondary" onClick={() => { if (!submitting) onClose() }} disabled={submitting} style={{ flex: 1, height: 42 }}>
              Cancel
            </Button>
            <Button variant="primary" type="submit" loading={submitting} style={{ flex: 1, height: 42 }}>
              Save credentials
            </Button>
          </div>
        </form>
    </Modal>
  )
}

// ---- Integration card ---------------------------------------------------

interface IntCardProps {
  integration: Integration
  onConnect: () => void
  onDisconnect: () => void
  connectLoading: boolean
  connectError: boolean
  disconnectLoading: boolean
  disconnectError: boolean
}

function IntCard({
  integration: i,
  onConnect,
  onDisconnect,
  connectLoading,
  connectError,
  disconnectLoading,
  disconnectError,
}: IntCardProps) {
  // Cast to extended to access OAuth-specific and apikey fields gracefully.
  const ext = i as Partial<IntegrationExtended>
  const authType = ext.auth_type ?? 'none'
  const configured = ext.configured ?? true  // default true for backwards compat
  const credentialFields = ext.credential_fields ?? []
  const isOAuth = authType === 'oauth2'
  const isApikey = authType === 'apikey'
  const hasCredentialFields = isApikey && credentialFields.length > 0
  // OAuth is "unconfigured" when client creds are missing from env (admin task).
  // Apikey with credential_fields is always "configurable" by the user.
  const isUnconfigured = isOAuth && !configured

  const sm = getIntMeta(i.status)
  const connected = i.status === 'connected'

  // Determine primary button label.
  let primaryLabel: string
  if (isUnconfigured) {
    primaryLabel = 'Needs setup'
  } else if (connectLoading) {
    primaryLabel = 'Connecting…'
  } else if (connectError) {
    primaryLabel = 'Retry'
  } else if (hasCredentialFields) {
    primaryLabel = connected ? 'Update credentials' : 'Configure'
  } else if (i.status === 'connected') {
    primaryLabel = 'Re-authorise'
  } else if (i.status === 'degraded') {
    primaryLabel = 'Fix access'
  } else {
    primaryLabel = isOAuth ? 'Connect with OAuth' : 'Connect'
  }

  const primaryFg =
    isUnconfigured
      ? 'var(--hachi-muted)'
      : connectError
      ? 'var(--hachi-danger)'
      : i.status === 'none'
      ? 'var(--hachi-trust)'
      : hasCredentialFields && !connected
      ? 'var(--hachi-trust)'
      : 'var(--hachi-ink)'


  return (
    <div
      style={{
        background: 'var(--hachi-surface)',
        border: '0.5px solid var(--hachi-line)',
        borderRadius: 14,
        padding: 18,
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      {/* header row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: 10,
            background: 'var(--hachi-cream)',
            display: 'grid',
            placeItems: 'center',
            flexShrink: 0,
          }}
        >
          <ConnectorLogo id={i.id} size={22} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 500, fontSize: 15, display: 'flex', alignItems: 'center', gap: 6 }}>
            {i.name}
            {/* Show configured indicator when apikey connector is wired */}
            {hasCredentialFields && connected && (
              <span
                title="Credentials configured"
                aria-label="Credentials configured"
                tabIndex={0}
                style={{ lineHeight: 0, display: 'inline-flex', cursor: 'default' }}
              >
                <Icon name="circle-check" size={14} style={{ color: 'var(--hachi-success)', flexShrink: 0 }} />
              </span>
            )}
          </div>
          <div style={{ fontSize: 12, color: 'var(--hachi-muted)', marginTop: 1 }}>
            {i.can}
          </div>
        </div>
        <StatusChip
          bg={sm.bg}
          fg={sm.fg}
          dot={sm.dot}
          text={sm.text}
          dotSize={7}
          padding="5px 11px"
          fontSize={12}
        />
      </div>

      {/* unconfigured OAuth warning */}
      {isUnconfigured && (
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 7,
            fontSize: 12,
            color: 'var(--hachi-muted)',
            background: 'var(--hachi-cream)',
            padding: '7px 10px',
            borderRadius: 8,
          }}
          title="An admin must configure the OAuth client ID and secret for this connector before users can connect."
        >
          <Icon name="key" size={13} style={{ marginTop: 1, flexShrink: 0 }} />
          Admin needs to set OAuth client credentials before this can be connected.
        </div>
      )}

      {/* apikey hint when not yet configured */}
      {hasCredentialFields && !connected && !connectError && (
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 7,
            fontSize: 12,
            color: 'var(--hachi-muted)',
            background: 'var(--hachi-cream)',
            padding: '7px 10px',
            borderRadius: 8,
          }}
        >
          <Icon name="key" size={13} style={{ marginTop: 1, flexShrink: 0 }} />
          Click &ldquo;Configure&rdquo; to enter your credentials.
        </div>
      )}

      {/* risky warning */}
      {i.risky && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 7,
            fontSize: 12,
            color: 'var(--hachi-danger-fg)',
            background: 'var(--hachi-danger-tint)',
            padding: '7px 10px',
            borderRadius: 8,
          }}
        >
          <Icon name="alert" size={14} />
          Broad filesystem + shell access. Review what it can reach.
        </div>
      )}

      {/* connect error banner */}
      {connectError && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 7,
            fontSize: 12,
            color: 'var(--hachi-danger-fg)',
            background: 'var(--hachi-danger-tint)',
            padding: '7px 10px',
            borderRadius: 8,
          }}
          role="alert"
        >
          <Icon name="alert" size={14} />
          {isOAuth
            ? 'OAuth flow failed. Check popup permissions and try again.'
            : 'Connection failed. Check your gateway and try again.'}
        </div>
      )}

      {/* disconnect error banner */}
      {disconnectError && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 7,
            fontSize: 12,
            color: 'var(--hachi-danger-fg)',
            background: 'var(--hachi-danger-tint)',
            padding: '7px 10px',
            borderRadius: 8,
          }}
          role="alert"
        >
          <Icon name="alert" size={14} />
          Disconnect failed. Check your gateway and try again.
        </div>
      )}

      {/* action buttons */}
      <div style={{ display: 'flex', gap: 8 }}>
        <button
          className="hachi-int-primary-btn"
          onClick={isUnconfigured ? undefined : onConnect}
          disabled={isUnconfigured || connectLoading || disconnectLoading}
          aria-busy={connectLoading}
          title={isUnconfigured ? 'An admin must configure OAuth client credentials first.' : undefined}
          style={{
            flex: 1,
            height: 34,
            borderRadius: 10,
            border: connectError
              ? '0.5px solid var(--hachi-danger)'
              : hasCredentialFields && !connected
              ? '0.5px solid var(--hachi-trust)'
              : '0.5px solid var(--hachi-line)',
            background: 'var(--hachi-canvas)',
            color: primaryFg,
            font: '500 13px var(--font-body)',
            cursor: connectLoading || disconnectLoading || isUnconfigured ? 'not-allowed' : 'pointer',
            opacity: connectLoading || disconnectLoading || isUnconfigured ? 0.65 : 1,
            transition: 'background var(--dur-fast) var(--ease)',
          }}
        >
          {primaryLabel}
        </button>
        {/* Show "Clear / Disconnect" button when connected or for apikey when configured */}
        {(connected || (hasCredentialFields && configured)) && (
          disconnectLoading ? (
            <span style={{ fontSize: 13, color: 'var(--hachi-muted)', padding: '0 4px' }}>
              Clearing…
            </span>
          ) : (
            <ConfirmButton
              label={disconnectError ? 'Retry' : hasCredentialFields ? 'Clear' : 'Disconnect'}
              confirmLabel={hasCredentialFields ? 'Clear?' : 'Disconnect?'}
              onConfirm={onDisconnect}
              tone="danger"
              ariaLabel={hasCredentialFields ? 'Clear credentials' : 'Disconnect integration'}
              style={{ opacity: connectLoading ? 0.65 : 1 }}
            />
          )
        )}
      </div>
    </div>
  )
}

// ---- MCP server row -----------------------------------------------------

interface McpServerRowProps {
  server: McpServer
  isLast: boolean
}

function McpServerRow({ server: s, isLast }: McpServerRowProps) {
  const m = getMcpMeta(s.status)
  const toolCount = s.tools === 0 ? '—' : s.tools
  const ext = s as Partial<McpServerExtended>
  // Default enabled=true when the backend hasn't sent the field yet (older gateway).
  const enabled = ext.enabled ?? true
  const [toggling, setToggling] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const confirmTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => () => { if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current) }, [])

  async function handleToggle(next: boolean) {
    if (toggling) return
    setToggling(true)
    try {
      if (next) {
        await enableMcpServer(s.name)
      } else {
        await disableMcpServer(s.name)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to update MCP server'
      useStore.getState().showToast(msg, 'blocked')
    } finally {
      setToggling(false)
    }
  }

  async function handleDelete() {
    if (!confirmDelete) {
      setConfirmDelete(true)
      // Auto-disarm after 4s so an armed delete doesn't linger indefinitely if
      // the user walks away without blurring or pressing Escape.
      confirmTimerRef.current = setTimeout(() => setConfirmDelete(false), 4000)
      return
    }
    if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current)
    setDeleting(true)
    setConfirmDelete(false)
    try {
      await deleteMcpServer(s.name)
      useStore.getState().showToast(`Removed ${s.name}`, 'success')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to remove MCP server'
      useStore.getState().showToast(msg, 'blocked')
      setDeleting(false)
    }
  }

  // Cancel the armed confirm state on blur or Escape — NOT on mouseleave, which
  // let a 1px cursor jitter silently disarm the confirmation (and never worked
  // for keyboard/touch users, who have no mouseleave event at all).
  function handleDeleteBlur() {
    setConfirmDelete(false)
  }
  function handleDeleteKeyDown(e: React.KeyboardEvent<HTMLButtonElement>) {
    if (e.key === 'Escape' && confirmDelete) {
      e.stopPropagation()
      setConfirmDelete(false)
    }
  }

  return (
    <div
      className="hachi-mcp-server-row"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 13,
        padding: '12px 16px',
        borderBottom: isLast ? 'none' : '0.5px solid var(--hachi-line)',
        opacity: enabled ? 1 : 0.55,
        transition: 'opacity var(--dur-fast) var(--ease)',
      }}
    >
      {/* name + error */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 13,
            color: 'var(--hachi-ink)',
          }}
        >
          {s.name}
        </div>
        {s.err && (
          <div
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 11.5,
              color: 'var(--hachi-danger)',
              marginTop: 2,
            }}
          >
            {s.err}
          </div>
        )}
      </div>

      {/* status */}
      <span style={{ width: 96, flexShrink: 0 }}>
        <StatusChip
          bg={m.bg}
          fg={m.fg}
          dot={m.dot}
          text={m.text}
          dotSize={6}
          padding="4px 9px"
          fontSize={11.5}
        />
      </span>

      {/* tool count */}
      <span
        style={{
          width: 52,
          flexShrink: 0,
          textAlign: 'right',
          fontFamily: 'var(--font-mono)',
          fontSize: 12.5,
          color: 'var(--hachi-ink)',
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {toolCount}
      </span>

      {/* transport */}
      <span
        style={{
          width: 64,
          flexShrink: 0,
          fontFamily: 'var(--font-mono)',
          fontSize: 12,
          color: 'var(--hachi-muted)',
        }}
      >
        {s.transport}
      </span>

      {/* uptime */}
      <span
        style={{
          width: 64,
          flexShrink: 0,
          textAlign: 'right',
          fontFamily: 'var(--font-mono)',
          fontSize: 12,
          color: 'var(--hachi-muted)',
        }}
      >
        {s.uptime}
      </span>

      {/* enable/disable toggle — BB-17: fixed 40px column (= Switch width =
          the "Enabled" header width) so cells line up under their headers.
          Previously this had no width, so every cell after Uptime drifted. */}
      <span
        style={{ width: 40, flexShrink: 0, display: 'flex', alignItems: 'center' }}
        title={enabled ? 'Disable server' : 'Enable server'}
      >
        <Switch
          checked={enabled}
          onChange={handleToggle}
          disabled={toggling}
          ariaLabel={enabled ? 'Disable server' : 'Enable server'}
        />
      </span>

      {/* delete button — single click shows confirm label, second click fires */}
      <button
        type="button"
        className="hachi-mcp-delete-btn"
        data-confirm={String(confirmDelete)}
        onClick={handleDelete}
        onBlur={handleDeleteBlur}
        onKeyDown={handleDeleteKeyDown}
        disabled={deleting}
        aria-label={confirmDelete ? `Confirm remove ${s.name}` : `Remove ${s.name}`}
        title={confirmDelete ? 'Click again to confirm removal' : 'Remove server'}
        style={{
          flexShrink: 0,
          // BB-17: normal state occupies the same 32px slot the header reserves
          // (the empty spacer span) so columns align; the confirm state grows to
          // fit "Remove?" — a transient interaction, not the resting layout.
          width: confirmDelete ? 'auto' : 32,
          justifyContent: 'center',
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          height: 26,
          padding: confirmDelete ? '0 8px' : '0 4px',
          borderRadius: 7,
          cursor: deleting ? 'not-allowed' : 'pointer',
          opacity: deleting ? 0.5 : 1,
          font: '500 11.5px var(--font-body)',
          transition: 'background var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease)',
          whiteSpace: 'nowrap',
        }}
      >
        <Icon name="minus" size={13} />
        {confirmDelete && <span>Remove?</span>}
      </button>
    </div>
  )
}

// ---- MCP tool row -------------------------------------------------------

interface McpToolRowProps {
  tool: McpTool
  isLast: boolean
}

function McpToolRow({ tool: t, isLast }: McpToolRowProps) {
  const args = t.args.map(([k, ty]) => ({ k, ty }))
  return (
    <div
      style={{
        padding: '13px 0',
        borderBottom: isLast ? 'none' : '0.5px solid var(--hachi-line)',
      }}
    >
      {/* name + server badge */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 9,
          marginBottom: args.length > 0 ? 8 : 0,
        }}
      >
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 13,
            color: 'var(--hachi-ink)',
          }}
        >
          {t.name}
        </span>
        <span
          style={{
            fontSize: 11,
            color: 'var(--hachi-muted)',
            background: 'var(--hachi-cream)',
            padding: '2px 8px',
            borderRadius: 999,
          }}
        >
          {t.server}
        </span>
      </div>

      {/* arg chips */}
      {args.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
          {args.map((arg) => (
            <span
              key={arg.k}
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 11.5,
                color: 'var(--hachi-muted)',
                background: 'var(--hachi-canvas)',
                border: '0.5px solid var(--hachi-line)',
                padding: '3px 8px',
                borderRadius: 6,
              }}
            >
              <span style={{ color: 'var(--hachi-ink)' }}>{arg.k}</span>: {arg.ty}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

// ---- Empty state --------------------------------------------------------

function NoIntegrations() {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 12,
        padding: '48px 24px',
        textAlign: 'center',
        color: 'var(--hachi-muted)',
      }}
    >
      <Icon name="plug" size={32} style={{ opacity: 0.35 }} />
      <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--hachi-ink)' }}>
        No accounts connected yet
      </div>
      <div style={{ fontSize: 13 }}>
        Connect an account to let Hachi reach your tools.
      </div>
    </div>
  )
}

function NoMcpServers() {
  return (
    <div
      style={{
        padding: '32px 16px',
        textAlign: 'center',
        color: 'var(--hachi-muted)',
        fontSize: 13,
      }}
    >
      No MCP servers configured.
    </div>
  )
}

// ---- Add MCP dialog — extended with transport selector ------------------

interface AddMcpDialogProps {
  onClose: () => void
}

interface FormState {
  name: string
  transport: McpTransport
  // stdio fields
  command: McpCommand
  args: string
  envKey: string
  envVal: string
  envVars: Record<string, string>
  // sse/http fields
  url: string
  headerKey: string
  headerVal: string
  headers: Record<string, string>
  // submit state
  submitting: boolean
  submitError: string | null
  fieldErrors: Partial<Record<'name' | 'args' | 'envVars' | 'url' | 'command', string>>
}

type FormAction =
  | { type: 'set_name'; value: string }
  | { type: 'set_transport'; value: McpTransport }
  | { type: 'set_command'; value: McpCommand }
  | { type: 'set_args'; value: string }
  | { type: 'set_env_key'; value: string }
  | { type: 'set_env_val'; value: string }
  | { type: 'add_env' }
  | { type: 'remove_env'; key: string }
  | { type: 'set_url'; value: string }
  | { type: 'set_header_key'; value: string }
  | { type: 'set_header_val'; value: string }
  | { type: 'add_header' }
  | { type: 'remove_header'; key: string }
  | { type: 'set_submitting'; value: boolean }
  | { type: 'set_submit_error'; value: string | null }
  | { type: 'set_field_error'; field: keyof FormState['fieldErrors']; value: string | null }
  | { type: 'clear_field_error'; field: keyof FormState['fieldErrors'] }

function formReducer(state: FormState, action: FormAction): FormState {
  switch (action.type) {
    case 'set_name':
      return { ...state, name: action.value, fieldErrors: { ...state.fieldErrors, name: undefined } }
    case 'set_transport':
      return { ...state, transport: action.value, fieldErrors: {} }
    case 'set_command':
      return { ...state, command: action.value }
    case 'set_args':
      return { ...state, args: action.value, fieldErrors: { ...state.fieldErrors, args: undefined } }
    case 'set_env_key':
      return { ...state, envKey: action.value }
    case 'set_env_val':
      return { ...state, envVal: action.value }
    case 'add_env': {
      if (!state.envKey.trim()) return state
      return {
        ...state,
        envVars: { ...state.envVars, [state.envKey.trim()]: state.envVal },
        envKey: '',
        envVal: '',
        fieldErrors: { ...state.fieldErrors, envVars: undefined },
      }
    }
    case 'remove_env': {
      const next = { ...state.envVars }
      delete next[action.key]
      return { ...state, envVars: next }
    }
    case 'set_url':
      return { ...state, url: action.value, fieldErrors: { ...state.fieldErrors, url: undefined } }
    case 'set_header_key':
      return { ...state, headerKey: action.value }
    case 'set_header_val':
      return { ...state, headerVal: action.value }
    case 'add_header': {
      if (!state.headerKey.trim()) return state
      return {
        ...state,
        headers: { ...state.headers, [state.headerKey.trim()]: state.headerVal },
        headerKey: '',
        headerVal: '',
      }
    }
    case 'remove_header': {
      const next = { ...state.headers }
      delete next[action.key]
      return { ...state, headers: next }
    }
    case 'set_submitting':
      return { ...state, submitting: action.value }
    case 'set_submit_error':
      return { ...state, submitError: action.value }
    case 'set_field_error':
      return {
        ...state,
        fieldErrors: {
          ...state.fieldErrors,
          [action.field]: action.value ?? undefined,
        },
      }
    case 'clear_field_error':
      return {
        ...state,
        fieldErrors: { ...state.fieldErrors, [action.field]: undefined },
      }
    default:
      return state
  }
}

const initialFormState: FormState = {
  name: '',
  transport: 'stdio',
  command: 'npx',
  args: '',
  envKey: '',
  envVal: '',
  envVars: {},
  url: '',
  headerKey: '',
  headerVal: '',
  headers: {},
  submitting: false,
  submitError: null,
  fieldErrors: {},
}

function AddMcpDialog({ onClose }: AddMcpDialogProps) {
  const [state, dispatch] = useReducer(formReducer, initialFormState)
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (state.submitting) return

    const input = {
      name: state.name.trim(),
      transport: state.transport,
      // stdio
      command: state.command,
      args: state.args.trim(),
      envVars: state.envVars,
      // sse/http
      url: state.url.trim(),
      headers: state.headers,
    }

    const result = validateMcpServerInput(input)
    if (!result.ok) {
      const field = result.field as keyof FormState['fieldErrors']
      if (field === 'name' || field === 'args' || field === 'envVars' || field === 'url') {
        dispatch({ type: 'set_field_error', field, value: result.message })
      } else {
        dispatch({ type: 'set_submit_error', value: result.message })
      }
      return
    }

    dispatch({ type: 'set_submitting', value: true })
    dispatch({ type: 'set_submit_error', value: null })

    try {
      await addMcpServer(input)
      useStore.getState().showToast(`MCP server "${input.name}" registered`, 'success')
      onClose()
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : 'Failed to register MCP server — check the server name and args, then try again.'
      dispatch({ type: 'set_submit_error', value: msg })
      dispatch({ type: 'set_submitting', value: false })
    }
  }

  const fieldWrapStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
  }

  const labelStyle: CSSProperties = {
    fontSize: 12,
    fontWeight: 500,
    color: 'var(--hachi-muted)',
  }

  function fieldInputStyle(hasError: boolean): CSSProperties {
    return {
      height: 36,
      padding: '0 10px',
      borderRadius: 8,
      border: hasError
        ? '0.5px solid var(--hachi-danger)'
        : '0.5px solid var(--hachi-line)',
      background: 'var(--hachi-canvas)',
      color: 'var(--hachi-ink)',
      font: '13px var(--font-body)',
      width: '100%',
      boxSizing: 'border-box' as CSSProperties['boxSizing'],
    }
  }

  const errorTextStyle: CSSProperties = {
    fontSize: 11.5,
    color: 'var(--hachi-danger)',
    marginTop: 2,
  }

  const hasEnvPairs = Object.keys(state.envVars).length > 0
  const hasHeaderPairs = Object.keys(state.headers).length > 0
  const isStdio = state.transport === 'stdio'

  return (
    <Modal
      onClose={() => { if (!state.submitting) onClose() }}
      titleId="add-mcp-dialog-title"
      dirtyGuard={state.submitting}
      width={520}
    >
        {/* Header */}
        <div
          style={{
            padding: '20px 22px 0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <div
              id="add-mcp-dialog-title"
              style={{
                fontFamily: 'var(--font-display)',
                fontWeight: 500,
                fontSize: 18,
              }}
            >
              Add MCP server
            </div>
            <div style={{ fontSize: 12, color: 'var(--hachi-muted)', marginTop: 2 }}>
              Register a new Model Context Protocol server for Hachi to call.
            </div>
          </div>
          <button
            type="button"
            onClick={state.submitting ? undefined : onClose}
            disabled={state.submitting}
            aria-label="Close dialog"
            style={{
              width: 30,
              height: 30,
              borderRadius: 8,
              border: 'none',
              background: 'transparent',
              color: 'var(--hachi-muted)',
              cursor: state.submitting ? 'not-allowed' : 'pointer',
              display: 'grid',
              placeItems: 'center',
              flexShrink: 0,
            }}
          >
            <Icon name="x" size={16} />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} noValidate>
          <div style={{ padding: '16px 22px', display: 'flex', flexDirection: 'column', gap: 14 }}>

            {/* Server name */}
            <div style={fieldWrapStyle}>
              <label htmlFor="mcp-name" style={labelStyle}>
                Server name <span aria-hidden="true" style={{ color: 'var(--hachi-danger)' }}>*</span>
              </label>
              <input
                id="mcp-name"
                type="text"
                value={state.name}
                onChange={(e) => dispatch({ type: 'set_name', value: e.target.value })}
                placeholder="e.g. github"
                disabled={state.submitting}
                aria-invalid={!!state.fieldErrors.name}
                aria-describedby={state.fieldErrors.name ? 'mcp-name-error' : undefined}
                style={fieldInputStyle(!!state.fieldErrors.name)}
                autoComplete="off"
                spellCheck={false}
              />
              {state.fieldErrors.name && (
                <span id="mcp-name-error" style={errorTextStyle} role="alert">
                  {state.fieldErrors.name}
                </span>
              )}
              <span style={{ fontSize: 11, color: 'var(--hachi-muted)' }}>
                Letters, digits, hyphens, underscores only.
              </span>
            </div>

            {/* Transport selector */}
            <div style={fieldWrapStyle}>
              <span style={labelStyle}>
                Transport <span aria-hidden="true" style={{ color: 'var(--hachi-danger)' }}>*</span>
              </span>
              <div style={{ display: 'flex', gap: 8 }}>
                {(['stdio', 'sse', 'http'] as McpTransport[]).map((t) => {
                  const active = state.transport === t
                  return (
                    <button
                      key={t}
                      type="button"
                      onClick={() => dispatch({ type: 'set_transport', value: t })}
                      disabled={state.submitting}
                      style={{
                        flex: 1,
                        height: 34,
                        borderRadius: 8,
                        border: active
                          ? '1.5px solid var(--hachi-trust)'
                          : '0.5px solid var(--hachi-line)',
                        background: active ? 'var(--hachi-trust-tint)' : 'var(--hachi-canvas)',
                        color: active ? 'var(--hachi-trust)' : 'var(--hachi-muted)',
                        font: `${active ? 600 : 400} 13px var(--font-mono)`,
                        cursor: state.submitting ? 'not-allowed' : 'pointer',
                        transition: 'all var(--dur-fast) var(--ease)',
                      }}
                    >
                      {t}
                    </button>
                  )
                })}
              </div>
              <span style={{ fontSize: 11, color: 'var(--hachi-muted)' }}>
                {isStdio
                  ? 'stdio — launches a local process via command + args.'
                  : state.transport === 'sse'
                  ? 'SSE — connects to a server-sent events endpoint.'
                  : 'HTTP — connects to a streamable HTTP endpoint.'}
              </span>
            </div>

            {/* ---- stdio-only fields ---- */}
            {isStdio && (
              <>
                {/* Command */}
                <div style={fieldWrapStyle}>
                  <label htmlFor="mcp-command" style={labelStyle}>
                    Command <span aria-hidden="true" style={{ color: 'var(--hachi-danger)' }}>*</span>
                  </label>
                  <select
                    id="mcp-command"
                    value={state.command}
                    onChange={(e) =>
                      dispatch({ type: 'set_command', value: e.target.value as McpCommand })
                    }
                    disabled={state.submitting}
                    style={{
                      ...fieldInputStyle(false),
                      appearance: 'auto',
                      cursor: 'pointer',
                    }}
                  >
                    {ALLOWED_MCP_COMMANDS.map((cmd) => (
                      <option key={cmd} value={cmd}>
                        {cmd}
                      </option>
                    ))}
                  </select>
                  <span style={{ fontSize: 11, color: 'var(--hachi-muted)' }}>
                    Launcher executable. Only these commands are permitted for security.
                  </span>
                </div>

                {/* Args */}
                <div style={fieldWrapStyle}>
                  <label htmlFor="mcp-args" style={labelStyle}>
                    Args <span aria-hidden="true" style={{ color: 'var(--hachi-danger)' }}>*</span>
                  </label>
                  <input
                    id="mcp-args"
                    type="text"
                    value={state.args}
                    onChange={(e) => dispatch({ type: 'set_args', value: e.target.value })}
                    placeholder="e.g. -y @modelcontextprotocol/server-github"
                    disabled={state.submitting}
                    aria-invalid={!!state.fieldErrors.args}
                    aria-describedby={state.fieldErrors.args ? 'mcp-args-error' : undefined}
                    style={{
                      ...fieldInputStyle(!!state.fieldErrors.args),
                      fontFamily: 'var(--font-mono)',
                      fontSize: 12,
                    }}
                    autoComplete="off"
                    spellCheck={false}
                  />
                  {state.fieldErrors.args && (
                    <span id="mcp-args-error" style={errorTextStyle} role="alert">
                      {state.fieldErrors.args}
                    </span>
                  )}
                  <span style={{ fontSize: 11, color: 'var(--hachi-muted)' }}>
                    Shell metacharacters are not allowed.
                  </span>
                </div>

                {/* Env vars (optional) */}
                <div style={fieldWrapStyle}>
                  <span style={labelStyle}>Environment variables (optional)</span>
                  <span style={{ fontSize: 11, color: 'var(--hachi-muted)', marginTop: -4 }}>
                    Plain config only — secret/token/key/auth names are rejected. Use SecretStore for credentials.
                  </span>

                  {hasEnvPairs && (
                    <div
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 4,
                        background: 'var(--hachi-canvas)',
                        border: '0.5px solid var(--hachi-line)',
                        borderRadius: 8,
                        padding: '6px 10px',
                      }}
                    >
                      {Object.entries(state.envVars).map(([k, v]) => (
                        <div
                          key={k}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 8,
                            fontSize: 12,
                            fontFamily: 'var(--font-mono)',
                          }}
                        >
                          <span style={{ flex: 1, color: 'var(--hachi-ink)' }}>
                            {k}={v}
                          </span>
                          <button
                            type="button"
                            onClick={() => dispatch({ type: 'remove_env', key: k })}
                            disabled={state.submitting}
                            aria-label={`Remove env var ${k}`}
                            style={{
                              border: 'none',
                              background: 'transparent',
                              color: 'var(--hachi-muted)',
                              cursor: 'pointer',
                              padding: '2px 4px',
                              borderRadius: 4,
                              lineHeight: 1,
                              fontSize: 14,
                            }}
                          >
                            ×
                          </button>
                        </div>
                      ))}
                    </div>
                  )}

                  {state.fieldErrors.envVars && (
                    <span style={errorTextStyle} role="alert">
                      {state.fieldErrors.envVars}
                    </span>
                  )}

                  <div style={{ display: 'flex', gap: 6 }}>
                    <input
                      type="text"
                      value={state.envKey}
                      onChange={(e) => dispatch({ type: 'set_env_key', value: e.target.value })}
                      placeholder="KEY"
                      disabled={state.submitting}
                      aria-label="Environment variable key"
                      style={{
                        ...fieldInputStyle(false),
                        flex: 1,
                        fontFamily: 'var(--font-mono)',
                        fontSize: 12,
                      }}
                      autoComplete="off"
                      spellCheck={false}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault()
                          const result = validateMcpServerInput({
                            name: state.name,
                            transport: state.transport,
                            command: state.command,
                            args: state.args,
                            envVars: { ...state.envVars, [state.envKey]: state.envVal },
                          })
                          if (!result.ok && result.field === 'envVars') {
                            dispatch({ type: 'set_field_error', field: 'envVars', value: result.message })
                          } else {
                            dispatch({ type: 'add_env' })
                          }
                        }
                      }}
                    />
                    <input
                      type="text"
                      value={state.envVal}
                      onChange={(e) => dispatch({ type: 'set_env_val', value: e.target.value })}
                      placeholder="value"
                      disabled={state.submitting}
                      aria-label="Environment variable value"
                      style={{
                        ...fieldInputStyle(false),
                        flex: 2,
                        fontFamily: 'var(--font-mono)',
                        fontSize: 12,
                      }}
                      autoComplete="off"
                      spellCheck={false}
                    />
                    <button
                      type="button"
                      onClick={() => {
                        const result = validateMcpServerInput({
                          name: state.name,
                          transport: state.transport,
                          command: state.command,
                          args: state.args,
                          envVars: { ...state.envVars, [state.envKey]: state.envVal },
                        })
                        if (!result.ok && result.field === 'envVars') {
                          dispatch({ type: 'set_field_error', field: 'envVars', value: result.message })
                        } else {
                          dispatch({ type: 'add_env' })
                        }
                      }}
                      disabled={state.submitting || !state.envKey.trim()}
                      aria-label="Add environment variable"
                      style={{
                        height: 36,
                        padding: '0 12px',
                        borderRadius: 8,
                        border: '0.5px solid var(--hachi-line)',
                        background: 'var(--hachi-canvas)',
                        color: 'var(--hachi-trust)',
                        font: '500 12px var(--font-body)',
                        cursor: state.submitting || !state.envKey.trim() ? 'not-allowed' : 'pointer',
                        opacity: !state.envKey.trim() ? 0.5 : 1,
                        flexShrink: 0,
                      }}
                    >
                      Add
                    </button>
                  </div>
                </div>
              </>
            )}

            {/* ---- sse/http-only fields ---- */}
            {!isStdio && (
              <>
                {/* URL */}
                <div style={fieldWrapStyle}>
                  <label htmlFor="mcp-url" style={labelStyle}>
                    URL <span aria-hidden="true" style={{ color: 'var(--hachi-danger)' }}>*</span>
                  </label>
                  <input
                    id="mcp-url"
                    type="url"
                    value={state.url}
                    onChange={(e) => dispatch({ type: 'set_url', value: e.target.value })}
                    placeholder={
                      state.transport === 'sse'
                        ? 'e.g. https://mcp.example.com/sse'
                        : 'e.g. https://mcp.example.com/mcp'
                    }
                    disabled={state.submitting}
                    aria-invalid={!!state.fieldErrors.url}
                    aria-describedby={state.fieldErrors.url ? 'mcp-url-error' : undefined}
                    style={{
                      ...fieldInputStyle(!!state.fieldErrors.url),
                      fontFamily: 'var(--font-mono)',
                      fontSize: 12,
                    }}
                    autoComplete="off"
                    spellCheck={false}
                  />
                  {state.fieldErrors.url && (
                    <span id="mcp-url-error" style={errorTextStyle} role="alert">
                      {state.fieldErrors.url}
                    </span>
                  )}
                </div>

                {/* Optional headers */}
                <div style={fieldWrapStyle}>
                  <span style={labelStyle}>Request headers (optional)</span>
                  <span style={{ fontSize: 11, color: 'var(--hachi-muted)', marginTop: -4 }}>
                    e.g. Authorization header for private endpoints.
                  </span>

                  {hasHeaderPairs && (
                    <div
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 4,
                        background: 'var(--hachi-canvas)',
                        border: '0.5px solid var(--hachi-line)',
                        borderRadius: 8,
                        padding: '6px 10px',
                      }}
                    >
                      {Object.entries(state.headers).map(([k, v]) => (
                        <div
                          key={k}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 8,
                            fontSize: 12,
                            fontFamily: 'var(--font-mono)',
                          }}
                        >
                          <span style={{ flex: 1, color: 'var(--hachi-ink)' }}>
                            {k}: {v}
                          </span>
                          <button
                            type="button"
                            onClick={() => dispatch({ type: 'remove_header', key: k })}
                            disabled={state.submitting}
                            aria-label={`Remove header ${k}`}
                            style={{
                              border: 'none',
                              background: 'transparent',
                              color: 'var(--hachi-muted)',
                              cursor: 'pointer',
                              padding: '2px 4px',
                              borderRadius: 4,
                              lineHeight: 1,
                              fontSize: 14,
                            }}
                          >
                            ×
                          </button>
                        </div>
                      ))}
                    </div>
                  )}

                  <div style={{ display: 'flex', gap: 6 }}>
                    <input
                      type="text"
                      value={state.headerKey}
                      onChange={(e) => dispatch({ type: 'set_header_key', value: e.target.value })}
                      placeholder="Header-Name"
                      disabled={state.submitting}
                      aria-label="Request header name"
                      style={{
                        ...fieldInputStyle(false),
                        flex: 1,
                        fontFamily: 'var(--font-mono)',
                        fontSize: 12,
                      }}
                      autoComplete="off"
                      spellCheck={false}
                    />
                    <input
                      type="text"
                      value={state.headerVal}
                      onChange={(e) => dispatch({ type: 'set_header_val', value: e.target.value })}
                      placeholder="value"
                      disabled={state.submitting}
                      aria-label="Request header value"
                      style={{
                        ...fieldInputStyle(false),
                        flex: 2,
                        fontFamily: 'var(--font-mono)',
                        fontSize: 12,
                      }}
                      autoComplete="off"
                      spellCheck={false}
                    />
                    <button
                      type="button"
                      onClick={() => dispatch({ type: 'add_header' })}
                      disabled={state.submitting || !state.headerKey.trim()}
                      aria-label="Add header"
                      style={{
                        height: 36,
                        padding: '0 12px',
                        borderRadius: 8,
                        border: '0.5px solid var(--hachi-line)',
                        background: 'var(--hachi-canvas)',
                        color: 'var(--hachi-trust)',
                        font: '500 12px var(--font-body)',
                        cursor: state.submitting || !state.headerKey.trim() ? 'not-allowed' : 'pointer',
                        opacity: !state.headerKey.trim() ? 0.5 : 1,
                        flexShrink: 0,
                      }}
                    >
                      Add
                    </button>
                  </div>
                </div>
              </>
            )}

            {/* Submit error */}
            {state.submitError && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 8,
                  fontSize: 12.5,
                  color: 'var(--hachi-danger-fg)',
                  background: 'var(--hachi-danger-tint)',
                  padding: '10px 12px',
                  borderRadius: 8,
                }}
                role="alert"
              >
                <Icon name="alert" size={14} style={{ marginTop: 1, flexShrink: 0 }} />
                {state.submitError}
              </div>
            )}
          </div>

          {/* Actions */}
          <div
            style={{
              display: 'flex',
              gap: 10,
              padding: '0 22px 22px',
            }}
          >
            <Button variant="secondary" onClick={onClose} disabled={state.submitting} style={{ flex: 1, height: 42 }}>
              Cancel
            </Button>
            <Button variant="primary" type="submit" loading={state.submitting} style={{ flex: 1, height: 42 }}>
              Register server
            </Button>
          </div>
        </form>
    </Modal>
  )
}

// ---- Add MCP affordance -------------------------------------------------

interface AddMcpRowProps {
  onAdd: () => void
}

function AddMcpRow({ onAdd }: AddMcpRowProps) {
  return (
    <button
      type="button"
      className="hachi-ghost-icon-btn-bg"
      onClick={onAdd}
      aria-label="Add MCP server"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '11px 16px',
        borderWidth: '0.5px 0 0 0',
        borderStyle: 'solid',
        borderColor: 'var(--hachi-line)',
        cursor: 'pointer',
        transition: 'background var(--dur-fast) var(--ease)',
        color: 'var(--hachi-trust)',
        width: '100%',
        textAlign: 'left',
        font: '500 13px var(--font-body)',
      }}
    >
      <Icon name="plus" size={15} style={{ color: 'var(--hachi-trust)' }} />
      Add MCP server
    </button>
  )
}

// ---- Integration card wrapper with action status ------------------------

interface IntCardWithStatusProps {
  integration: Integration
}

function IntCardWithStatus({ integration: i }: IntCardWithStatusProps) {
  const [, forceUpdate] = useReducer((x: number) => x + 1, 0)
  const [showCredDialog, setShowCredDialog] = useState(false)

  useEffect(() => {
    return subscribeActionStatus(forceUpdate)
  }, [])

  const connectStatus = getConnectStatus(i.id)
  const disconnectStatus = getDisconnectStatus(i.id)

  // Extract auth_type and credential_fields from the extended shape if present.
  const ext = i as Partial<IntegrationExtended>
  const authType = ext.auth_type
  const credentialFields = ext.credential_fields ?? []

  async function handleConnect() {
    const result = await connectIntegration(i.id, authType, credentialFields)
    if (result === 'needs_credentials') {
      // Apikey connector with declared fields — open the credential dialog.
      setShowCredDialog(true)
    }
  }

  async function handleDisconnect() {
    await disconnectIntegration(i.id, authType, credentialFields)
  }

  return (
    <>
      <IntCard
        integration={i}
        onConnect={handleConnect}
        onDisconnect={handleDisconnect}
        connectLoading={connectStatus === 'loading'}
        connectError={connectStatus === 'error'}
        disconnectLoading={disconnectStatus === 'loading'}
        disconnectError={disconnectStatus === 'error'}
      />
      {showCredDialog && credentialFields.length > 0 && (
        <CredentialDialog
          connectorId={i.id}
          connectorName={i.name}
          fields={credentialFields}
          connectorSource={(i as Partial<IntegrationExtended>).source ?? null}
          onClose={() => setShowCredDialog(false)}
          onSaved={() => {
            setShowCredDialog(false)
            useStore.getState().showToast?.(`${i.name} credentials saved`, 'success')
          }}
        />
      )}
    </>
  )
}

// ---- Main screen --------------------------------------------------------

function Integrations() {
  const integrations = useStore((s) => s.integrations)
  const loadedIntegrations = useStore((s) => s.loaded.integrations)
  const mcpServers = useStore((s) => s.mcpServers)
  const mcpTools = useStore((s) => s.mcpTools)
  const operator = useStore((s) => s.operator)
  const [showAddMcp, setShowAddMcp] = useState(false)

  useEffect(() => {
    void loadIntegrations()
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* page header */}
      <div
        className="hachi-int-header"
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
          Integrations
        </h1>
        <span style={{ fontSize: 13, color: 'var(--hachi-muted)' }}>
          what Hachi can reach
        </span>
      </div>

      {/* scrollable body */}
      <div
        className="hachi-scroll hachi-int-body"
        style={{ flex: 1, overflow: 'auto', padding: '24px 32px 64px' }}
      >
        <div
          style={{
            maxWidth: 820,
            margin: '0 auto',
            display: 'flex',
            flexDirection: 'column',
            gap: 24,
          }}
        >
          {/* ---- Tavily fallback notice (C-SEARCHFALLBACK) ---- */}
          {integrations.some((i) => (i as Partial<IntegrationExtended>).fallback_active) && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '10px 14px',
                borderRadius: 10,
                background: 'var(--hachi-working-tint)',
                border: '0.5px solid var(--hachi-working)',
                fontSize: 13,
                color: 'var(--hachi-working-fg)',
              }}
              role="status"
            >
              <Icon name="alert" size={15} style={{ flexShrink: 0 }} />
              Using Playwright fallback — Tavily not reachable. Configure Tavily below to restore full web search.
            </div>
          )}

          {/* ---- Your accounts ---- */}
          <div>
            <h2
              style={{
                margin: '0 0 12px',
                fontFamily: 'var(--font-display)',
                fontWeight: 500,
                fontSize: 15,
                color: 'var(--hachi-muted)',
              }}
            >
              Your accounts
            </h2>
            {!loadedIntegrations ? (
              <PendingCard label="Loading integrations…" />
            ) : integrations.length === 0 ? (
              <div
                style={{
                  background: 'var(--hachi-surface)',
                  border: '0.5px solid var(--hachi-line)',
                  borderRadius: 16,
                }}
              >
                <NoIntegrations />
              </div>
            ) : (
              <div
                className="hachi-int-grid"
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: 12,
                }}
              >
                {integrations.map((i) => (
                  <IntCardWithStatus key={i.id} integration={i} />
                ))}
              </div>
            )}
          </div>

          {/* ---- MCP servers ---- */}
          <div>
            <h2
              style={{
                margin: '0 0 12px',
                fontFamily: 'var(--font-display)',
                fontWeight: 500,
                fontSize: 15,
                color: 'var(--hachi-muted)',
              }}
            >
              MCP servers — tools Hachi can call
            </h2>
            <div
              style={{
                background: 'var(--hachi-surface)',
                border: '0.5px solid var(--hachi-line)',
                borderRadius: 16,
                overflow: 'hidden',
              }}
            >
              {/* table header */}
              <div
                className="hachi-mcp-table-header"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 13,
                  padding: '11px 16px',
                  borderBottom: '0.5px solid var(--hachi-line)',
                  fontSize: 11.5,
                  color: 'var(--hachi-muted)',
                }}
              >
                <span style={{ flex: 1, minWidth: 0 }}>Server</span>
                <span style={{ width: 96, flexShrink: 0 }}>Status</span>
                <span style={{ width: 52, flexShrink: 0, textAlign: 'right' }}>
                  Tools
                </span>
                <span style={{ width: 64, flexShrink: 0 }}>Transport</span>
                <span style={{ width: 64, flexShrink: 0, textAlign: 'right' }}>
                  Uptime
                </span>
                <span style={{ width: 40, flexShrink: 0 }}>Enabled</span>
                <span style={{ width: 32, flexShrink: 0 }}></span>
              </div>

              {mcpServers.length === 0 ? (
                <NoMcpServers />
              ) : (
                mcpServers.map((s, idx) => (
                  <McpServerRow
                    key={s.name}
                    server={s}
                    isLast={idx === mcpServers.length - 1}
                  />
                ))
              )}

              {/* add MCP affordance */}
              <AddMcpRow onAdd={() => setShowAddMcp(true)} />
            </div>
          </div>

          {/* ---- Tool inventory (operator only) ---- */}
          {operator && (
            <div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 9,
                  marginBottom: 12,
                }}
              >
                <h2
                  style={{
                    margin: 0,
                    fontFamily: 'var(--font-display)',
                    fontWeight: 500,
                    fontSize: 15,
                    color: 'var(--hachi-muted)',
                  }}
                >
                  Tool inventory
                </h2>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 500,
                    color: 'var(--hachi-trust)',
                    background: 'var(--hachi-trust-tint)',
                    padding: '3px 9px',
                    borderRadius: 999,
                  }}
                >
                  operator
                </span>
              </div>
              <div
                style={{
                  background: 'var(--hachi-surface)',
                  border: '0.5px solid var(--hachi-line)',
                  borderRadius: 16,
                  padding: '6px 18px',
                }}
              >
                {mcpTools.length === 0 ? (
                  <div
                    style={{
                      padding: '24px 0',
                      fontSize: 13,
                      color: 'var(--hachi-muted)',
                      textAlign: 'center',
                    }}
                  >
                    No tools in inventory.
                  </div>
                ) : (
                  mcpTools.map((t, idx) => (
                    <McpToolRow
                      key={t.name}
                      tool={t}
                      isLast={idx === mcpTools.length - 1}
                    />
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Add MCP dialog (rendered at root level to escape overflow:hidden) */}
      {showAddMcp && <AddMcpDialog onClose={() => setShowAddMcp(false)} />}
    </div>
  )
}

export const Route = createFileRoute('/integrations')({
  component: Integrations,
})
