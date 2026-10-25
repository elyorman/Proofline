import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { delimiter } from 'node:path';

const root = fileURLToPath(new URL('../../../', import.meta.url));
const python = process.env.PROOFLINE_PYTHON;
// Build tooling only. Every case command must carry --replay: never a live model.
for (const args of [
  ['-m', 'engine.cli', 'generate', '--script', 'engine/scripts/planted/m01.yaml', '--out', 'data/m01'],
  ['-m', 'orchestration.cli', 'run', '--mode', 'studio', '--match', 'm01',
    '--replay', 'tests/fixtures/studio/m01'],
  // One take everywhere: the three agents' side of the comparison is the Studio take's own
  // 63' case, the one the fan surface shows, not a separate recording.
  ['-c', "import json; d = json.load(open('runs/studio/m01/ledger.json')); "
    + "f = next(f for f in d['case_files'] if f['case']['case_id'] == 'case-m01-063-pressure_shift'); "
    + "open('runs/case-m01-063-pressure_shift-A.json', 'w').write(json.dumps(f, indent=2) + '\\n')"],
  ['-m', 'orchestration.cli', 'case', '--match', 'm01', '--minute', '63', '--variant', 'B',
    '--replay', 'tests/fixtures/cases/m01-063-B'],
  ['surfaces/web/scripts/export_web_replay.py', '--source', 'data/m01', '--match', 'm01',
    '--out', 'surfaces/web/public/fixtures/m01', '--studio-ledger', 'runs/studio/m01/ledger.json',
    '--answers', 'tests/fixtures/questions/m01/A/answers.jsonl',
    '--case-files', 'runs/case-m01-063-pressure_shift-A.json', 'runs/case-m01-063-pressure_shift-B.json'],
  // The evaluation tab's numbers, from the saved records only.
  ['surfaces/web/scripts/export_scoreboard.py'],
]) {
  const result = spawnSync(python || 'uv', [...(python ? ['-B'] : ['run', 'python']), ...args], {
    cwd: root, stdio: 'inherit',
    env: { ...process.env, PYTHONPATH: [root, process.env.PYTHONPATH].filter(Boolean).join(delimiter) },
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    process.exitCode = result.status ?? 1;
    break;
  }
}
