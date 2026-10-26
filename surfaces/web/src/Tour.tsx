// A guided tour for a judge arriving cold. Each step moves the replay itself (route, clock,
// tab) and highlights one area with one line of explanation. The highlight never takes the
// pointer, so the page stays usable while the tour is open; closed, nothing of it renders.
import { useEffect, useId, useRef, useState, type CSSProperties } from 'react';
import type { CaseTab } from './Analyst';
import type { RailTab } from './FanRail';
import type { Route } from './replay';
import { Icon, useText } from './ui';

export interface TourStep {
  id: string;
  route: Route;
  clock: string;
  /** Highlighted together: the box around every match that is on screen. */
  targets: string[];
  rail?: RailTab;
  caseTab?: CaseTab;
  /** Prefill Ask with a question no recording holds, for the judge to send. */
  draft?: boolean;
}

export const TOUR_STEPS: TourStep[] = [
  { id: 'card', route: 'fan', clock: '68:00', targets: ['.fan-now'], rail: 'ask' },
  { id: 'correction', route: 'fan', clock: '70:00', targets: ['.fan-now', '.fan-rail'], rail: 'earlier' },
  { id: 'ask', route: 'fan', clock: '76:00', targets: ['.fan-rail'], rail: 'ask', draft: true },
  { id: 'investigation', route: 'analyst', clock: '68:00', targets: ['.case-funnel'], caseTab: 'investigation' },
  { id: 'scoreboard', route: 'analyst', clock: '68:00', targets: ['.scoreboard'], caseTab: 'evaluation' },
  { id: 'cue', route: 'broadcast', clock: '70:30', targets: ['.cue-queue .cue-card'] },
];

/** The deep link a step leaves in the address bar, keeping the link's language if it had one. */
export function tourLink(step: TourStep, lang?: string): string {
  return `#/${step.route}?t=${step.clock}${lang ? `&lang=${lang}` : ''}`;
}

const KEY = 'proofline.tour';
type Store = Pick<Storage, 'getItem' | 'setItem'>;
const browserStore = (): Store | undefined => { try { return window.localStorage; } catch { return undefined; } };

/** Whether this browser has started or dismissed the tour. Storage may be missing or throw. */
export function tourSeen(store: Store | undefined = browserStore()): boolean {
  try { return store?.getItem(KEY) === 'seen'; } catch { return false; }
}

export function markTourSeen(store: Store | undefined = browserStore()): void {
  try { store?.setItem(KEY, 'seen'); } catch { /* private mode: the invitation just returns next visit */ }
}

export interface Box { top: number; left: number; width: number; height: number }

/** Where the step card goes: beside the highlight if there is room (left first, the side
 * away from the rail), else below or above it, else inside its lower-left corner. */
export function placeCard(target: Box | undefined, card: { width: number; height: number }, view: { width: number; height: number }, gap = 16): { top: number; left: number } {
  const clampTop = (top: number) => Math.max(gap, Math.min(view.height - card.height - gap, top));
  const clampLeft = (left: number) => Math.max(gap, Math.min(view.width - card.width - gap, left));
  if (!target) return { top: view.height - card.height - gap, left: view.width - card.width - gap };
  if (target.left - card.width - 2 * gap >= 0) return { top: clampTop(target.top), left: target.left - card.width - gap };
  if (target.left + target.width + card.width + 2 * gap <= view.width) return { top: clampTop(target.top), left: target.left + target.width + gap };
  if (target.top + target.height + card.height + 2 * gap <= view.height) return { top: target.top + target.height + gap, left: clampLeft(target.left) };
  if (target.top - card.height - 2 * gap >= 0) return { top: target.top - card.height - gap, left: clampLeft(target.left) };
  return { top: clampTop(target.top + target.height - card.height - gap), left: clampLeft(target.left + gap) };
}

const PHONE = '(max-width: 899px)';

/** The on-screen box around a step's targets, re-measured every frame while the tour is open. */
function useTargetBox(step: TourStep): Box | undefined {
  const [box, setBox] = useState<Box>();
  useEffect(() => {
    let frame = 0;
    let scrolled = false;
    let last = '';
    const measure = () => {
      const elements = step.targets.map(selector => document.querySelector(selector)).filter((e): e is HTMLElement => !!e);
      const rects = elements.map(e => e.getBoundingClientRect()).filter(r => r.width > 0 && r.height > 0);
      if (rects.length && !scrolled) {
        scrolled = true;
        elements[0].scrollIntoView({ block: matchMedia(PHONE).matches ? 'start' : 'nearest', behavior: 'smooth' });
      }
      const top = Math.max(0, Math.min(...rects.map(r => r.top)));
      const left = Math.max(0, Math.min(...rects.map(r => r.left)));
      const bottom = Math.min(innerHeight, Math.max(...rects.map(r => r.bottom)));
      const right = Math.min(innerWidth, Math.max(...rects.map(r => r.right)));
      const next = rects.length && bottom > top ? { top: Math.round(top), left: Math.round(left), width: Math.round(right - left), height: Math.round(bottom - top) } : undefined;
      const key = JSON.stringify(next ?? null);
      if (key !== last) { last = key; setBox(next); }
      frame = requestAnimationFrame(measure);
    };
    frame = requestAnimationFrame(measure);
    return () => cancelAnimationFrame(frame);
  }, [step]);
  return box;
}

export function Tour({ step, onStep, onClose }: { step: number; onStep: (step: number) => void; onClose: () => void }) {
  const { text } = useText();
  const current = TOUR_STEPS[step];
  const last = step === TOUR_STEPS.length - 1;
  const box = useTargetBox(current);
  const card = useRef<HTMLDivElement>(null);
  const next = useRef<HTMLButtonElement>(null);
  const [place, setPlace] = useState<{ top: number; left: number }>();
  const titleId = useId();
  const bodyId = useId();

  useEffect(() => { next.current?.focus(); }, []);
  // Back disables itself on the first step; keep focus inside the card.
  useEffect(() => { if (document.activeElement instanceof HTMLButtonElement && document.activeElement.disabled) next.current?.focus(); }, [step]);
  useEffect(() => {
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
    document.addEventListener('keydown', escape);
    return () => document.removeEventListener('keydown', escape);
  }, [onClose]);
  useEffect(() => {
    const element = card.current;
    if (!element || matchMedia(PHONE).matches) { setPlace(undefined); return; }
    setPlace(placeCard(box, { width: element.offsetWidth, height: element.offsetHeight }, { width: innerWidth, height: innerHeight }));
  }, [box, step]);

  const style: CSSProperties | undefined = place && { top: place.top, left: place.left };
  return <>
    {box && <div className="tour-spot" aria-hidden="true" style={{ top: box.top - 6, left: box.left - 6, width: box.width + 12, height: box.height + 12 }} />}
    <div className={`tour-card ${place ? 'placed' : ''}`} ref={card} style={style} role="dialog" aria-modal="false" aria-labelledby={titleId} aria-describedby={bodyId}
      onKeyDown={event => {
        if (event.key === 'ArrowRight' && !last) onStep(step + 1);
        if (event.key === 'ArrowLeft' && step > 0) onStep(step - 1);
      }}>
      <div className="tour-head">
        <span className="eyebrow">{text('tour.label')} · {text('tour.step', { n: step + 1, total: TOUR_STEPS.length })}</span>
        <button type="button" className="tour-close" aria-label={text('tour.close')} onClick={onClose}><Icon name="close" size={16} /></button>
      </div>
      <div className="tour-text" aria-live="polite" key={current.id}>
        <h2 id={titleId}>{text(`tour.${current.id}.title`)}</h2>
        <p id={bodyId}>{text(`tour.${current.id}.body`)}</p>
      </div>
      <div className="tour-foot">
        <span className="tour-dots" aria-hidden="true">{TOUR_STEPS.map((s, i) => <i key={s.id} className={i === step ? 'on' : i < step ? 'done' : ''} />)}</span>
        <button type="button" className="button" disabled={step === 0} onClick={() => onStep(step - 1)}>{text('tour.back')}</button>
        <button type="button" className="button primary" ref={next} onClick={() => last ? onClose() : onStep(step + 1)}>{text(last ? 'tour.done' : 'tour.next')}</button>
      </div>
    </div>
  </>;
}

/** The first-visit invitation. Starting or dismissing it is remembered in this browser. */
export function TourInvite({ onStart, onDismiss }: { onStart: () => void; onDismiss: () => void }) {
  const { text } = useText();
  return <aside className="tour-invite" aria-label={text('tour.label')}>
    <span className="tour-invite-icon" aria-hidden="true"><Icon name="tour" size={20} /></span>
    <p>{text('tour.invite')}</p>
    <div><button type="button" className="button primary" onClick={onStart}>{text('tour.start')}</button>
      <button type="button" className="button" onClick={onDismiss}>{text('tour.dismiss')}</button></div>
  </aside>;
}
