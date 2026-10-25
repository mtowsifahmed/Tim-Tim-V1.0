-- Live web search keys live in the same table as the other BYOK keys.
-- 'search' is per account, so one user's Tavily key is never used for anyone else.
alter table public.api_keys drop constraint if exists api_keys_capability_check;
alter table public.api_keys add constraint api_keys_capability_check
  check (capability in ('llm', 'stt', 'tts', 'search'));
