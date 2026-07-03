-- PSAT Drift Database — Supabase schema
-- Run this once in the Supabase SQL editor on a fresh project.

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------
-- Profiles: one row per authenticated user (extends auth.users)
-- ---------------------------------------------------------------------
create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  institution text,
  created_at timestamptz not null default now()
);

create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, display_name)
  values (new.id, coalesce(new.raw_user_meta_data->>'display_name', new.email));
  return new;
end;
$$ language plpgsql security definer;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- ---------------------------------------------------------------------
-- Deployments: one row per tag deployment / uploaded file
-- ---------------------------------------------------------------------
create table public.deployments (
  id uuid primary key default gen_random_uuid(),
  deploy_id text not null,
  ptt text,
  instrument_model text,
  manufacturer text not null default 'wildlife_computers'
    check (manufacturer in ('wildlife_computers','lotek','desert_star','microwave_telemetry','other')),
  species text,
  deploy_date timestamptz,
  pop_up_date timestamptz,
  source_filename text,
  source_format text not null default 'wc_locations_v1',
  uploader_id uuid not null references public.profiles(id),
  notes text,
  uploaded_at timestamptz not null default now()
);

create index deployments_uploader_idx on public.deployments(uploader_id);
create index deployments_deploy_id_idx on public.deployments(deploy_id);

-- ---------------------------------------------------------------------
-- Positions: one row per drift fix
-- ---------------------------------------------------------------------
create table public.positions (
  id uuid primary key default gen_random_uuid(),
  deployment_id uuid not null references public.deployments(id) on delete cascade,
  ts timestamptz not null,
  latitude double precision not null check (latitude between -90 and 90),
  longitude double precision not null check (longitude between -180 and 180),
  location_type text not null,        -- e.g. 'Argos', 'GPS', 'GPE'
  quality_raw text,                    -- verbatim manufacturer quality code
  quality_class text not null default 'unknown'
    check (quality_class in ('high','medium','low','unusable','unknown')),
  raw_metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index positions_deployment_idx on public.positions(deployment_id);
create index positions_ts_idx on public.positions(ts);
create index positions_latlon_idx on public.positions(latitude, longitude);
create index positions_quality_idx on public.positions(quality_class);

-- ---------------------------------------------------------------------
-- Downloads: usage log (who downloaded what, and how much)
-- ---------------------------------------------------------------------
create table public.downloads (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id),
  filters jsonb not null default '{}'::jsonb,
  row_count integer not null default 0,
  downloaded_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- Row Level Security
-- Anyone authenticated can read; uploaders can only write as themselves.
-- ---------------------------------------------------------------------
alter table public.profiles enable row level security;
alter table public.deployments enable row level security;
alter table public.positions enable row level security;
alter table public.downloads enable row level security;

create policy "profiles_select_authenticated" on public.profiles
  for select using (auth.role() = 'authenticated');
create policy "profiles_update_own" on public.profiles
  for update using (auth.uid() = id);

create policy "deployments_select_authenticated" on public.deployments
  for select using (auth.role() = 'authenticated');
create policy "deployments_insert_own" on public.deployments
  for insert with check (auth.uid() = uploader_id);
create policy "deployments_update_own" on public.deployments
  for update using (auth.uid() = uploader_id);

create policy "positions_select_authenticated" on public.positions
  for select using (auth.role() = 'authenticated');
create policy "positions_insert_own_deployment" on public.positions
  for insert with check (
    exists (
      select 1 from public.deployments d
      where d.id = deployment_id and d.uploader_id = auth.uid()
    )
  );

create policy "downloads_insert_own" on public.downloads
  for insert with check (auth.uid() = user_id);
create policy "downloads_select_own" on public.downloads
  for select using (auth.uid() = user_id);
