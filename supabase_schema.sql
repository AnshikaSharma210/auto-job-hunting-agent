-- ============================================================
-- Job Hunt Pro — Supabase schema
-- Run this once in the Supabase SQL Editor (Dashboard → SQL)
-- ============================================================

-- 1. Resume metadata (one row per user)
create table if not exists resume_meta (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid references auth.users not null unique,
  storage_path     text,
  raw_text         text,
  roles            text,
  years_experience float,
  ats_results      jsonb default '{}',
  updated_at       timestamptz default now()
);

-- 2. Shortlisted jobs (many per user)
create table if not exists shortlist (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references auth.users not null,
  job_data    jsonb not null,
  match_data  jsonb not null,
  created_at  timestamptz default now()
);

-- 3. Application tracker (many per user)
create table if not exists applications (
  id            text primary key,
  user_id       uuid references auth.users not null,
  job_id        text,
  company       text,
  role          text,
  platform      text,
  applied_at    text,
  status        text default 'Applied',
  job_url       text,
  cover_letter  text,
  notes         text default ''
);

-- ── Row-Level Security: each user sees only their own rows ──────────────────
alter table resume_meta   enable row level security;
alter table shortlist     enable row level security;
alter table applications  enable row level security;

create policy "own resume_meta"  on resume_meta  for all using (auth.uid() = user_id);
create policy "own shortlist"    on shortlist     for all using (auth.uid() = user_id);
create policy "own applications" on applications  for all using (auth.uid() = user_id);

-- ── Index for shortlist job lookup ──────────────────────────────────────────
create index if not exists shortlist_user_job_idx
  on shortlist ((job_data->>'id'), user_id);
