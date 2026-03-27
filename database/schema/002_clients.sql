-- 002: Clients (Tenants) Table
CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    logo_url TEXT,
    primary_color TEXT DEFAULT '#C4A04D',
    secondary_color TEXT DEFAULT '#1B3A4B',
    accent_color TEXT DEFAULT '#C4A04D',
    surface_color TEXT DEFAULT '#F7F4EE',
    company_name TEXT NOT NULL,
    tagline TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
