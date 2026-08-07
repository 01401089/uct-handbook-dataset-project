// Cloudflare Pages advanced-mode worker: gates EVERY request behind a
// verified Firebase (Google) ID token for @uct.ac.za accounts.
//
// Flow: no/invalid session cookie -> 302 /login (static page, public).
// /login signs in with Google via Firebase JS, POSTs the ID token to
// /auth/session; this worker fully verifies it (RS256 signature against
// Google's published keys, issuer, audience, expiry, email_verified,
// @uct.ac.za domain) and sets an HttpOnly cookie holding the token.
// Every subsequent request re-verifies the cookie before serving assets.
//
// Config is injected from auth/config.json by scripts/add-auth.js at
// deploy time (the __FIREBASE_PROJECT_ID__ placeholder below).

const PROJECT_ID = '__FIREBASE_PROJECT_ID__';
const PROJECT_NUMBER = '__FIREBASE_PROJECT_NUMBER__';
const LOGIN_HTML = __LOGIN_HTML__;
// Admin accounts: full access plus the /admin activity log. Admins may be
// outside the UCT domains (site owner's personal account).
const ADMIN_EMAILS = ['kkefale@gmail.com'];

// uct.ac.za itself plus any sub-domain (wf.uct.ac.za, etc.), or an admin.
function emailAllowed(email) {
  const e = String(email || '').toLowerCase();
  if (ADMIN_EMAILS.includes(e)) return true;
  const domain = e.split('@').pop();
  return domain === 'uct.ac.za' || domain.endsWith('.uct.ac.za');
}

// ---- activity log (Cloudflare KV, binding LOGS) -----------------------
// Keys are inverse-timestamped so KV's lexicographic list order is
// newest-first. Entries expire after 180 days.
function logEvent(env, ctx, request, email, event, path) {
  if (!env.LOGS || !ctx) return;
  const now = Date.now();
  const key = `log:${String(1e14 - now).padStart(14, '0')}:${crypto.randomUUID().slice(0, 8)}`;
  const entry = JSON.stringify({
    t: new Date(now).toISOString(),
    email,
    event,
    path,
    ip: request.headers.get('CF-Connecting-IP') || '',
    country: (request.cf && request.cf.country) || '',
    ua: (request.headers.get('User-Agent') || '').slice(0, 160),
  });
  ctx.waitUntil(env.LOGS.put(key, entry, { expirationTtl: 15552000 }));
}

function esc(s) {
  return String(s).replace(/[&<>"]/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

async function adminPage(env, url) {
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '300', 10) || 300, 1000);
  const rows = [];
  if (env.LOGS) {
    const list = await env.LOGS.list({ prefix: 'log:', limit });
    const values = await Promise.all(list.keys.map((k) => env.LOGS.get(k.name)));
    for (const v of values) {
      if (!v) continue;
      try { rows.push(JSON.parse(v)); } catch {}
    }
  }
  const body = rows.map((r) => `<tr>
    <td>${esc(r.t).replace('T', ' ').slice(0, 19)}</td>
    <td>${esc(r.email)}</td>
    <td class="ev-${esc(r.event)}">${esc(r.event)}</td>
    <td>${esc(r.path)}</td>
    <td>${esc(r.ip)} ${esc(r.country)}</td>
    <td class="ua">${esc(r.ua)}</td>
  </tr>`).join('');
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Activity log — UCT Faculty Handbook Explorer</title>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@300;600&family=Roboto:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root { color-scheme: light dark; }
  body { margin: 0; font: 14px/1.5 Roboto, system-ui, sans-serif;
    background: #f4f6f8; color: #14232f; }
  @media (prefers-color-scheme: dark) {
    body { background: #0d161e; color: #dbe4ea; }
    table { background: #12202b; }
    th { background: #00243A; }
    tr:nth-child(even) td { background: #16273441; }
  }
  header { background: #00243A; color: #fff; padding: 1rem 1.4rem;
    border-bottom: 3px solid #0098DB; display: flex; gap: 1rem;
    align-items: baseline; flex-wrap: wrap; }
  header h1 { font-family: Montserrat, sans-serif; font-weight: 300;
    font-size: 1.15rem; margin: 0; }
  header .uni { font-family: Montserrat, sans-serif; font-weight: 600;
    font-size: .68rem; letter-spacing: .2em; text-transform: uppercase;
    color: #0098DB; }
  header a { color: #7fcdf0; margin-left: auto; font-size: .8rem; }
  main { padding: 1.2rem 1.4rem; max-width: 90rem; margin: 0 auto; }
  .meta { opacity: .65; font-size: .8rem; margin: 0 0 .8rem; }
  input#f { width: 20rem; max-width: 100%; padding: .45rem .6rem;
    border: 1px solid #b9c6cf; border-radius: 2px; font: inherit;
    margin-bottom: .8rem; background: inherit; color: inherit; }
  table { border-collapse: collapse; width: 100%; background: #fff;
    font-size: .82rem; }
  th { background: #00243A; color: #fff; text-align: left;
    font-family: Montserrat, sans-serif; font-weight: 600;
    font-size: .7rem; letter-spacing: .08em; text-transform: uppercase;
    padding: .5rem .6rem; position: sticky; top: 0; }
  td { padding: .4rem .6rem; border-bottom: 1px solid #dde5ea40;
    vertical-align: top; }
  td.ua { opacity: .55; font-size: .72rem; max-width: 22rem;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ev-login { color: #0098DB; font-weight: 500; }
</style></head><body>
<header><img src="/uct-official-dark.svg" alt="University of Cape Town" height="26" style="align-self:center;">
<h1><b>Faculty Handbook</b> Explorer — activity log</h1>
<a href="/">back to the explorer</a></header>
<main>
<p class="meta">${rows.length} most recent events (logins and page
navigations; entries kept 180 days). Append <code>?limit=1000</code> for
more.</p>
<input id="f" placeholder="Filter (email, path, event…)" oninput="
  const q = this.value.toLowerCase();
  document.querySelectorAll('tbody tr').forEach((tr) => {
    tr.style.display = tr.textContent.toLowerCase().includes(q) ? '' : 'none';
  });">
<table><thead><tr><th>Time (UTC)</th><th>Account</th><th>Event</th>
<th>Path</th><th>IP · Country</th><th>Browser</th></tr></thead>
<tbody>${body}</tbody></table>
</main></body></html>`;
  return new Response(html, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'no-store',
    },
  });
}
const COOKIE = 'uct_session';
const JWKS_URL =
  'https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com';

let jwksCache = { keys: null, fetchedAt: 0 };

function b64urlToBytes(s) {
  s = s.replace(/-/g, '+').replace(/_/g, '/');
  const bin = atob(s.padEnd(s.length + ((4 - (s.length % 4)) % 4), '='));
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}

function decodeSegment(seg) {
  return JSON.parse(new TextDecoder().decode(b64urlToBytes(seg)));
}

async function getVerificationKey(kid) {
  const now = Date.now();
  if (!jwksCache.keys || now - jwksCache.fetchedAt > 3600_000) {
    const res = await fetch(JWKS_URL);
    if (!res.ok) return null;
    jwksCache = { keys: (await res.json()).keys, fetchedAt: now };
  }
  const jwk = jwksCache.keys.find((k) => k.kid === kid);
  if (!jwk) {
    jwksCache.fetchedAt = 0; // force refresh next time (key rotation)
    return null;
  }
  return crypto.subtle.importKey(
    'jwk', jwk,
    { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' },
    false, ['verify']
  );
}

async function verifyToken(token) {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return { reason: 'malformed token' };
    const header = decodeSegment(parts[0]);
    const payload = decodeSegment(parts[1]);
    const now = Math.floor(Date.now() / 1000);
    if (header.alg !== 'RS256') return { reason: 'unexpected algorithm' };
    if (!(payload.exp > now)) return { reason: 'token expired' };
    if (!(payload.iat < now + 300)) return { reason: 'token from the future' };
    const audOk = payload.aud === PROJECT_ID || payload.aud === PROJECT_NUMBER;
    if (!audOk) return { reason: `wrong audience (${payload.aud})` };
    const issOk =
      payload.iss === `https://securetoken.google.com/${PROJECT_ID}` ||
      payload.iss === `https://securetoken.google.com/${PROJECT_NUMBER}`;
    if (!issOk) return { reason: `wrong issuer (${payload.iss})` };
    if (!payload.sub) return { reason: 'missing subject' };
    if (payload.email_verified !== true) return { reason: 'email not verified' };
    if (!emailAllowed(payload.email)) {
      return { reason: `domain not allowed (${payload.email})` };
    }
    const key = await getVerificationKey(header.kid);
    if (!key) return { reason: 'unknown signing key' };
    const ok = await crypto.subtle.verify(
      'RSASSA-PKCS1-v1_5', key,
      b64urlToBytes(parts[2]),
      new TextEncoder().encode(parts[0] + '.' + parts[1])
    );
    return ok ? { payload } : { reason: 'bad signature' };
  } catch {
    return { reason: 'token verification error' };
  }
}

function getCookie(request, name) {
  const header = request.headers.get('Cookie') || '';
  for (const part of header.split(';')) {
    const [k, ...v] = part.trim().split('=');
    if (k === name) return v.join('=');
  }
  return null;
}

function redirectToLogin(url) {
  const next = encodeURIComponent(url.pathname + url.search);
  return Response.redirect(`${url.origin}/login?next=${next}`, 302);
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Public assets the login page needs before authentication.
    if (url.pathname === '/favicon.ico' ||
        url.pathname === '/uct-official-light.svg' ||
        url.pathname === '/uct-official-dark.svg') {
      return env.ASSETS.fetch(request);
    }

    // Public: the login page, baked into the worker (no asset layer,
    // so the pretty-URL redirect machinery can never loop it).
    if (url.pathname === '/login' || url.pathname === '/login.html') {
      return new Response(LOGIN_HTML, {
        headers: {
          'Content-Type': 'text/html; charset=utf-8',
          'Cache-Control': 'no-store',
        },
      });
    }

    // Session mint: verify the posted ID token, set the HttpOnly cookie.
    if (url.pathname === '/auth/session' && request.method === 'POST') {
      let token;
      try {
        ({ token } = await request.json());
      } catch {
        return new Response('bad request', { status: 400 });
      }
      const result = token ? await verifyToken(token) : { reason: 'no token' };
      if (!result.payload) {
        return new Response(JSON.stringify({ reason: result.reason }), {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      const payload = result.payload;
      logEvent(env, ctx, request, payload.email, 'login', url.pathname);
      const maxAge = Math.max(60, payload.exp - Math.floor(Date.now() / 1000) - 30);
      // Display name for the header: Google's name claim, else derived
      // from the email local part ("kende.kefale" -> "Kende Kefale").
      const displayName = payload.name ||
        String(payload.email).split('@')[0].split(/[._-]+/)
          .map((s) => s.charAt(0).toUpperCase() + s.slice(1)).join(' ');
      const headers = new Headers();
      headers.append('Set-Cookie',
        `${COOKIE}=${token}; Path=/; Max-Age=${maxAge}; ` +
        'HttpOnly; Secure; SameSite=Lax');
      headers.append('Set-Cookie',
        `uct_user=${encodeURIComponent(displayName)}; Path=/; ` +
        `Max-Age=${maxAge}; Secure; SameSite=Lax`);
      return new Response(null, { status: 204, headers });
    }

    if (url.pathname === '/auth/logout') {
      const headers = new Headers({ Location: `${url.origin}/login?signout=1` });
      headers.append('Set-Cookie',
        `${COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax`);
      headers.append('Set-Cookie',
        'uct_user=; Path=/; Max-Age=0; Secure; SameSite=Lax');
      return new Response(null, { status: 302, headers });
    }

    // Everything else requires a valid session.
    const session = getCookie(request, COOKIE);
    const verified = session ? await verifyToken(session) : {};
    if (verified.payload) {
      const email = String(verified.payload.email || '').toLowerCase();
      // Admin-only activity log.
      if (url.pathname === '/admin' || url.pathname.startsWith('/admin/')) {
        if (!ADMIN_EMAILS.includes(email)) {
          return new Response('forbidden', { status: 403 });
        }
        logEvent(env, ctx, request, email, 'admin-view', url.pathname);
        return adminPage(env, url);
      }
      // Log page navigations (documents only, not assets/data).
      if (request.method === 'GET' &&
          request.headers.get('Sec-Fetch-Mode') === 'navigate') {
        logEvent(env, ctx, request, email, 'page-view', url.pathname);
      }
      return env.ASSETS.fetch(request);
    }
    if (request.method === 'GET' || request.method === 'HEAD') {
      return redirectToLogin(url);
    }
    return new Response('unauthorised', { status: 401 });
  },
};
