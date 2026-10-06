create table if not exists public.readings (
  id bigint generated always as identity primary key,
  device_id text not null check (device_id = 'pico-01'),
  temperatura_c real not null check (temperatura_c >= 0 and temperatura_c <= 50),
  umidade_pct real not null check (umidade_pct >= 0 and umidade_pct <= 100),
  presenca smallint not null check (presenca in (0,1)),
  classe text not null check (classe in ('normal','presenca','alerta','critico')),
  classifier text not null check (classifier in ('tree','rules')),
  received_at timestamptz not null default now()
);
create index if not exists readings_received_at_idx on public.readings (received_at desc);
alter table public.readings enable row level security;
revoke all on public.readings from anon, authenticated;
grant select on public.readings to anon, authenticated;
drop policy if exists "Read environmental measurements" on public.readings;
-- Deliberately public read access for the demonstration dashboard. No public writes.
create policy "Read environmental measurements" on public.readings
  for select to anon, authenticated using (device_id = 'pico-01');
