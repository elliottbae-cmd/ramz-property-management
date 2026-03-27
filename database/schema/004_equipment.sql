-- 004: Equipment and Warranties

DROP TABLE IF EXISTS equipment CASCADE;

-- Equipment (scoped to store, which is scoped to client)
CREATE TABLE equipment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_id UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    serial_number TEXT,
    category TEXT NOT NULL,
    manufacturer TEXT,
    brand TEXT,
    model TEXT,
    install_date DATE,
    notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Equipment Warranties
CREATE TABLE equipment_warranties (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    equipment_id UUID NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    warranty_provider TEXT NOT NULL,
    warranty_type TEXT,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    coverage_description TEXT,
    contact_phone TEXT,
    contact_email TEXT,
    claim_url TEXT,
    document_urls TEXT[] DEFAULT '{}',
    status warranty_status NOT NULL DEFAULT 'active',
    notes TEXT,
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_equipment_store ON equipment(store_id);
CREATE INDEX idx_equipment_serial ON equipment(serial_number) WHERE serial_number IS NOT NULL;
CREATE INDEX idx_equipment_category ON equipment(category);
CREATE INDEX idx_warranties_equipment ON equipment_warranties(equipment_id);
CREATE INDEX idx_warranties_status ON equipment_warranties(status);
CREATE INDEX idx_warranties_end_date ON equipment_warranties(end_date);

-- Enable RLS
ALTER TABLE equipment ENABLE ROW LEVEL SECURITY;
ALTER TABLE equipment_warranties ENABLE ROW LEVEL SECURITY;
