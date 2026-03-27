-- 005: Tickets, Photos, Comments

DROP TABLE IF EXISTS ticket_comments CASCADE;
DROP TABLE IF EXISTS ticket_photos CASCADE;
DROP TABLE IF EXISTS tickets CASCADE;

-- Tickets
CREATE TABLE tickets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_number SERIAL,
    client_id UUID NOT NULL REFERENCES clients(id),
    store_id UUID NOT NULL REFERENCES stores(id),
    equipment_id UUID REFERENCES equipment(id),
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    urgency TEXT NOT NULL,
    status ticket_status NOT NULL DEFAULT 'submitted',
    estimated_cost DECIMAL(12, 2),
    actual_cost DECIMAL(12, 2),
    submitted_by UUID NOT NULL REFERENCES auth.users(id),
    assigned_to UUID REFERENCES auth.users(id),
    custom_fields JSONB DEFAULT '{}',
    -- Warranty routing
    warranty_checked BOOLEAN DEFAULT FALSE,
    warranty_claim_id UUID,
    -- Troubleshooting
    troubleshooting_completed BOOLEAN DEFAULT FALSE,
    troubleshooting_resolved BOOLEAN DEFAULT FALSE,
    -- Resolution
    resolution_notes TEXT,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ticket Photos
CREATE TABLE ticket_photos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    photo_url TEXT NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ticket Comments
CREATE TABLE ticket_comments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id),
    comment TEXT NOT NULL,
    is_internal BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_tickets_client ON tickets(client_id);
CREATE INDEX idx_tickets_store ON tickets(store_id);
CREATE INDEX idx_tickets_status ON tickets(status);
CREATE INDEX idx_tickets_urgency ON tickets(urgency);
CREATE INDEX idx_tickets_submitted_by ON tickets(submitted_by);
CREATE INDEX idx_tickets_assigned_to ON tickets(assigned_to) WHERE assigned_to IS NOT NULL;
CREATE INDEX idx_tickets_created ON tickets(created_at DESC);
CREATE INDEX idx_tickets_equipment ON tickets(equipment_id) WHERE equipment_id IS NOT NULL;
CREATE INDEX idx_ticket_photos_ticket ON ticket_photos(ticket_id);
CREATE INDEX idx_ticket_comments_ticket ON ticket_comments(ticket_id);

-- Enable RLS
ALTER TABLE tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE ticket_photos ENABLE ROW LEVEL SECURITY;
ALTER TABLE ticket_comments ENABLE ROW LEVEL SECURITY;
