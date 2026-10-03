import rules from './data/rules.json' with { type: 'json' };
export const labels = { normal: 'Normal', alerta: 'Alerta', critico: 'Crítico', presenca: 'Presença' };
export function valid(t, h, p) { return Number.isFinite(t) && Number.isFinite(h) && t >= 0 && t <= 50 && h >= 0 && h <= 100 && (p === 0 || p === 1); }
export function exact(t, h, p) {
  if (!valid(t,h,p)) return null;
  const values = { temperatura_c: Math.fround(t), umidade_pct: Math.fround(h), presenca: p };
  return rules.rules.find(rule => {
    const results = rule.conditions.map(([key, op, limit]) => op === 'ge' ? values[key] >= limit : values[key] === limit);
    return rule.mode === 'all' ? results.every(Boolean) : results.some(Boolean);
  })?.class ?? rules.default;
}
export function tree(t,h,p) {
  if (!valid(t,h,p)) return null;
  t = Math.fround(t); h = Math.fround(h);
  if (p <= .5) return t <= 29.5 ? h <= 79 ? 'normal' : h <= 89.5 ? 'alerta' : 'critico' : 'alerta';
  return h <= 73.5 ? t <= 30 ? 'presenca' : 'critico' : 'critico';
}
export function parseSerial(line) {
  const m = line.match(/T=([\d.+-]+)\s+U=([\d.+-]+)\s+IR=([01])\s+presenca=([01])\s+classe=(normal|alerta|critico|presenca)\s*$/);
  if (!m || !valid(+m[1],+m[2],+m[4]) || +m[3] === +m[4]) return null;
  return { temperatura_c: +m[1], umidade_pct: +m[2], presenca: +m[4], classe: m[5], time: new Date().toLocaleTimeString('pt-BR') };
}
