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
  ['surfaces/web/scripts/export_web_replay.py', '--source', 'data/m01', '--match', 'm01',
    '--out', 'surfaces/web/public/fixtures/m01', '--studio-ledger', 'runs/studio/m01/ledger.json',
    '--answers', 'tests/fixtures/questions/m01/A/answers.jsonl'],
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
