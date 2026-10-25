import type { CaseFile, Prediction, ToolCall, Persistence } from './types/case-file';
import { formatClock } from './replay';
import { useText, SectionTitle } from './ui';

function WindowText({ window }: { window: Prediction['window'] }) {
  return <>{formatClock(window.start)}–{formatClock(window.end)}</>;
}

export function PersistenceView({ item, label }: { item: Persistence; label?: string }) {
  const { text, metric, num } = useText();
  return <article className={`persistence ${item.holds ? 'held' : 'faded'}`}>
    <strong>{label ?? item.subject} · {text(`metric.${item.metric}`)}</strong>
    <p><WindowText window={item.window} /> · <b>{item.sigmas == null ? text('value.unset') : text('inv.sd', { value: num(item.sigmas) })}</b> · {text(item.holds ? 'inv.held' : 'inv.faded')}</p>
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

export function Investigation({ file }: { file: CaseFile }) {
  const { text, metric, num } = useText();
  const anchor = (id: string) => `hyp-${file.variant}-${file.case.case_id}-${id}`;
  const actors = [...new Set([...file.agents, ...file.refused.map(r => r.agent)])];
  const teams = [...new Set((file.case.both_teams ?? []).map(r => r.subject))];
  return <section className="investigation-view" data-case-id={file.case.case_id}>
    <div className="investigation-heading"><span className="eyebrow">{text('inv.recorded')}</span><h2>{file.case.case_id}</h2>
      <p>{text('inv.detected', { clock: file.case.detected_at ? formatClock(file.case.detected_at) : text('value.unset') })} · {text('case.window')}: <WindowText window={file.case.window} /></p>
    </div>
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
      // result is serialized by the backend; its validation-mode schema omits it.
      const result = (exam as typeof exam & { result?: string }).result;
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
