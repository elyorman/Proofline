import { Component, createContext, useContext, useMemo, type ReactNode } from 'react';
import { t, number, metricNumber, type Locale } from './i18n';

export const LocaleContext = createContext<Locale>('en');
export function useText() {
  const locale = useContext(LocaleContext);
  return useMemo(() => ({
    locale,
    text: (key: string, values?: Record<string, string | number>) => t(locale, key, values),
    num: (value: number, percent = false) => number(locale, value, percent),
    metric: (name: string, value: unknown) => metricNumber(locale, name, value),
  }), [locale]);
}

function ViewFailure({ retry }: { retry: () => void }) {
  const { text } = useText();
  return <div className="panel view-error" role="alert">
    <Empty title={text('view.error')} body={text('view.error.body')} />
    <button className="button" onClick={retry}>{text('view.retry')}</button>
  </div>;
}

export class ViewBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    return this.state.failed
      ? <ViewFailure retry={() => this.setState({ failed: false })} />
      : this.props.children;
  }
}

const icons = {
  fan: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M12 5v14M3 9h3v6H3m18-6h-3v6h3" /><circle cx="12" cy="12" r="3" /></>,
  analyst: <><path d="M5 3h11l3 3v15H5zM9 8h5M9 12h6M9 16h3" /></>,
  broadcast: <><rect x="3" y="5" width="15" height="14" rx="2" /><path d="m18 10 4-3v10l-4-3M7 9v6m4-6v6" /></>,
  overlay: <><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M6 14h12v3H6z" /></>,
  arrow: <path d="M5 12h14m-6-6 6 6-6 6" />,
  play: <path d="m8 5 11 7-11 7z" />,
  pause: <><path d="M8 5v14M16 5v14" /></>,
  reset: <><path d="M4 10a8 8 0 1 1 1 8M4 4v6h6" /></>,
  chevron: <path d="m6 9 6 6 6-6" />,
  evidence: <><path d="m4 13 5 5L20 6" /><circle cx="12" cy="12" r="10" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  globe: <><circle cx="12" cy="12" r="9" /><ellipse cx="12" cy="12" rx="4" ry="9" /><path d="M3 12h18" /></>,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v6m0-10v1" /></>,
  close: <path d="m6 6 12 12M6 18 18 6" />,
} as const;

export function Icon({ name, size = 20 }: { name: keyof typeof icons; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{icons[name]}</svg>;
}

export function Crest({ code, away = false, small = false }: { code: string; away?: boolean; small?: boolean }) {
  return <div className={`crest ${away ? 'away' : ''} ${small ? 'small' : ''}`} aria-hidden="true"><span>{code}</span></div>;
}

export function SectionTitle({ title, sub, children }: { title: string; sub?: string; children?: ReactNode }) {
  return <div className="section-heading"><div><h2>{title}</h2>{sub && <p>{sub}</p>}</div>{children}</div>;
}

export function Empty({ title, body }: { title: string; body?: string }) {
  return <div className="empty-state"><span className="empty-symbol"><Icon name="fan" size={26} /></span><h3>{title}</h3>{body && <p>{body}</p>}</div>;
}
