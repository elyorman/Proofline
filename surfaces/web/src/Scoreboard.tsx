// The evaluation tab: every number is read from src/fixtures/scoreboard.json, which
// scripts/export_scoreboard.py writes from the saved evaluation records. Nothing is computed
// here; a value is a fraction, shown as a percentage, with its interval and n.
import board from './fixtures/scoreboard.json';
import { useText } from './ui';
import type { Locale } from './i18n';

interface Estimate { name: string; value: number | null; ci_low: number | null; ci_high: number | null; n: number }
interface Run { id: string; split: string | null; variant: string; after_follow_up: boolean; metrics: Estimate[] }
interface Comparison { id: string; split: string | null; type: string; variant_a: string; variant_b: string; after_follow_up: boolean; differences: Estimate[] }
interface Seeded { id: string; model_id: string | null; catch_rate: Estimate | null; false_rejection_rate: Estimate | null }

export const scoreboard = board as unknown as { detector: Run[]; comparisons: Comparison[]; questions: Run[]; seeded: Seeded[] };

const CASE_METRICS = ['planted_recall', 'cause_precision', 'decoy_restraint'];
const QUESTION_METRICS = ['true_premise_accuracy', 'false_premise_rejection', 'false_claims_per_question', 'claim_precision'];
const RATE_PER_QUESTION = new Set(['false_claims_per_question']);

function fixed(locale: Locale, value: number, digits: number): string {
  return new Intl.NumberFormat(locale, { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
}

export function estimate(locale: Locale, e: Estimate | undefined | null, points = false): string {
  if (!e || e.value == null) return '—';
  const perQuestion = RATE_PER_QUESTION.has(e.name);
  const show = (v: number) => perQuestion ? fixed(locale, v, 2) : `${points && v > 0 ? '+' : ''}${fixed(locale, v * 100, 1)}`;
  const unit = perQuestion ? '' : points ? ' pp' : '%';
  const ci = e.ci_low != null && e.ci_high != null ? ` [${show(e.ci_low)}, ${show(e.ci_high)}]` : '';
  return `${show(e.value)}${unit}${ci} · n=${e.n}`;
}

const order = (r: { split: string | null; after_follow_up: boolean }, variant: string) =>
  `${r.split === 'heldout' ? 0 : 1}${variant}${r.after_follow_up ? 1 : 0}`;

export function Scoreboard() {
  const { text, locale } = useText();
  const rows = (runs: Run[]) => [...runs].sort((a, b) => order(a, a.variant).localeCompare(order(b, b.variant)));
  const label = (r: { split: string | null; after_follow_up: boolean }) =>
    `${text(`sb.split.${r.split ?? 'dev'}`)} · ${text(r.after_follow_up ? 'sb.after' : 'sb.first')}`;
  const table = (runs: Run[], metrics: string[]) => <div className="table-scroll"><table>
    <thead><tr><th>{text('sb.variant')}</th><th>{text('sb.scoring')}</th>{metrics.map(m => <th key={m}>{text(`sb.m.${m}`)}</th>)}</tr></thead>
    <tbody>{rows(runs).map(r => <tr key={r.id}><th>{text(`sb.variant.${r.variant}`)}</th><td>{label(r)}</td>
      {metrics.map(m => <td key={m}>{estimate(locale, r.metrics.find(e => e.name === m))}</td>)}</tr>)}</tbody>
  </table></div>;
  return <section className="scoreboard">
    <p className="muted">{text('sb.source')}</p>
    <h3>{text('sb.cases')}</h3>
    {scoreboard.detector.length ? table(scoreboard.detector, CASE_METRICS) : <p className="muted">{text('sb.none')}</p>}
    {scoreboard.comparisons.length > 0 && <><h3>{text('sb.comparisons')}</h3><div className="table-scroll"><table>
      <thead><tr><th>{text('sb.pair')}</th><th>{text('sb.scoring')}</th><th>{text('sb.metric')}</th><th>{text('sb.difference')}</th></tr></thead>
      <tbody>{[...scoreboard.comparisons].sort((a, b) => a.id.localeCompare(b.id)).map(c => c.differences.map(d => <tr key={`${c.id}-${d.name}`}>
        <th>{text(`sb.variant.${c.variant_a}`)} − {text(`sb.variant.${c.variant_b}`)}</th><td>{label(c)}</td><td>{text(`sb.m.${d.name}`)}</td><td>{estimate(locale, d, true)}</td>
      </tr>))}</tbody></table></div></>}
    {scoreboard.questions.length > 0 && <><h3>{text('sb.questions')}</h3>{table(scoreboard.questions, QUESTION_METRICS)}</>}
    {scoreboard.seeded.length > 0 && <><h3>{text('sb.verifier')}</h3><div className="table-scroll"><table>
      <thead><tr><th>{text('sb.model')}</th><th>{text('sb.catch_rate')}</th><th>{text('sb.false_rejection_rate')}</th></tr></thead>
      <tbody>{scoreboard.seeded.map(s => <tr key={s.id}><th>{s.model_id ?? '—'}</th><td>{estimate(locale, s.catch_rate)}</td><td>{estimate(locale, s.false_rejection_rate)}</td></tr>)}</tbody>
    </table></div></>}
  </section>;
}
