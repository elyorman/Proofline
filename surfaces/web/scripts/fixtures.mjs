import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { delimiter } from 'node:path';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const root = fileURLToPath(new URL('../../../', import.meta.url));
const python = process.env.PROOFLINE_PYTHON;
const source = mkdtempSync(join(tmpdir(), 'proofline-web-'));
try {
  // Build tooling only: raw legacy metadata stays in a temporary directory.
  // The browser receives the allowlisted meta.json produced by the second step.
  for (const args of [
    ['-m', 'engine.cli', 'generate', '--script', 'engine/scripts/planted/m01.yaml', '--out', source],
    ['surfaces/web/scripts/export_web_replay.py', '--source', source],
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
} finally {
  rmSync(source, { recursive: true, force: true });
}
