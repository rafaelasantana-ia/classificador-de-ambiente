const url = import.meta.env.VITE_SUPABASE_URL;
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;
export async function fetchReadings(signal) {
  if (!url || !key) throw new Error('Configure a URL e a chave pública do Supabase em .env.local.');
  const response = await fetch(`${url}/rest/v1/readings?select=*&device_id=eq.pico-01&order=id.desc&limit=1000`, { headers: {apikey:key}, signal });
  if(!response.ok) {
    if(response.status===404) throw new Error('Crie a tabela readings no SQL Editor do Supabase usando o arquivo de configuração do projeto.');
    throw new Error(`Supabase retornou HTTP ${response.status}. Confira a chave pública e as permissões da tabela.`);
  }
  return (await response.json()).reverse().map(row=>({...row,sample:row.id,time:new Date(row.received_at).toLocaleString('pt-BR')}));
}
