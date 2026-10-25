-- Tim-Tim schema. Run in Supabase SQL editor (or `supabase db push`).
create extension if not exists vector;
create extension if not exists pgcrypto;

-- ───────────── users ─────────────
create table public.users (
  id          uuid primary key references auth.users(id) on delete cascade,
  email       text not null unique,
  role        text not null default 'free' check (role in ('owner','moderator','pro','free')),
  plan        text not null default 'free' check (plan in ('free','pro')),
  granted_by  uuid references public.users(id),
  granted_at  timestamptz,
  created_at  timestamptz not null default now()
);
-- Exactly one owner, ever.
create unique index one_owner on public.users ((role)) where role = 'owner';

-- Owner row cannot be demoted or deleted by any code path (including the backend).
create function public.protect_owner() returns trigger language plpgsql as $$
begin
  if tg_op = 'DELETE' and old.role = 'owner' then
    raise exception 'owner row cannot be deleted';
  end if;
  if tg_op = 'UPDATE' and old.role = 'owner' and new.role <> 'owner' then
    raise exception 'owner row cannot be demoted';
  end if;
  return coalesce(new, old);
end $$;
create trigger protect_owner_trg before update or delete on public.users
  for each row execute function public.protect_owner();

-- Every new auth user gets a row; the owner email is seeded here.
create function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.users (id, email, role)
  values (new.id, lower(new.email),
          case when lower(new.email) = 'm.towsifoffical2013@gmail.com' then 'owner' else 'free' end)
  on conflict (id) do nothing;
  return new;
end $$;
create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();

-- ───────────── per-user data ─────────────
create table public.settings (
  user_id    uuid primary key references public.users(id) on delete cascade,
  persona    jsonb not null default '{}'::jsonb,   -- tone, humor, formality, voice persona, orb figure/colors, theme
  updated_at timestamptz not null default now()
);

create table public.memory_facts (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references public.users(id) on delete cascade,
  fact       text not null,
  scope      text not null default 'global',       -- global | research | coding | creative | planner
  embedding  vector(768),                           -- dimension must match your embedding provider
  created_at timestamptz not null default now()
);
create index memory_facts_user on public.memory_facts(user_id);
create index memory_facts_vec on public.memory_facts using hnsw (embedding vector_cosine_ops);

create table public.usage_daily (
  user_id uuid not null references public.users(id) on delete cascade,
  day     date not null,
  turns   int  not null default 0,
  primary key (user_id, day)
);

-- Encrypted BYOK keys. Ciphertext only; encrypted by the backend (Fernet), never returned in full.
create table public.api_keys (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references public.users(id) on delete cascade,
  capability  text not null check (capability in ('llm','stt','tts')),
  provider    text not null,
  key_cipher  text not null,
  last4       text not null,
  created_at  timestamptz not null default now(),
  unique (user_id, capability)                      -- one active key per capability
);

create table public.admin_audit_log (
  id         bigserial primary key,
  actor_id   uuid not null references public.users(id),
  target_id  uuid not null references public.users(id),
  action     text not null,                         -- grant_pro | revoke_pro | add_moderator | remove_moderator
  detail     jsonb not null default '{}'::jsonb,
  at         timestamptz not null default now()
);

create table public.automation_log (
  id         bigserial primary key,
  user_id    uuid not null references public.users(id) on delete cascade,
  agent      text not null,
  skill      text not null,
  args       jsonb not null default '{}'::jsonb,
  status     text not null default 'proposed',      -- proposed | confirmed | done | failed | undone
  at         timestamptz not null default now()
);

-- Rotation bookkeeping (backend only).
create table public.provider_usage_daily (
  provider text not null, capability text not null, day date not null,
  calls int not null default 0,
  primary key (provider, capability, day)
);
create table public.provider_state (
  provider text not null, capability text not null,
  exhausted_until timestamptz,
  primary key (provider, capability)
);

-- Atomic free-tier cap: returns the new count, or -1 if the cap is already reached.
create function public.consume_turn(p_user uuid, p_cap int) returns int
language plpgsql as $$
declare t int;
begin
  insert into public.usage_daily as u (user_id, day, turns)
  values (p_user, (now() at time zone 'utc')::date, 1)
  on conflict (user_id, day) do update set turns = u.turns + 1
    where u.turns < p_cap
  returning turns into t;
  return coalesce(t, -1);
end $$;

create function public.match_memory(p_user uuid, p_embedding vector(768), p_k int default 5)
returns table (id uuid, fact text, similarity float)
language sql stable as $$
  select id, fact, 1 - (embedding <=> p_embedding)
  from public.memory_facts where user_id = p_user and embedding is not null
  order by embedding <=> p_embedding limit p_k
$$;
