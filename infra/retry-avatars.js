const fs = require('fs'), path = require('path');
const { google } = require('googleapis');

const TOKEN_FILE       = path.join(__dirname, 'google-oauth-token.json');
const CREDENTIALS_FILE = path.join(__dirname, 'google-oauth-client.json');

const RINAT_PHOTO = fs.readFileSync('C:\\Users\\Artem\\Downloads\\T051RLPQ5AP-U05RJEFTJ90-5e0acd07545b-192.png');
const PETR_PHOTO  = fs.readFileSync('C:\\Users\\Artem\\Downloads\\T051RLPQ5AP-U05S7E6MUGY-3d6ba346c70e-192 (1).png');

function toUrlSafeBase64(buf) {
  return buf.toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

const failed = [
  { email: 'petr@cronaplatform.com',  photo: PETR_PHOTO },
  { email: 'rinat@cronasuite.com',    photo: RINAT_PHOTO },
  { email: 'rinat@cronainsights.com', photo: RINAT_PHOTO },
  { email: 'rinat@cronaoutreach.com', photo: RINAT_PHOTO },
  { email: 'rinat@cronaintel.com',    photo: RINAT_PHOTO },
  { email: 'rinat@cronacore.com',     photo: RINAT_PHOTO },
];

(async () => {
  const creds = JSON.parse(fs.readFileSync(CREDENTIALS_FILE));
  const { client_id, client_secret } = creds.installed;
  const auth = new google.auth.OAuth2(client_id, client_secret, 'http://localhost:3000');
  auth.setCredentials(JSON.parse(fs.readFileSync(TOKEN_FILE)));
  const adminDir = google.admin({ version: 'directory_v1', auth });

  for (const { email, photo } of failed) {
    process.stdout.write(`${email} ... `);
    try {
      await adminDir.users.photos.update({
        userKey: email,
        requestBody: { photoData: toUrlSafeBase64(photo), mimeType: 'IMAGE/PNG', width: 192, height: 192 },
      });
      console.log('OK');
    } catch (e) {
      console.log('FAIL:', e.response?.data?.error?.message || e.message);
    }
    await new Promise(r => setTimeout(r, 500));
  }
})();
