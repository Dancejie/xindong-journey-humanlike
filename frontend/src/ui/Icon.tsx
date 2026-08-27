import type { CSSProperties, SVGProps } from 'react'

export type IconName =
  | 'heart'
  | 'arrow-right'
  | 'arrow-left'
  | 'arrow-up-right'
  | 'close'
  | 'volume-on'
  | 'volume-off'
  | 'check'
  | 'radio-empty'
  | 'plus'
  | 'status-dot'

type IconTone = 'current' | 'rose' | 'lavender'

export type IconProps = Omit<SVGProps<SVGSVGElement>, 'children' | 'name'> & {
  name: IconName
  size?: number | string
  tone?: IconTone
}

const ICON_PATHS: Record<IconName, JSX.Element> = {
  heart: <>
    <path d="M12 20.25S4.5 16.1 4.5 10.18A4.18 4.18 0 0 1 12 7.64a4.18 4.18 0 0 1 7.5 2.54c0 5.92-7.5 10.07-7.5 10.07Z" />
    <path className="ui-icon__accent" d="M7.15 9.7a2.4 2.4 0 0 1 2.24-1.48" />
  </>,
  'arrow-right': <><path d="M5 12h14" /><path d="m14.25 7.25 4.75 4.75-4.75 4.75" /></>,
  'arrow-left': <><path d="M19 12H5" /><path d="m9.75 7.25-4.75 4.75 4.75 4.75" /></>,
  'arrow-up-right': <><path d="M6.25 17.75 17.75 6.25" /><path d="M9.25 6.25h8.5v8.5" /></>,
  close: <><path d="m6.5 6.5 11 11" /><path d="m17.5 6.5-11 11" /></>,
  'volume-on': <>
    <path d="M5 9.25h3.1L12 6v12l-3.9-3.25H5z" />
    <path className="ui-icon__accent" d="M15 9a4.25 4.25 0 0 1 0 6" />
    <path d="M17.25 6.65a7.6 7.6 0 0 1 0 10.7" />
  </>,
  'volume-off': <>
    <path d="M5 9.25h3.1L12 6v6" />
    <path d="M10.5 16.7 8.1 14.75H5v-3" />
    <path className="ui-icon__accent" d="m4.75 4.75 14.5 14.5" />
  </>,
  check: <path d="m5.75 12.3 4.05 4.05 8.45-8.7" />,
  'radio-empty': <circle cx="12" cy="12" r="7.25" />,
  plus: <><path d="M12 5.25v13.5" /><path d="M5.25 12h13.5" /></>,
  'status-dot': <circle className="ui-icon__accent ui-icon__fill" cx="12" cy="12" r="4.25" />,
}

export function Icon({ name, size = 20, tone = 'current', className = '', style, ...props }: IconProps) {
  const toneValue = tone === 'rose' ? 'var(--rose)' : tone === 'lavender' ? 'var(--lavender)' : 'currentColor'
  return (
    <svg
      {...props}
      className={`ui-icon ui-icon--${name} ${className}`.trim()}
      style={{ '--icon-accent': toneValue, ...style } as CSSProperties}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {ICON_PATHS[name]}
    </svg>
  )
}
