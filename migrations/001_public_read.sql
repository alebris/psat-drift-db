-- Run this once in your existing Supabase project's SQL editor.
-- Makes deployments and positions readable without login (map/statistics
-- are now public); upload/download still require authentication as before.

drop policy if exists "deployments_select_authenticated" on public.deployments;
create policy "deployments_select_public" on public.deployments
  for select using (true);

drop policy if exists "positions_select_authenticated" on public.positions;
create policy "positions_select_public" on public.positions
  for select using (true);
