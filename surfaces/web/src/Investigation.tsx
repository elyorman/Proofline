import type { CaseFile, Prediction, ToolCall, Persistence } from './types/case-file';
import type { InsightCard } from './types/insight-card';
import { formatClock } from './replay';
import { useText, SectionTitle } from './ui';

function WindowText({ window }: { window: Prediction['window'] }) {
  return <>{formatClock(window.start)}–{formatClock(window.end)}</>;
}

export function PersistenceView({ item, label }: { item: Persistence; label?: string }) {
  const { text, metric, num } = useText();
  return <article className={`persistence ${item.holds ? 'held' : 'faded'}`}>
    <strong>{label ?? item.subject} · {text(`metric.${item.metric}`)}</strong>
    <p><WindowText window={item.window} /> · {item.sigmas == null ? <b>{text('inv.untested')}</b>
      : <><b>{text('inv.sd', { value: num(item.sigmas) })}</b> · {text(item.holds ? 'inv.held' : 'inv.faded')}</>}</p>
    <p>{item.value == null ? text('value.unset') : metric(item.metric, item.value)} · {text('case.baseline')}: {item.baseline == null ? text('value.unset') : metric(item.metric, item.baseline)}</p>
    <p className="recorded-reason">{item.reason}</p>
    {item.tool_call_id && <code>{item.tool_call_id}</code>}
  </article>;
}

export function PredictionView({ prediction: p }: { prediction: Prediction }) {
  const { text, num } = useText();
  return <dl className="card-facts prediction">
    <div><dt>{text('case.metric')}</dt><dd>{text(`metric.${p.metric}`)}</dd></div>
    <div><dt>{text('case.subject')}</dt><dd>{p.subject}</dd></div>
    <div><dt>{text('case.direction')}</dt><dd>{text(`direction.${p.direction}`)}</dd></div>
    <div><dt>{text('inv.minimum')}</dt><dd>{num(p.min_change)} {text(`threshold.${p.threshold_kind}`)}</dd></div>
    <div><dt>{text('case.window')}</dt><dd><WindowText window={p.window} /></dd></div>
    <div><dt>{text('case.baseline')}</dt><dd>{text(`baseline.${p.compare_to}`)}</dd></div>
  </dl>;
}

function ToolMeasurement({ call }: { call?: ToolCall }) {
  const { text, num } = useText();
  if (!call) return null;
  return <div className="tool-measurement">
    {call.value != null && <span>{text('case.value')}: {num(call.value)}</span>}
    {call.baseline != null && <span>{text('case.baseline')}: {num(call.baseline)}</span>}
    {call.n_events != null && <span>{text('insights.sample', { count: call.n_events })}</span>}
    {call.error && <p>{call.error}</p>}{call.insufficient_data && <p>{call.insufficient_data}</p>}
  </div>;
}

type ExamResult = 'holds' | 'weakened' | 'refuted';
// result is serialized by the backend; its validation-mode schema omits it.
const examResult = (exam: CaseFile['cross_examinations'][number]) => (exam as typeof exam & { result?: ExamResult }).result;

export interface Funnel {
  agents: CaseFile['agents'];
  registered: number;
  refused: number;
  tested: number;
  kept: number;
  failed: number;
  counter: Record<ExamResult, number> & { unrun: number };
  outcome: CaseFile['ranking']['outcome'];
  primary?: { id: string; cause?: string };
  verdict?: string;
  support?: string | null;
}

/** The investigation at a glance, tallied from what the case file recorded: the causes
 * registered, code's verdicts on them and the counter-tests' recorded results. The Verifier's
 * verdict comes from the case's own card, when one was published. Nothing is re-scored. */
export function caseFunnel(file: CaseFile, card?: InsightCard): Funnel | undefined {
  if (!file.agents.length) return undefined;
  const results = file.cross_examinations.map(examResult);
  const tally = (result: ExamResult) => results.filter(r => r === result).length;
  const primary = file.ranking.primary;
  const verification = card?.case_id === file.case.case_id ? card.verification : undefined;
  return {
    agents: file.agents,
    registered: file.hypotheses.length,
    refused: file.refused.length,
    tested: file.tests.length,
    kept: file.tests.filter(t => t.outcome === 'supported').length,
    failed: file.tests.filter(t => t.outcome === 'failed').length,
    counter: { holds: tally('holds'), weakened: tally('weakened'), refuted: tally('refuted'), unrun: file.unrun.length },
    outcome: file.ranking.outcome,
    ...(primary ? { primary: { id: primary, cause: file.hypotheses.find(h => h.hypothesis_id === primary)?.taxonomy } } : {}),
    ...(verification ? { verdict: verification.status, support: verification.support_level } : {}),
  };
}

const share = (part: number, whole: number) => `${whole > 0 ? part / whole * 100 : 0}%`;

export function CaseFunnel({ funnel: f }: { funnel: Funnel }) {
  const { text, num } = useText();
  const exams = f.counter.holds + f.counter.weakened + f.counter.refuted;
  return <section className="case-funnel" aria-label={text('funnel.title')}>
    <ol>
      <li className="funnel-step">
        <span className="funnel-label">{text('funnel.registered')}</span>
        <b>{num(f.registered)}</b>
        <span className="funnel-bar" aria-hidden="true"><i style={{ width: share(f.registered, f.registered) }} /></span>
        <small>{f.agents.map(agent => text(`case.role.${agent}`)).join(' · ')}</small>
        {f.refused > 0 && <small>{text('funnel.refused', { count: num(f.refused) })}</small>}
      </li>
      <li className="funnel-step">
        <span className="funnel-label">{text('funnel.kept')}</span>
        <b>{text('funnel.of', { kept: num(f.kept), tested: num(f.tested) })}</b>
        <span className="funnel-bar" aria-hidden="true"><i style={{ width: share(f.kept, f.registered) }} /></span>
        <small>{text('funnel.failed', { count: num(f.failed) })}</small>
      </li>
      <li className="funnel-step">
        <span className="funnel-label">{text('funnel.counter')}</span>
        <span className="funnel-counts">{(['holds', 'weakened', 'refuted'] as const).map(result =>
          <span key={result} className={result}><b>{num(f.counter[result])}</b>{text(`exam.${result}`)}</span>)}</span>
        <span className="funnel-bar" aria-hidden="true">{(['holds', 'weakened', 'refuted'] as const).map(result =>
          <i key={result} className={result} style={{ width: share(f.counter[result], exams) }} />)}</span>
        {f.counter.unrun > 0 && <small>{text('funnel.unrun', { count: num(f.counter.unrun) })}</small>}
      </li>
      <li className="funnel-step funnel-outcome">
        <span className="funnel-label">{text('funnel.outcome')}</span>
        <strong>{f.primary ? text('funnel.primary', { outcome: text(`outcome.${f.outcome}`), cause: f.primary.cause ? text(`cause.${f.primary.cause}`) : f.primary.id })
          : text(`outcome.${f.outcome}`)}</strong>
        {f.verdict && <span className={`status ${f.verdict === 'rejected' ? 'warn' : ''}`}>
          {text('funnel.verifier', { verdict: text(`status.${f.verdict}`) })}{f.support ? ` · ${text(`support.${f.support}`)}` : ''}</span>}
      </li>
    </ol>
  </section>;
}

export function Investigation({ file, card }: { file: CaseFile; card?: InsightCard }) {
  const { text, metric, num } = useText();
  const anchor = (id: string) => `hyp-${file.variant}-${file.case.case_id}-${id}`;
  const actors = [...new Set([...file.agents, ...file.refused.map(r => r.agent)])];
  const teams = [...new Set((file.case.both_teams ?? []).map(r => r.subject))];
  const funnel = caseFunnel(file, card);
  return <section className="investigation-view" data-case-id={file.case.case_id}>
    <div className="investigation-heading"><span className="eyebrow">{text('inv.recorded')}</span><h2>{file.case.case_id}</h2>
      <p>{text('inv.detected', { clock: file.case.detected_at ? formatClock(file.case.detected_at) : text('value.unset') })} · {text('case.window')}: <WindowText window={file.case.window} /></p>
    </div>
    {funnel && <CaseFunnel funnel={funnel} />}
    <SectionTitle title={text('inv.confirmation')} />
    {file.confirmation?.map((item, i) => <PersistenceView key={`${item.tool_call_id}-${i}`} item={item} />)}
    {!file.agents.length && <p className="notice-inline">{text('inv.noAgents')}</p>}
    <SectionTitle title={text('inv.bothTeams')} sub={text('inv.fromFile')} />
    <div className="both-teams">{teams.map(team => <section key={team}><h3>{team}</h3><table><thead><tr><th>{text('case.metric')}</th><th>{text('case.value')}</th><th>{text('case.baseline')}</th><th>{text('threshold.sigma')}</th></tr></thead><tbody>
      {file.case.both_teams?.filter(r => r.subject === team).map((reading, i) => <tr key={`${reading.metric}-${i}`}><th>{text(`metric.${reading.metric}`)}</th><td>{metric(reading.metric, reading.value)}</td><td>{metric(reading.metric, reading.baseline_value)}</td><td>{reading.sigmas == null ? text('value.unset') : num(reading.sigmas)}</td></tr>)}
    </tbody></table></section>)}</div>
    <SectionTitle title={text('inv.registration')} />
    <div className="specialist-columns">{actors.map(agent => <section className={`specialist agent-${agent}`} key={agent}>
      <h3>{text(`case.role.${agent}`)}</h3>
      {!file.hypotheses.some(h => h.agent === agent) && <p className="muted">{text('inv.noHypotheses')}</p>}
      {file.hypotheses.filter(h => h.agent === agent).map(h => {
        const result = file.tests.find(t => t.hypothesis_id === h.hypothesis_id);
        return <article id={anchor(h.hypothesis_id)} key={h.hypothesis_id} className="hypothesis-card">
          <code>{h.hypothesis_id}</code><h4>{h.taxonomy}</h4><PredictionView prediction={h.prediction} />
          {result && <div className={`code-verdict ${result.outcome}`}><strong>{text(`test.${result.outcome}`)} · {num(result.observed_change)} {text(`threshold.${h.prediction.threshold_kind}`)}</strong><ToolMeasurement call={file.tool_calls.find(c => c.tool_call_id === result.tool_call_id)} /><p>{result.reason}</p><code>{result.tool_call_id}</code></div>}
        </article>;
      })}
      {file.refused.filter(r => r.agent === agent).map((r, i) => <article className="refused-proposal" key={i}><span className="status warn">{text('inv.refused')}</span><h4>{r.cause}</h4><p>{r.subject} · {text(`metric.${r.metric}`)}</p><p>{r.reason}</p></article>)}
    </section>)}</div>
    <SectionTitle title={text('case.crossExam')} />
    <div className="cross-examinations">{file.cross_examinations.map((exam, i) => {
      const target = file.hypotheses.find(h => h.hypothesis_id === exam.hypothesis_id);
      const result = examResult(exam);
      return <article key={`${exam.tool_call_id}-${i}`} className={`cross-exam ${result ?? ''}`}>
        <div className="challenge-edge"><strong>{text(`case.role.${exam.challenger}`)}</strong><span aria-hidden="true">→</span><button onClick={() => document.getElementById(anchor(exam.hypothesis_id))?.scrollIntoView({ block: 'center' })}><strong>{target ? text(`case.role.${target.agent}`) : exam.hypothesis_id}</strong><code>{exam.hypothesis_id}</code></button></div>
        <span className="status">{text(exam.corollary ? 'inv.corollary' : 'inv.control')}</span>
        <PredictionView prediction={exam.counter_prediction} />
        <p><b>{text('inv.measured')}: {num(exam.observed_change)} {text(`threshold.${exam.counter_prediction.threshold_kind}`)}</b></p>
        {exam.hypothesis_change != null && <p>{text('inv.claimChange')}: {num(exam.hypothesis_change)} {text(`threshold.${exam.counter_prediction.threshold_kind}`)}</p>}
        <ToolMeasurement call={file.tool_calls.find(c => c.tool_call_id === exam.tool_call_id)} />
        <p className="recorded-reason">{exam.reason}</p><strong className="exam-result">{result ? text(`exam.${result}`) : text('value.unset')}</strong><code>{exam.tool_call_id}</code>
      </article>;
    })}</div>
    {file.unrun.map((reason, i) => <p className="notice-inline" key={i}>{text('inv.unrun')}: {reason}</p>)}
    <SectionTitle title={text('inv.synthesis')} />
    <dl className="card-facts synthesis"><div><dt>{text('case.outcome')}</dt><dd>{text(`outcome.${file.ranking.outcome}`)}</dd></div><div><dt>{text('role.primary')}</dt><dd><code>{file.ranking.primary ?? text('value.unset')}</code></dd></div><div><dt>{text('role.secondary')}</dt><dd>{file.ranking.secondary.map(id => <code key={id}>{id}</code>)}</dd></div></dl>
    <p className="recorded-reason">{file.ranking.why}</p>
    <SectionTitle title={text('inv.checkpoints')} />
    <p>{text('case.recovered')}: <b>{text(file.case.recovered_from_checkpoint ? 'value.yes' : 'value.no')}</b></p>
    <ol className="checkpoints">{file.case.checkpoints?.map((checkpoint, i) => <li key={`${checkpoint.stage}-${i}`}><strong>{text(`stage.${checkpoint.stage}`)}</strong><p>{checkpoint.note}</p><p>{text('inv.completed')}: {checkpoint.agents_completed?.map(a => text(`case.role.${a}`)).join(', ')}</p>{!!checkpoint.agents_failed?.length && <p>{text('inv.failedAgents')}: {checkpoint.agents_failed.map(a => text(`case.role.${a}`)).join(', ')}</p>}</li>)}</ol>
    <details className="tool-log"><summary>{text('inv.toolLog')} · {text('case.budget')}: {file.case.tool_calls_used} / {file.case.tool_call_budget}</summary>
      {file.tool_calls.map((call, i) => <article key={`${call.tool_call_id}-${i}`}><h4>{call.tool}</h4><code>{call.tool_call_id}</code><pre>{JSON.stringify(call.arguments, null, 2)}</pre><ToolMeasurement call={call} />{Object.keys(call.values ?? {}).length > 0 && <pre>{JSON.stringify(call.values, null, 2)}</pre>}</article>)}
    </details>
  </section>;
}
