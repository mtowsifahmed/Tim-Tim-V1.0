-- Row Level Security. Clients (anon/authenticated roles) get the minimum;
-- the backend connects with a database role that bypasses RLS and enforces roles in code.

create function public.is_staff() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.users where id = auth.uid() and role in ('owner','moderator'))
$$;

alter table public.users                enable row level security;
alter table public.settings             enable row level security;
alter table public.memory_facts         enable row level security;
alter table public.usage_daily          enable row level security;
alter table public.api_keys             enable row level security;
alter table public.admin_audit_log      enable row level security;
alter table public.automation_log       enable row level security;
alter table public.provider_usage_daily enable row level security;
alter table public.provider_state       enable row level security;

-- users: read own row; staff read all. NO client writes (role/plan only change via backend).
create policy users_self_read  on public.users for select using (id = auth.uid());
create policy users_staff_read on public.users for select using (public.is_staff());

-- own-rows-only tables
create policy settings_own on public.settings     for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy memory_own   on public.memory_facts for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy usage_read   on public.usage_daily  for select using (user_id = auth.uid());
create policy usage_staff  on public.usage_daily  for select using (public.is_staff());
create policy autolog_read on public.automation_log for select using (user_id = auth.uid());

-- audit log: staff read only; written by backend
create policy audit_staff_read on public.admin_audit_log for select using (public.is_staff());

-- api_keys, provider_*: RLS on and NO policies => clients can never read them.
revoke all on public.api_keys, public.provider_usage_daily, public.provider_state from anon, authenticated;
revoke insert, update, delete on public.users, public.usage_daily, public.admin_audit_log, public.automation_log from anon, authenticated;
revoke all on public.users, public.settings, public.memory_facts, public.usage_daily,
              public.admin_audit_log, public.automation_log from anon;
