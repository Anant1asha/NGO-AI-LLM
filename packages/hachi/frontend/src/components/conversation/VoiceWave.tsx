// VoiceWave — animated bars for dictate + push-to-talk indicators.

export function VoiceWave({ height = 20, color = 'var(--hachi-brand)' }: { height?: number; color?: string }) {
  const delays = [0, 0.16, 0.32, 0.1, 0.24]
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height }} aria-hidden="true">
      {delays.map((d, i) => (
        <span
          key={i}
          style={{
            width: 3,
            height,
            borderRadius: 2,
            background: color,
            transformOrigin: 'bottom',
            animation: `hachiVoice .82s ease-in-out infinite ${d}s`,
          }}
        />
      ))}
    </div>
  )
}
