// Write dist/staticwebapp.config.json: the security headers Static Web Apps serves with every
// page. The page loads nothing from elsewhere; its only other origin is the live API, which
// differs per environment, so it is passed in at deploy time.
//   node surfaces/web/scripts/swa_config.mjs <live API url> <dist dir>
import { writeFileSync } from 'node:fs';
import { join } from 'node:path';

const [api, dist] = process.argv.slice(2);
const apiOrigin = api ? new URL(api).origin : '';
const csp = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline'", // React sets inline style attributes on the pitch and charts
  "img-src 'self' data:",
  "font-src 'self' data:",
  `connect-src 'self'${apiOrigin ? ` ${apiOrigin}` : ''}`,
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join('; ');
const config = {
  globalHeaders: {
    'Content-Security-Policy': csp,
    'X-Frame-Options': 'DENY',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
  },
};
writeFileSync(join(dist, 'staticwebapp.config.json'), `${JSON.stringify(config, null, 2)}\n`);
console.log(`staticwebapp.config.json written, live API ${apiOrigin || 'none'}`);
