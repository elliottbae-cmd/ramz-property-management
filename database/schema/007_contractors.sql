-- 007: Contractors, Geographic Exceptions, Reviews, Work Orders

DROP TABLE IF EXISTS work_orders CASCADE;
DROP TABLE IF EXISTS contractor_reviews CASCADE;
DROP TABLE IF EXISTS contractors CASCADE;

-- Contractors (shared across all clients, PSP-managed)
CREATE TABLE contractors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_name TEXT NOT NULL,
    contact_name TEXT,
    phone TEXT,
    email TEXT,
    trades TEXT[] NOT NULL DEFAULT '{}',
    service_cities TEXT[] DEFAULT '{}',
    service_states TEXT[] NOT NULL DEFAULT '{}',
    service_zip_codes TEXT[] DEFAULT '{}',
    avg_rating DECIMAL(3, 2) DEFAULT 0,
    total_jobs INT DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_preferred BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deactivated_at TIMESTAMPTZ,
    deactivated_reason TEXT
);

-- Contractor Geographic Exceptions (PSP grants access outside normal area)
CREATE TABLE contractor_geographic_exceptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contractor_id UUID NOT NULL REFERENCES contractors(id) ON DELETE CASCADE,
    store_id UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    granted_by UUID NOT NULL REFERENCES auth.users(id),
    reason TEXT,
    expires_at DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(contractor_id, store_id)
);

-- Contractor Reviews
CREATE TABLE contractor_reviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contractor_id UUID NOT NULL REFERENCES contractors(id) ON DELETE CASCADE,
    ticket_id UUID REFERENCES tickets(id),
    reviewed_by UUID NOT NULL REFERENCES auth.users(id),
    rating INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    timeliness INT CHECK (timeliness BETWEEN 1 AND 5),
    quality INT CHECK (quality BETWEEN 1 AND 5),
    communication INT CHECK (communication BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Work Orders
CREATE TABLE work_orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES clients(id),
    contractor_id UUID NOT NULL REFERENCES contractors(id),
    amount DECIMAL(12, 2),
    status work_order_status NOT NULL DEFAULT 'issued',
    issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    notes TEXT
);

-- Warranty Claims (depends on tickets and equipment_warranties)
CREATE TABLE warranty_claims (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    warranty_id UUID NOT NULL REFERENCES equipment_warranties(id),
    ticket_id UUID NOT NULL REFERENCES tickets(id),
    claim_number TEXT,
    claim_date DATE NOT NULL DEFAULT CURRENT_DATE,
    status warranty_status NOT NULL DEFAULT 'claim_pending',
    resolution_notes TEXT,
    resolved_at TIMESTAMPTZ,
    created_by UUID NOT NULL REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add FK from tickets to warranty_claims (deferred because of circular dependency)
ALTER TABLE tickets ADD CONSTRAINT fk_tickets_warranty_claim
    FOREIGN KEY (warranty_claim_id) REFERENCES warranty_claims(id);

-- Indexes
CREATE INDEX idx_contractors_trades ON contractors USING GIN(trades);
CREATE INDEX idx_contractors_cities ON contractors USING GIN(service_cities);
CREATE INDEX idx_contractors_states ON contractors USING GIN(service_states);
CREATE INDEX idx_contractors_active ON contractors(is_active);
CREATE INDEX idx_contractor_exceptions_contractor ON contractor_geographic_exceptions(contractor_id);
CREATE INDEX idx_contractor_exceptions_store ON contractor_geographic_exceptions(store_id);
CREATE INDEX idx_contractor_reviews_contractor ON contractor_reviews(contractor_id);
CREATE INDEX idx_work_orders_ticket ON work_orders(ticket_id);
CREATE INDEX idx_work_orders_client ON work_orders(client_id);
CREATE INDEX idx_work_orders_contractor ON work_orders(contractor_id);
CREATE INDEX idx_work_orders_status ON work_orders(status);
CREATE INDEX idx_warranty_claims_warranty ON warranty_claims(warranty_id);
CREATE INDEX idx_warranty_claims_ticket ON warranty_claims(ticket_id);

-- Enable RLS
ALTER TABLE contractors ENABLE ROW LEVEL SECURITY;
ALTER TABLE contractor_geographic_exceptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE contractor_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE work_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE warranty_claims ENABLE ROW LEVEL SECURITY;
