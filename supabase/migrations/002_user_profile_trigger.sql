-- ============================================================================
-- Migration: 002_user_profile_trigger.sql
-- Description: Automated, idempotent user profile creation & robust RLS policies
-- Author: Senior Backend Architect
-- ============================================================================

-- 1. Create SECURITY DEFINER trigger function to automatically create a profile
--    whenever a user is created in auth.users (Google OAuth, Email/Password, etc.)
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
declare
  raw_role text;
  normalized_role text;
  extracted_name text;
begin
  -- Extract name from user metadata, falling back to email prefix
  extracted_name := coalesce(
    new.raw_user_meta_data->>'full_name',
    new.raw_user_meta_data->>'name',
    split_part(new.email, '@', 1),
    'Enforcement Officer'
  );

  -- Extract and normalize role
  raw_role := lower(trim(coalesce(new.raw_user_meta_data->>'role', 'inspector')));
  if raw_role in ('admin', 'administrator') then
    normalized_role := 'admin';
  else
    normalized_role := 'inspector';
  end if;

  -- Upsert profile row safely
  insert into public.profiles (id, full_name, role)
  values (new.id, extracted_name, normalized_role)
  on conflict (id) do update set
    full_name = coalesce(profiles.full_name, excluded.full_name),
    role = coalesce(profiles.role, excluded.role);

  return new;
end;
$$;

-- 2. Bind trigger to auth.users table
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- 3. Ensure profiles table has Row Level Security active
alter table public.profiles enable row level security;

-- 4. Re-create and expand RLS policies on public.profiles
-- Drop legacy policies to ensure idempotent migration
drop policy if exists "users can read their own profile" on public.profiles;
drop policy if exists "users can insert their own profile" on public.profiles;
drop policy if exists "users can update their own profile" on public.profiles;

-- Policy: Authenticated users can view their own profile; Admins can view all profiles
create policy "users can read their own profile"
on public.profiles for select
using (
  id = auth.uid() 
  or exists (
    select 1 from public.profiles where id = auth.uid() and role = 'admin'
  )
);

-- Policy: Users can insert their own profile row
create policy "users can insert their own profile"
on public.profiles for insert
with check (id = auth.uid());

-- Policy: Users can update their own profile row
create policy "users can update their own profile"
on public.profiles for update
using (id = auth.uid())
with check (id = auth.uid());

-- 5. Backfill: Create missing profiles for any existing users in auth.users
--    (including user e5e5150f-ba47-4b27-bbab-f011788d9a55 from Render logs)
insert into public.profiles (id, full_name, role)
select 
  u.id,
  coalesce(
    u.raw_user_meta_data->>'full_name',
    u.raw_user_meta_data->>'name',
    split_part(u.email, '@', 1),
    'Enforcement Officer'
  ) as full_name,
  case 
    when lower(trim(coalesce(u.raw_user_meta_data->>'role', 'inspector'))) in ('admin', 'administrator') then 'admin'
    else 'inspector'
  end as role
from auth.users u
left join public.profiles p on p.id = u.id
where p.id is null
on conflict (id) do nothing;
