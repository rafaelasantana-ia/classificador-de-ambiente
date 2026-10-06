// Paste this file in the Supabase Edge Function editor. No additional files needed.
const json = (body: unknown, status = 200) => Response.json(body, { status });
Deno.serve(async (req: Request) => {
  if (req.method !== 'POST') return json({ error: 'Use POST' }, 405);
  const expected = Deno.env.get('PICO_DEVICE_TOKEN');
  const supplied = req.headers.get('x-device-token') || '';
  if (!expected || expected.length < 32) return json({ error: 'Device authentication not configured' }, 503);
  const digest = async (value: string) => new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value)));
  const [a,b] = await Promise.all([digest(expected),digest(supplied)]);
  let mismatch = 0; for(let i=0;i<a.length;i++) mismatch |= a[i]^b[i];
  if (mismatch) return json({ error: 'Unauthorized device' }, 401);
  if (Number(req.headers.get('content-length')) > 1024) return json({ error: 'Payload too large' }, 413);
  let reading;
  try { const raw = await req.text(); if(raw.length > 1024) return json({ error: 'Payload too large' },413); reading = JSON.parse(raw); }
  catch { return json({ error: 'Invalid JSON' }, 400); }
  if (!reading || typeof reading !== 'object') return json({ error: 'Invalid reading' },400);
  const { temperatura_c: t, umidade_pct: h, presenca: p, classe, classifier } = reading;
  if (!Number.isFinite(t) || t<0 || t>50 || !Number.isFinite(h) || h<0 || h>100 || ![0,1].includes(p) || !['normal','presenca','alerta','critico'].includes(classe) || !['tree','rules'].includes(classifier)) return json({ error: 'Invalid reading' },400);
  const url = Deno.env.get('SUPABASE_URL'), key = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
  if (!url || !key) return json({ error: 'Database not configured' },503);
  try {
    const response = await fetch(`${url}/rest/v1/readings`, {
      method: 'POST', headers: { apikey: key, Authorization: `Bearer ${key}`, 'Content-Type': 'application/json', Prefer: 'return=minimal' },
      body: JSON.stringify({ device_id:'pico-01', temperatura_c:t, umidade_pct:h, presenca:p, classe, classifier }),
    });
    if (!response.ok) { console.error('Insert failed', response.status); return json({ error:'Failed to save reading' },502); }
    return json({ ok:true },201);
  } catch { return json({ error:'Database unavailable' },502); }
});
