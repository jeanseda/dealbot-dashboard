-- DealBot Dashboard - PostgreSQL Schema
-- Run once on first deploy (handled by init_db.py)

CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    phone_number VARCHAR(30) UNIQUE NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tracked_products (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    asin          VARCHAR(20),
    name          TEXT,
    url           TEXT,
    current_price NUMERIC(10, 2),
    target_price  NUMERIC(10, 2),
    is_active     INTEGER DEFAULT 1,
    created_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS price_history (
    id          SERIAL PRIMARY KEY,
    product_id  INTEGER NOT NULL REFERENCES tracked_products(id) ON DELETE CASCADE,
    price       NUMERIC(10, 2) NOT NULL,
    recorded_at TIMESTAMP DEFAULT NOW()
);

-- Magic Link tokens for passwordless authentication
CREATE TABLE IF NOT EXISTS access_tokens (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
    token       VARCHAR(64) UNIQUE NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW(),
    expires_at  TIMESTAMP NOT NULL,
    used_at     TIMESTAMP NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_tracked_products_user_id ON tracked_products(user_id);
CREATE INDEX IF NOT EXISTS idx_price_history_product_id ON price_history(product_id);
CREATE INDEX IF NOT EXISTS idx_access_tokens_token ON access_tokens(token);
CREATE INDEX IF NOT EXISTS idx_access_tokens_user_id ON access_tokens(user_id);
