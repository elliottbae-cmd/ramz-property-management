-- 006: Approval Configuration and Records

DROP TABLE IF EXISTS approvals CASCADE;
DROP TABLE IF EXISTS approval_settings CASCADE;

-- Approval Chain Config (per-client configurable approval steps)
CREATE TABLE approval_chain_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    step_order INT NOT NULL,
    role_required client_role NOT NULL,
    min_amount DECIMAL(12, 2) DEFAULT 0,
    max_auto_approve DECIMAL(12, 2),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(client_id, step_order)
);

-- Approval Thresholds (per-client)
CREATE TABLE approval_thresholds (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE UNIQUE,
    threshold_amount DECIMAL(12, 2) NOT NULL DEFAULT 1000.00,
    updated_by UUID REFERENCES auth.users(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Individual Approval Records
CREATE TABLE approvals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES clients(id),
    approver_id UUID REFERENCES auth.users(id),
    role_required client_role,
    psp_role_required psp_role,
    step_order INT NOT NULL,
    status approval_status NOT NULL DEFAULT 'pending',
    is_psp_override BOOLEAN DEFAULT FALSE,
    notes TEXT,
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_approval_config_client ON approval_chain_config(client_id);
CREATE INDEX idx_approvals_ticket ON approvals(ticket_id);
CREATE INDEX idx_approvals_client ON approvals(client_id);
CREATE INDEX idx_approvals_approver ON approvals(approver_id) WHERE approver_id IS NOT NULL;
CREATE INDEX idx_approvals_status ON approvals(status);

-- Enable RLS
ALTER TABLE approval_chain_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_thresholds ENABLE ROW LEVEL SECURITY;
ALTER TABLE approvals ENABLE ROW LEVEL SECURITY;
