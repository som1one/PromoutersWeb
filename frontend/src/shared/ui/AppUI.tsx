import type {
  AnchorHTMLAttributes,
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  PropsWithChildren,
  ReactElement,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from 'react';
import { Link, NavLink } from 'react-router-dom';

type Tone = 'neutral' | 'accent' | 'positive' | 'warning';

export function Surface({
  className = '',
  children,
}: PropsWithChildren<{ className?: string }>) {
  return <section className={`surface ${className}`.trim()}>{children}</section>;
}

export function PageIntro({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-intro">
      <div className="page-intro-copy">
        {eyebrow ? <span className="eyebrow">{eyebrow}</span> : null}
        <h1 className="page-title">{title}</h1>
        {description ? <p className="page-copy">{description}</p> : null}
      </div>
      {action ? <div className="page-intro-action">{action}</div> : null}
    </div>
  );
}

export function SectionTitle({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div className="section-title">
      <div>
        <h2>{title}</h2>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
      {action ? <div>{action}</div> : null}
    </div>
  );
}

export function StatusPill({
  tone = 'neutral',
  children,
}: PropsWithChildren<{ tone?: Tone }>) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}

export function MetricCard({
  label,
  value,
  note,
  to,
}: {
  label: string;
  value: string;
  note?: string;
  to?: string;
}) {
  const content = (
    <>
      <span>{label}</span>
      <strong>{value}</strong>
      {note ? <p>{note}</p> : null}
    </>
  );
  if (to) {
    return (
      <Link to={to} className="metric-card metric-card-link">
        {content}
      </Link>
    );
  }
  return <article className="metric-card">{content}</article>;
}

export function InfoGrid({
  items,
}: {
  items: Array<{ label: string; value: ReactNode }>;
}) {
  return (
    <div className="info-grid">
      {items.map((item) => (
        <div key={item.label} className="info-cell">
          <span>{item.label}</span>
          <strong>{item.value}</strong>
        </div>
      ))}
    </div>
  );
}

export function EmptyState({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      {description ? <p>{description}</p> : null}
    </div>
  );
}

export function AppLink({
  to,
  children,
  variant = 'secondary',
}: PropsWithChildren<{ to: string; variant?: 'primary' | 'secondary' | 'ghost' }>) {
  return (
    <Link to={to} className={`button button-${variant}`}>
      {children}
    </Link>
  );
}

export function AppButton({
  className = '',
  variant = 'primary',
  children,
  ...props
}: PropsWithChildren<
  ButtonHTMLAttributes<HTMLButtonElement> & { className?: string; variant?: 'primary' | 'secondary' | 'ghost' }
>) {
  return (
    <button {...props} className={`button button-${variant} ${className}`.trim()}>
      {children}
    </button>
  );
}

export function TextInput({
  label,
  hint,
  className = '',
  ...props
}: {
  label: string;
  hint?: string;
  className?: string;
} & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className={`field ${className}`.trim()}>
      <span className="field-label">{label}</span>
      <input {...props} className="field-input" />
      {hint ? <small className="field-hint">{hint}</small> : null}
    </label>
  );
}

export function TextArea({
  label,
  hint,
  className = '',
  ...props
}: {
  label: string;
  hint?: string;
  className?: string;
} & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <label className={`field ${className}`.trim()}>
      <span className="field-label">{label}</span>
      <textarea {...props} className="field-input field-textarea" />
      {hint ? <small className="field-hint">{hint}</small> : null}
    </label>
  );
}

export function SelectField({
  label,
  hint,
  className = '',
  children,
  ...props
}: PropsWithChildren<
  {
    label: string;
    hint?: string;
    className?: string;
  } & SelectHTMLAttributes<HTMLSelectElement>
>) {
  return (
    <label className={`field ${className}`.trim()}>
      <span className="field-label">{label}</span>
      <select {...props} className="field-input field-select">
        {children}
      </select>
      {hint ? <small className="field-hint">{hint}</small> : null}
    </label>
  );
}

export function InlineNotice({
  tone = 'neutral',
  children,
}: PropsWithChildren<{ tone?: Tone }>) {
  return <div className={`inline-notice inline-notice-${tone}`}>{children}</div>;
}

export function DetailRow({
  label,
  value,
}: {
  label: string;
  value: ReactNode;
}) {
  return (
    <div className="detail-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function Accordion({
  title,
  subtitle,
  children,
  defaultOpen = false,
}: PropsWithChildren<{
  title: string;
  subtitle?: string;
  defaultOpen?: boolean;
}>) {
  return (
    <details className="accordion" open={defaultOpen}>
      <summary className="accordion-summary">
        <div className="accordion-summary-text">
          <strong>{title}</strong>
          {subtitle ? <span>{subtitle}</span> : null}
        </div>
        <span className="accordion-chevron" aria-hidden="true">
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </span>
      </summary>
      <div className="accordion-body">{children}</div>
    </details>
  );
}

const navIcons: Record<string, ReactElement> = {
  home: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9.5L12 3l9 6.5V20a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9.5z"/>
      <path d="M9 21V12h6v9"/>
    </svg>
  ),
  routes: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 17.5L8 13l3 3 5-5 5 5"/>
      <circle cx="8" cy="7" r="2"/>
      <circle cx="18" cy="5" r="2"/>
    </svg>
  ),
  payouts: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="4" width="20" height="16" rx="2"/>
      <circle cx="12" cy="12" r="3"/>
      <path d="M12 2v2M12 20v2M2 12h2M20 12h2"/>
    </svg>
  ),
  signals: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
      <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
    </svg>
  ),
  reports: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/>
    </svg>
  ),
  audit: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
    </svg>
  ),
  profile: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="8" r="4"/>
      <path d="M20 21a8 8 0 0 0-16 0"/>
    </svg>
  ),
};

export function BottomNav({
  items,
}: {
  items: Array<{ to: string; label: string; icon?: string }>;
}) {
  return (
    <nav className="bottom-nav" aria-label="Основная навигация">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/app' || item.to === '/app/profile'}
          className={({ isActive }) => `bottom-link${isActive ? ' bottom-link-active' : ''}`}
        >
          {item.icon && navIcons[item.icon] && (
            <span className="bottom-link-icon">{navIcons[item.icon]}</span>
          )}
          <span className="bottom-link-label">{item.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

export function ChipLink({
  to,
  children,
  ...props
}: PropsWithChildren<{ to: string } & AnchorHTMLAttributes<HTMLAnchorElement>>) {
  return (
    <Link to={to} className="chip-link" {...props}>
      {children}
    </Link>
  );
}
