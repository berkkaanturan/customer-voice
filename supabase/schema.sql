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
    sentiment       VARCHAR(20) NOT NULL         -- 'Positive', 'Negative', 'Neutral'
                    CHECK (sentiment IN ('Positive', 'Negative', 'Neutral')),
    category        VARCHAR(100) NOT NULL,       -- AI-determined category
    rating          SMALLINT                     -- Platform rating 1-5 (optional)
                    CHECK (rating IS NULL OR (rating >= 1 AND rating <= 5)),
    source_url      TEXT,                        -- Original review URL
    subject         VARCHAR(255),                -- Review title or topic/subject (optional)
    text_hash       VARCHAR(64),                 -- SHA-256 hash for deduplication
    is_read         BOOLEAN NOT NULL DEFAULT false, -- Read status for dashboard
    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT now(), -- When the review was scraped
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()  -- Row creation timestamp
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
