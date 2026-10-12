-- ============================================
-- Customer Voice Dashboard — Database Schema
-- Platform: Supabase (PostgreSQL)
-- ============================================

-- Enable UUID extension (usually enabled by default in Supabase)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- REVIEWS TABLE
-- Stores all customer reviews from various platforms
-- ============================================
CREATE TABLE IF NOT EXISTS reviews (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_name   VARCHAR(50) NOT NULL,       -- 'Şikayetvar', 'Play Store', 'App Store', 'Ekşi Sözlük'
    author          VARCHAR(255),                -- Review author name (optional)
    original_text   TEXT NOT NULL,               -- Original review text
    sentiment       VARCHAR(20) NOT NULL         -- 'Positive', 'Negative'
                    CHECK (sentiment IN ('Positive', 'Negative', 'Neutral')),
    category        VARCHAR(100) NOT NULL,       -- AI-determined category
    rating          SMALLINT                     -- Platform rating 1-5 (optional)
                    CHECK (rating IS NULL OR (rating >= 1 AND rating <= 5)),
    source_url      TEXT,                        -- Original review URL
    subject         VARCHAR(255),                -- Review title or topic/subject (optional)
    text_hash       VARCHAR(64),                 -- SHA-256 hash for deduplication
    external_id     TEXT,                        -- Stable per-platform ID (entry id, reviewId, complaint path)
    keywords        TEXT[] DEFAULT '{}',         -- Extracted domain-specific keywords
    is_read         BOOLEAN NOT NULL DEFAULT false, -- Read status for dashboard
    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT now(), -- When the review was scraped
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),  -- Row creation timestamp
    CONSTRAINT uq_reviews_platform_external_id UNIQUE (platform_name, external_id)
);

-- ============================================
-- INDEXES for query performance
-- ============================================

-- Filter by platform
CREATE INDEX IF NOT EXISTS idx_reviews_platform_name ON reviews (platform_name);

-- Filter by sentiment
CREATE INDEX IF NOT EXISTS idx_reviews_sentiment ON reviews (sentiment);

-- Filter by category
CREATE INDEX IF NOT EXISTS idx_reviews_category ON reviews (category);

-- Sort/filter by date (most common query pattern)
CREATE INDEX IF NOT EXISTS idx_reviews_scraped_at ON reviews (scraped_at DESC);

-- Filter unread reviews
CREATE INDEX IF NOT EXISTS idx_reviews_is_read ON reviews (is_read) WHERE is_read = false;

-- Composite index for dashboard's most common query pattern
CREATE INDEX IF NOT EXISTS idx_reviews_platform_scraped_at ON reviews (platform_name, scraped_at DESC);

-- ============================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================

-- Enable RLS on the table
ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;

-- Allow public read access (anon key can read all reviews)
CREATE POLICY "Allow public read access"
    ON reviews
    FOR SELECT
    USING (true);

-- Allow service role to insert (Python scraper uses service role key)
CREATE POLICY "Allow service role insert"
    ON reviews
    FOR INSERT
    WITH CHECK (true);

-- Allow service role to update (mark as read)
CREATE POLICY "Allow service role update"
    ON reviews
    FOR UPDATE
    USING (true)
    WITH CHECK (true);

-- ============================================
-- COMMENTS
-- ============================================
COMMENT ON TABLE reviews IS 'Customer reviews collected from various platforms, analyzed by Gemini AI';
COMMENT ON COLUMN reviews.platform_name IS 'Source platform: Şikayetvar, Play Store, App Store, Ekşi Sözlük';
COMMENT ON COLUMN reviews.sentiment IS 'AI-determined sentiment: Positive, Negative, or Neutral';
COMMENT ON COLUMN reviews.category IS 'AI-determined category: Altyapı, Fiyat, Kurulum, Müşteri Hizmetleri, etc.';
COMMENT ON COLUMN reviews.is_read IS 'Whether the review has been viewed in the dashboard';

-- ============================================
-- SCRAPER LOGS TABLE
-- Tracks the execution details of the daily scraping pipeline
-- ============================================
CREATE TABLE IF NOT EXISTS scraper_logs (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at              TIMESTAMPTZ NOT NULL,
    completed_at            TIMESTAMPTZ NOT NULL,
    total_duration_seconds  NUMERIC(10, 2) NOT NULL,
    status                  VARCHAR(20) NOT NULL CHECK (status IN ('success', 'error')),
    error_message           TEXT,
    platform_stats          JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_scraper_logs_started_at ON scraper_logs (started_at DESC);

ALTER TABLE scraper_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read access to logs"
    ON scraper_logs FOR SELECT USING (true);

CREATE POLICY "Allow service role insert to logs"
    ON scraper_logs FOR INSERT WITH CHECK (true);

-- ============================================
-- SCRAPE STATE TABLE
-- Per-source watermark used for incremental scraping
-- (see migrations/001_external_id_and_scrape_state.sql)
-- ============================================
CREATE TABLE IF NOT EXISTS scrape_state (
    platform_name     TEXT NOT NULL,
    source_key        TEXT NOT NULL,
    last_external_id  TEXT,
    last_seen_at      TIMESTAMPTZ,
    last_entry_count  INTEGER,
    meta              JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (platform_name, source_key)
);

ALTER TABLE scrape_state ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read access to scrape_state"
    ON scrape_state FOR SELECT USING (true);
