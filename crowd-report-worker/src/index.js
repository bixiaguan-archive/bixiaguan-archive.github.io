const MAX_ORIGINAL_LENGTH = 500;
const MAX_SUGGESTION_LENGTH = 300;
const MAX_COMMENT_LENGTH = 1000;

function json(data, status, origin) {
  return new Response(JSON.stringify(data), {
    status: status || 200,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      ...corsHeaders(origin)
    }
  });
}

function corsHeaders(origin) {
  return {
    'access-control-allow-origin': origin || 'null',
    'access-control-allow-methods': 'POST, OPTIONS',
    'access-control-allow-headers': 'content-type',
    'vary': 'Origin'
  };
}

function allowedOrigin(request, env) {
  const origin = request.headers.get('Origin') || '';
  return origin === env.SITE_ORIGIN ? origin : '';
}

function trimmedString(value, maxLength) {
  return typeof value === 'string' ? value.trim().slice(0, maxLength) : '';
}

async function hashIp(request, env) {
  const ip = request.headers.get('CF-Connecting-IP') || '';
  if (!ip || !env.IP_HASH_SALT) return null;
  const bytes = new TextEncoder().encode(env.IP_HASH_SALT + ':' + ip);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest)).map(function(byte) {
    return byte.toString(16).padStart(2, '0');
  }).join('');
}

async function verifyTurnstile(token, request, env) {
  if (!env.TURNSTILE_SECRET) return true;
  if (!token) return false;
  const form = new FormData();
  form.append('secret', env.TURNSTILE_SECRET);
  form.append('response', token);
  form.append('remoteip', request.headers.get('CF-Connecting-IP') || '');
  const response = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', {
    method: 'POST', body: form
  });
  const data = await response.json();
  return data.success === true;
}

async function isRateLimited(ipHash, env) {
  if (!ipHash) return false;
  const result = await env.DB.prepare(
    "SELECT COUNT(*) AS count FROM reports WHERE ip_hash = ? AND created_at >= datetime('now', '-1 hour')"
  ).bind(ipHash).first();
  return Number(result && result.count) >= 8;
}

export default {
  async fetch(request, env) {
    const origin = allowedOrigin(request, env);
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: origin ? 204 : 403, headers: corsHeaders(origin) });
    }
    if (!origin) return json({ error: 'Origin not allowed.' }, 403, '');
    if (request.method !== 'POST' || new URL(request.url).pathname !== '/api/reports') {
      return json({ error: 'Not found.' }, 404, origin);
    }

    let body;
    try {
      body = await request.json();
    } catch (_) {
      return json({ error: 'Invalid JSON.' }, 400, origin);
    }

    const episode = Number(body.episode);
    const timecode = trimmedString(body.timecode, 20);
    const original = trimmedString(body.original, MAX_ORIGINAL_LENGTH);
    const suggestion = trimmedString(body.suggestion, MAX_SUGGESTION_LENGTH);
    const comment = trimmedString(body.comment, MAX_COMMENT_LENGTH);
    const anchor = body.anchor && typeof body.anchor === 'object' ? body.anchor : null;
    const sourceUrl = trimmedString(body.sourceUrl, 1000);
    if (!Number.isInteger(episode) || episode < 1 || episode > 999 || !timecode || !original || !anchor) {
      return json({ error: '缺少必要的原文定位信息。' }, 400, origin);
    }

    const turnstileOk = await verifyTurnstile(body.turnstileToken, request, env);
    if (!turnstileOk) return json({ error: '人机验证未通过，请重试。' }, 400, origin);

    const ipHash = await hashIp(request, env);
    if (await isRateLimited(ipHash, env)) {
      return json({ error: '提交过于频繁，请稍后再试。' }, 429, origin);
    }

    const id = crypto.randomUUID();
    await env.DB.prepare(
      'INSERT INTO reports (id, created_at, episode, timecode, original, suggestion, comment, anchor_json, source_url, ip_hash) VALUES (?, datetime(\'now\'), ?, ?, ?, ?, ?, ?, ?, ?)'
    ).bind(id, episode, timecode, original, suggestion || null, comment || null, JSON.stringify(anchor), sourceUrl || null, ipHash).run();

    return json({ ok: true, id: id }, 201, origin);
  }
};
