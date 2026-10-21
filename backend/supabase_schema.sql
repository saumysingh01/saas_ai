-- ============================================================
-- MarketMind AI — Full Database Schema v2
-- Run this entire file in Supabase SQL Editor
-- ============================================================

-- ── 1. analysis_reports ──────────────────────────────────────
create table if not exists public.analysis_reports (
    id               uuid primary key default gen_random_uuid(),
    client_id        text not null,
    market_topic     text not null,
    generated_report text not null,
    created_at       timestamptz not null default now()
);

alter table public.analysis_reports enable row level security;

-- Drop old policy (if exists) and create new ones using auth.uid()
drop policy if exists "select own client reports" on public.analysis_reports;
drop policy if exists "select own reports"        on public.analysis_reports;
drop policy if exists "insert own reports"        on public.analysis_reports;

create policy "select own reports"
  on public.analysis_reports for select
  using (client_id = auth.uid()::text);

create policy "insert own reports"
  on public.analysis_reports for insert
  with check (client_id = auth.uid()::text);

create index if not exists idx_analysis_reports_client
    on public.analysis_reports (client_id, created_at desc);


-- ── 2. jobs ──────────────────────────────────────────────────
create table if not exists public.jobs (
    id           uuid primary key default gen_random_uuid(),
    client_id    text not null,
    market_topic text not null,
    status       text not null default 'queued',
    report_id    uuid references public.analysis_reports(id) on delete set null,
    error        text,
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now()
);

alter table public.jobs enable row level security;

drop policy if exists "select own jobs" on public.jobs;
drop policy if exists "insert own jobs" on public.jobs;

create policy "select own jobs"
  on public.jobs for select
  using (client_id = auth.uid()::text);

create policy "insert own jobs"
  on public.jobs for insert
  with check (client_id = auth.uid()::text);

create index if not exists idx_jobs_client
    on public.jobs (client_id, created_at desc);


-- ── 3. usage_events ──────────────────────────────────────────
create table if not exists public.usage_events (
    id         uuid primary key default gen_random_uuid(),
    client_id  text not null,
    event_type text not null default 'analysis_run',
    created_at timestamptz not null default now()
);

alter table public.usage_events enable row level security;

drop policy if exists "select own usage" on public.usage_events;

create policy "select own usage"
  on public.usage_events for select
  using (client_id = auth.uid()::text);

create index if not exists idx_usage_events_client
    on public.usage_events (client_id, event_type, created_at desc);


-- ── 4. share_tokens ──────────────────────────────────────────
create table if not exists public.share_tokens (
    token      text primary key default encode(gen_random_bytes(24), 'hex'),
    report_id  uuid not null references public.analysis_reports(id) on delete cascade,
    client_id  text not null,
    created_at timestamptz not null default now(),
    expires_at timestamptz
);

-- No RLS needed: public read by token design (server handles auth)
-- Service role bypasses RLS for all inserts

create index if not exists idx_share_tokens_report
    on public.share_tokens (report_id);
