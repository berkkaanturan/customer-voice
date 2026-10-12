-- ============================================================================
-- Migration 001 — ID-based incremental scraping
--
-- 1. reviews.external_id : stable per-platform ID (Ekşi entry id, Play Store
--    reviewId, App Store review id, Şikayetvar complaint path).
-- 2. UNIQUE (platform_name, external_id) so inserts can be idempotent upserts.
--    NULLs are distinct in Postgres, so legacy rows without an ID are fine.
-- 3. Backfill external_id for legacy Ekşi / Şikayetvar rows from source_url
--    (only ONE row per ID is tagged; existing duplicates are left untouched,
--    nothing is deleted).
-- 4. scrape_state : per-source watermark / change-detection state.
--
-- Safe to run multiple times.
-- ============================================================================

-- 1) Column ------------------------------------------------------------------
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS external_id TEXT;

-- 3) Backfill (before the constraint so duplicates can't break it) ----------
-- Ekşi Sözlük: https://eksisozluk.com/entry/<id>
WITH ranked AS (
    SELECT id,
           substring(source_url FROM '/entry/([0-9]+)') AS ext,
           row_number() OVER (
               PARTITION BY substring(source_url FROM '/entry/([0-9]+)')
               ORDER BY created_at
           ) AS rn
    FROM reviews
    WHERE platform_name = 'Ekşi Sözlük'
      AND external_id IS NULL
      AND source_url ~ '/entry/[0-9]+'
)
UPDATE reviews r
SET external_id = ranked.ext
FROM ranked
WHERE r.id = ranked.id
  AND ranked.rn = 1
  AND NOT EXISTS (
      SELECT 1 FROM reviews x
      WHERE x.platform_name = 'Ekşi Sözlük' AND x.external_id = ranked.ext
  );

-- Şikayetvar: https://www.sikayetvar.com/<brand>/<complaint-slug>
WITH ranked AS (
    SELECT id,
           substring(source_url FROM 'sikayetvar\.com/([^?#]+/[^?#/]+)$') AS ext,
           row_number() OVER (
               PARTITION BY substring(source_url FROM 'sikayetvar\.com/([^?#]+/[^?#/]+)$')
               ORDER BY created_at
           ) AS rn
    FROM reviews
    WHERE platform_name = 'Şikayetvar'
      AND external_id IS NULL
      AND source_url ~ 'sikayetvar\.com/[^?#]+/[^?#/]+$'
)
UPDATE reviews r
SET external_id = ranked.ext
FROM ranked
WHERE r.id = ranked.id
  AND ranked.rn = 1
  AND ranked.ext IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM reviews x
      WHERE x.platform_name = 'Şikayetvar' AND x.external_id = ranked.ext
  );

-- 2) Unique constraint ------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_reviews_platform_external_id'
    ) THEN
        ALTER TABLE reviews
            ADD CONSTRAINT uq_reviews_platform_external_id
            UNIQUE (platform_name, external_id);
    END IF;
END $$;

-- 4) scrape_state ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scrape_state (
    platform_name     TEXT NOT NULL,
    source_key        TEXT NOT NULL,          -- Ekşi: topic slug, others: 'default'
    last_external_id  TEXT,                   -- newest ID seen
    last_seen_at      TIMESTAMPTZ,            -- date of newest review seen
    last_entry_count  INTEGER,                -- Ekşi: entry count from search page
    meta              JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (platform_name, source_key)
);

ALTER TABLE scrape_state ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'scrape_state' AND policyname = 'Allow public read access to scrape_state'
    ) THEN
        CREATE POLICY "Allow public read access to scrape_state"
            ON scrape_state FOR SELECT USING (true);
    END IF;
END $$;
-- (Writes are done with the service-role key, which bypasses RLS.)

-- Quick check after running:
-- SELECT platform_name, count(*) AS total, count(external_id) AS with_id
-- FROM reviews GROUP BY platform_name;
