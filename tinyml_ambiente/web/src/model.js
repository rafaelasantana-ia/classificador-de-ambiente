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
  if (p <= .5) {
    if (t <= 29.85) return h <= 78.8 ? 'normal' : h <= 89.8 ? 'alerta' : 'critico';
    return t <= 35 ? h <= 90.15 ? 'alerta' : 'critico' : 'critico';
  }
  if (t <= 31.8) {
    if (h <= 80) return t <= 29.95 ? 'presenca' : 'alerta';
    return h <= 85.05 ? 'alerta' : 'critico';
  }
  return 'critico';
}
export function parseSerial(line) {
  try {
    const reading = JSON.parse(line);
    if (reading && reading.classe && valid(Number(reading.temperatura), Number(reading.umidade), Number(reading.presenca))) {
      return {
        temperatura_c: Number(reading.temperatura), umidade_pct: Number(reading.umidade),
        presenca: Number(reading.presenca), classe: reading.classe,
        ood: Boolean(reading.ood), tendencia_temp: Number(reading.tendencia_temp || 0),
        tendencia_umidade: Number(reading.tendencia_umidade || 0),
        media_temperatura: Number(reading.media_temperatura || reading.temperatura),
        media_umidade: Number(reading.media_umidade || reading.umidade),
        time: new Date().toLocaleTimeString('pt-BR')
      };
    }
  } catch {}
  const m = line.match(/T=([\d.+-]+)\s+U=([\d.+-]+)\s+IR=([01])\s+presenca=([01])\s+classe=(normal|alerta|critico|presenca)\s*$/);
  if (!m || !valid(+m[1],+m[2],+m[4]) || +m[3] === +m[4]) return null;
  return { temperatura_c: +m[1], umidade_pct: +m[2], presenca: +m[4], classe: m[5], ood: false, tendencia_temp: 0, tendencia_umidade: 0, time: new Date().toLocaleTimeString('pt-BR') };
}
