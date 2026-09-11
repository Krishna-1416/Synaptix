-- Apply this migration in the Supabase SQL editor before deploying the API.
-- It extends the existing inspections table; it does not create a duplicate table.

alter table public.inspections add column if not exists user_id uuid references auth.users(id) on delete cascade;

-- Preserve existing ownership where the legacy column was populated.
update public.inspections
set user_id = inspector_id
where user_id is null and inspector_id is not null;

create index if not exists inspections_user_id_idx on public.inspections(user_id);

alter table public.profiles enable row level security;
alter table public.inspections enable row level security;

create policy "users can read their own profile"
on public.profiles for select
using (id = auth.uid());

create policy "users can read their own inspections"
on public.inspections for select
using (user_id = auth.uid());

create policy "users can insert their own inspections"
on public.inspections for insert
with check (user_id = auth.uid());

create policy "users can update their own inspections"
on public.inspections for update
using (user_id = auth.uid())
with check (user_id = auth.uid());

create policy "users can delete their own inspections"
on public.inspections for delete
using (user_id = auth.uid());
