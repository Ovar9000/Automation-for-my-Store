-- ==============================================================================
-- SARI-SARI STORE POS — SUPABASE CLOUD SYNC & DISASTER RECOVERY SCHEMA
-- ==============================================================================
-- Run this entire script in your Supabase SQL Editor:
-- https://supabase.com/dashboard/project/dveufoeavxegvcgityax/sql/new
-- ==============================================================================

-- 1. STORAGE BUCKET: store-backups
-- Enables uploading of SQLite store.db snapshot backups
INSERT INTO storage.buckets (id, name, public)
VALUES ('store-backups', 'store-backups', true)
ON CONFLICT (id) DO UPDATE SET public = true;

-- Storage RLS Policies (Storage upsert requires SELECT + INSERT + UPDATE)
DROP POLICY IF EXISTS "Allow public read from store-backups" ON storage.objects;
CREATE POLICY "Allow public read from store-backups"
ON storage.objects FOR SELECT
USING (bucket_id = 'store-backups');

DROP POLICY IF EXISTS "Allow uploads to store-backups" ON storage.objects;
CREATE POLICY "Allow uploads to store-backups"
ON storage.objects FOR INSERT
WITH CHECK (bucket_id = 'store-backups');

DROP POLICY IF EXISTS "Allow updates to store-backups" ON storage.objects;
CREATE POLICY "Allow updates to store-backups"
ON storage.objects FOR UPDATE
USING (bucket_id = 'store-backups');


-- 2. CLOUD MIRROR TABLES (For real-time sales, inventory, and utang tracking)
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.products (
    id                  BIGINT PRIMARY KEY,
    barcode             TEXT,
    pack_barcode        TEXT,
    jar_code            TEXT,
    name                TEXT NOT NULL,
    category            TEXT DEFAULT 'General',
    unit                TEXT NOT NULL DEFAULT 'pc',
    cost_price          NUMERIC(12, 2) NOT NULL DEFAULT 0,
    selling_price       NUMERIC(12, 2) NOT NULL DEFAULT 0,
    stock_qty           NUMERIC(12, 3) NOT NULL DEFAULT 0,
    low_stock_threshold NUMERIC(12, 3) NOT NULL DEFAULT 5,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.transactions (
    id                  BIGINT PRIMARY KEY,
    receipt_number      TEXT,
    transaction_type    TEXT NOT NULL DEFAULT 'SALE',
    total_amount        NUMERIC(12, 2) NOT NULL DEFAULT 0,
    total_cost          NUMERIC(12, 2) NOT NULL DEFAULT 0,
    payment_method      TEXT DEFAULT 'CASH',
    amount_tendered     NUMERIC(12, 2) NOT NULL DEFAULT 0,
    change_amount       NUMERIC(12, 2) NOT NULL DEFAULT 0,
    customer_name       TEXT,
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.transaction_items (
    id                  BIGINT PRIMARY KEY,
    transaction_id      BIGINT REFERENCES public.transactions(id) ON DELETE CASCADE,
    product_name        TEXT NOT NULL,
    quantity            NUMERIC(12, 3) NOT NULL DEFAULT 1,
    unit_price          NUMERIC(12, 2) NOT NULL DEFAULT 0,
    cost_price          NUMERIC(12, 2) NOT NULL DEFAULT 0,
    subtotal            NUMERIC(12, 2) NOT NULL DEFAULT 0,
    pack_label          TEXT
);

CREATE TABLE IF NOT EXISTS public.customer_debts (
    id                  BIGINT PRIMARY KEY,
    customer_name       TEXT NOT NULL UNIQUE,
    total_debt          NUMERIC(12, 2) NOT NULL DEFAULT 0,
    phone_number        TEXT,
    notes               TEXT,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.debt_transactions (
    id                  BIGINT PRIMARY KEY,
    debt_id             BIGINT REFERENCES public.customer_debts(id) ON DELETE CASCADE,
    sale_id             BIGINT,
    type                TEXT NOT NULL,
    amount              NUMERIC(12, 2) NOT NULL,
    balance_after       NUMERIC(12, 2) NOT NULL,
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.gcash_transactions (
    id                  BIGINT PRIMARY KEY,
    transaction_id      BIGINT REFERENCES public.transactions(id) ON DELETE CASCADE,
    flow_type           TEXT NOT NULL,
    input_amount        NUMERIC(12, 2) NOT NULL,
    principal_amount    NUMERIC(12, 2) NOT NULL,
    fee                 NUMERIC(12, 2) NOT NULL,
    total_collected     NUMERIC(12, 2) NOT NULL,
    reference_number    TEXT,
    mobile_number       TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for lightning-fast queries
CREATE INDEX IF NOT EXISTS idx_cloud_products_barcode ON public.products(barcode);
CREATE INDEX IF NOT EXISTS idx_cloud_txns_created_at ON public.transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_cloud_txn_items_txnid ON public.transaction_items(transaction_id);
CREATE INDEX IF NOT EXISTS idx_cloud_debts_customer ON public.customer_debts(customer_name);

-- 3. ROW LEVEL SECURITY (RLS) & PUBLIC API ACCESS
ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transaction_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.customer_debts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.debt_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.gcash_transactions ENABLE ROW LEVEL SECURITY;

-- Read policies for authenticated & anon clients
CREATE POLICY "Allow public read on products" ON public.products FOR SELECT USING (true);
CREATE POLICY "Allow public read on transactions" ON public.transactions FOR SELECT USING (true);
CREATE POLICY "Allow public read on transaction_items" ON public.transaction_items FOR SELECT USING (true);
CREATE POLICY "Allow public read on customer_debts" ON public.customer_debts FOR SELECT USING (true);
CREATE POLICY "Allow public read on debt_transactions" ON public.debt_transactions FOR SELECT USING (true);
CREATE POLICY "Allow public read on gcash_transactions" ON public.gcash_transactions FOR SELECT USING (true);

-- Allow upsert/write from POS client with publishable key
CREATE POLICY "Allow write on products" ON public.products FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow write on transactions" ON public.transactions FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow write on transaction_items" ON public.transaction_items FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow write on customer_debts" ON public.customer_debts FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow write on debt_transactions" ON public.debt_transactions FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow write on gcash_transactions" ON public.gcash_transactions FOR ALL USING (true) WITH CHECK (true);

-- Grant schema permissions to anon and authenticated roles
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated;
