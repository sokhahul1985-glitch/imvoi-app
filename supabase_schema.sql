-- ==============================================================
-- IMVOI CLOUD DATABASE SCHEMA FOR SUPABASE (PostgreSQL)
-- Run this in Supabase -> SQL Editor -> New Query -> Run
-- ==============================================================

-- 1. Create Invoices Table
CREATE TABLE IF NOT EXISTS invoices (
    receipt_no TEXT PRIMARY KEY,
    category TEXT DEFAULT 'car',
    data JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Create Counters Table
CREATE TABLE IF NOT EXISTS app_counters (
    key TEXT PRIMARY KEY,
    val JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Enable Full Access via API
ALTER TABLE invoices DISABLE ROW LEVEL SECURITY;
ALTER TABLE app_counters DISABLE ROW LEVEL SECURITY;

-- 4. Fast Search Indexes
CREATE INDEX IF NOT EXISTS idx_invoices_category ON invoices(category);
CREATE INDEX IF NOT EXISTS idx_invoices_updated_at ON invoices(updated_at DESC);
