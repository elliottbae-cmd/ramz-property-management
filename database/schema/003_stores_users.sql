-- 003: Stores, Users, User-Stores, PSP Client Access

-- Drop old tables if they exist
DROP TABLE IF EXISTS user_stores CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS stores CASCADE;

-- Stores (scoped to client)
CREATE TABLE stores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    store_number TEXT NOT NULL,
    name TEXT NOT NULL,
    address TEXT,
    city TEXT,
    state TEXT,
    zip_code TEXT,
    region TEXT,
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(client_id, store_number)
);

-- Users (single table, dual-tier hierarchy)
CREATE TABLE users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    phone TEXT,
    user_tier user_tier NOT NULL DEFAULT 'client',
    -- PSP fields (NULL for client users)
    psp_role psp_role,
    -- Client fields (NULL for PSP users)
    client_id UUID REFERENCES clients(id),
    client_role client_role,
    store_id UUID REFERENCES stores(id),
    -- Shared
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Enforce tier/role consistency
    CONSTRAINT chk_user_tier_roles CHECK (
        (user_tier = 'psp' AND psp_role IS NOT NULL AND client_id IS NULL AND client_role IS NULL)
        OR (user_tier = 'client' AND client_role IS NOT NULL AND client_id IS NOT NULL AND psp_role IS NULL)
    )
);

-- User-Stores (many-to-many for DMs/DOOs overseeing multiple stores)
CREATE TABLE user_stores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    store_id UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    UNIQUE(user_id, store_id)
);

-- PSP Client Access (tracks which client a PSP user is viewing)
CREATE TABLE psp_client_access (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    psp_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    is_current BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE(psp_user_id, client_id)
);

-- Indexes
CREATE INDEX idx_stores_client ON stores(client_id);
CREATE INDEX idx_stores_city_state ON stores(city, state);
CREATE INDEX idx_users_client ON users(client_id);
CREATE INDEX idx_users_tier ON users(user_tier);
CREATE INDEX idx_user_stores_user ON user_stores(user_id);
CREATE INDEX idx_user_stores_store ON user_stores(store_id);
CREATE INDEX idx_psp_access_user ON psp_client_access(psp_user_id);

-- Enable RLS
ALTER TABLE stores ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_stores ENABLE ROW LEVEL SECURITY;
ALTER TABLE psp_client_access ENABLE ROW LEVEL SECURITY;
