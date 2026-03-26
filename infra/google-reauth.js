// Re-authenticates with expanded scopes (domain + user management)
// Usage: node google-reauth.js
const fs = require('fs'), http = require('http'), path = require('path');
const { google } = require('googleapis');

const CREDENTIALS_FILE = path.join(__dirname, 'google-oauth-client.json');
const TOKEN_FILE        = path.join(__dirname, 'google-oauth-token.json');

const creds = JSON.parse(fs.readFileSync(CREDENTIALS_FILE));
const { client_id, client_secret } = creds.installed;
const auth = new google.auth.OAuth2(client_id, client_secret, 'http://localhost:3000');

const SCOPES = [
  'https://www.googleapis.com/auth/admin.directory.domain',
  'https://www.googleapis.com/auth/admin.directory.user',
  'https://www.googleapis.com/auth/admin.directory.user.security',
];

const authUrl = auth.generateAuthUrl({ access_type: 'offline', scope: SCOPES, prompt: 'consent' });
console.log('Opening browser for Google OAuth...');
require('child_process').exec(`start "" "${authUrl}"`);
console.log('If browser did not open, go to:\n' + authUrl);
console.log('\nWaiting for callback on http://localhost:3000 ...');

const server = http.createServer(async (req, res) => {
  const code = new URL(req.url, 'http://localhost:3000').searchParams.get('code');
  if (!code) { res.end('Waiting...'); return; }
  res.end('<h1>Authorization complete. You can close this tab.</h1>');
  server.close();
  const { tokens } = await auth.getToken(code);
  fs.writeFileSync(TOKEN_FILE, JSON.stringify(tokens));
  console.log('\nToken saved! Scopes:', tokens.scope);
  process.exit(0);
});
server.listen(3000);
