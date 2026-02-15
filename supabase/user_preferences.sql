-- Run this in Supabase SQL Editor.

create table if not exists public.user_preferences (
  user_id uuid primary key references auth.users(id) on delete cascade,
  preferences jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.user_preferences enable row level security;

drop policy if exists "read own preferences" on public.user_preferences;
create policy "read own preferences"
on public.user_preferences
for select
using (auth.uid() = user_id);

drop policy if exists "upsert own preferences" on public.user_preferences;
create policy "upsert own preferences"
on public.user_preferences
for insert
with check (auth.uid() = user_id);

drop policy if exists "update own preferences" on public.user_preferences;
create policy "update own preferences"
on public.user_preferences
for update
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists user_preferences_set_updated_at on public.user_preferences;
create trigger user_preferences_set_updated_at
before update on public.user_preferences
for each row execute function public.set_updated_at();
