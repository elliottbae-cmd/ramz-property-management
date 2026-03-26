-- ============================================================
-- Ram-Z Property Management App — Database Schema
-- Run this in Supabase SQL Editor to set up all tables
-- ============================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- ENUM TYPES
-- ============================================================

CREATE TYPE user_role AS ENUM (
    'admin', 'director', 'dm', 'gm', 'property_manager', 'staff'
);

CREATE TYPE ticket_status AS ENUM (
    'submitted', 'assigned', 'pending_approval', 'approved', 'in_progress', 'completed', 'closed', 'rejected'
);

CREATE TYPE approval_status AS ENUM (
    'pending', 'approved', 'rejected'
);

CREATE TYPE approval_role_level AS ENUM (
    'gm', 'dm', 'director'
);

CREATE TYPE work_order_status AS ENUM (
    'issued', 'in_progress', 'completed', 'invoiced', 'paid'
);

CREATE TYPE form_field_type AS ENUM (
    'text', 'textarea', 'dropdown', 'number', 'date', 'checkbox'
);

-- ============================================================
-- STORES
-- ============================================================

CREATE TABLE stores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_number TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    address TEXT,
    city TEXT,
    state TEXT,
    region TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stores_region ON stores(region);
CREATE INDEX idx_stores_active ON stores(is_active);

-- ============================================================
-- USERS (links to Supabase Auth)
-- ============================================================

CREATE TABLE users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    role user_role NOT NULL DEFAULT 'staff',
    store_id UUID REFERENCES stores(id),
    phone TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_store ON users(store_id);

-- ============================================================
-- USER_STORES (many-to-many for DMs/Directors overseeing multiple stores)
-- ============================================================

CREATE TABLE user_stores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    store_id UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    UNIQUE(user_id, store_id)
);

CREATE INDEX idx_user_stores_user ON user_stores(user_id);
CREATE INDEX idx_user_stores_store ON user_stores(store_id);

-- ============================================================
-- EQUIPMENT
-- ============================================================

CREATE TABLE equipment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_id UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    serial_number TEXT,
    category TEXT NOT NULL,
    install_date DATE,
    notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_equipment_store ON equipment(store_id);
CREATE INDEX idx_equipment_category ON equipment(category);

-- ============================================================
-- TICKETS
-- ============================================================

CREATE TABLE tickets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_number SERIAL,
    store_id UUID NOT NULL REFERENCES stores(id),
    equipment_id UUID REFERENCES equipment(id),
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    urgency TEXT NOT NULL,
    status ticket_status NOT NULL DEFAULT 'submitted',
    estimated_cost DECIMAL(12, 2),
    actual_cost DECIMAL(12, 2),
    submitted_by UUID NOT NULL REFERENCES users(id),
    assigned_to UUID REFERENCES users(id),
    custom_fields JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tickets_store ON tickets(store_id);
CREATE INDEX idx_tickets_status ON tickets(status);
CREATE INDEX idx_tickets_urgency ON tickets(urgency);
CREATE INDEX idx_tickets_submitted_by ON tickets(submitted_by);
CREATE INDEX idx_tickets_assigned_to ON tickets(assigned_to);
CREATE INDEX idx_tickets_created ON tickets(created_at DESC);

-- ============================================================
-- TICKET PHOTOS
-- ============================================================

CREATE TABLE ticket_photos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    photo_url TEXT NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ticket_photos_ticket ON ticket_photos(ticket_id);

-- ============================================================
-- TICKET COMMENTS
-- ============================================================

CREATE TABLE ticket_comments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    comment TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ticket_comments_ticket ON ticket_comments(ticket_id);

-- ============================================================
-- APPROVALS
-- ============================================================

CREATE TABLE approvals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    approver_id UUID REFERENCES users(id),
    role_level approval_role_level NOT NULL,
    status approval_status NOT NULL DEFAULT 'pending',
    notes TEXT,
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_approvals_ticket ON approvals(ticket_id);
CREATE INDEX idx_approvals_approver ON approvals(approver_id);
CREATE INDEX idx_approvals_status ON approvals(status);

-- ============================================================
-- CONTRACTORS
-- ============================================================

CREATE TABLE contractors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_name TEXT NOT NULL,
    contact_name TEXT,
    phone TEXT,
    email TEXT,
    trades TEXT[] NOT NULL DEFAULT '{}',
    service_regions TEXT[] NOT NULL DEFAULT '{}',
    avg_rating DECIMAL(3, 2) DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_preferred BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deactivated_at TIMESTAMPTZ,
    deactivated_reason TEXT
);

CREATE INDEX idx_contractors_active ON contractors(is_active);
CREATE INDEX idx_contractors_preferred ON contractors(is_preferred);
CREATE INDEX idx_contractors_trades ON contractors USING GIN(trades);
CREATE INDEX idx_contractors_regions ON contractors USING GIN(service_regions);

-- ============================================================
-- CONTRACTOR REVIEWS
-- ============================================================

CREATE TABLE contractor_reviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contractor_id UUID NOT NULL REFERENCES contractors(id) ON DELETE CASCADE,
    ticket_id UUID REFERENCES tickets(id),
    reviewed_by UUID NOT NULL REFERENCES users(id),
    rating INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    timeliness INT CHECK (timeliness BETWEEN 1 AND 5),
    quality INT CHECK (quality BETWEEN 1 AND 5),
    communication INT CHECK (communication BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_contractor_reviews_contractor ON contractor_reviews(contractor_id);

-- ============================================================
-- WORK ORDERS
-- ============================================================

CREATE TABLE work_orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    contractor_id UUID NOT NULL REFERENCES contractors(id),
    amount DECIMAL(12, 2),
    status work_order_status NOT NULL DEFAULT 'issued',
    issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    notes TEXT
);

CREATE INDEX idx_work_orders_ticket ON work_orders(ticket_id);
CREATE INDEX idx_work_orders_contractor ON work_orders(contractor_id);
CREATE INDEX idx_work_orders_status ON work_orders(status);

-- ============================================================
-- FORM CATEGORIES (admin-configurable)
-- ============================================================

CREATE TABLE form_categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    display_order INT NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    requires_serial BOOLEAN NOT NULL DEFAULT FALSE,
    icon TEXT
);

-- ============================================================
-- FORM URGENCY LEVELS (admin-configurable)
-- ============================================================

CREATE TABLE form_urgency_levels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    display_order INT NOT NULL DEFAULT 0,
    color TEXT NOT NULL DEFAULT '#757575',
    sla_hours INT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

-- ============================================================
-- FORM CUSTOM FIELDS (admin-configurable)
-- ============================================================

CREATE TABLE form_fields (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    field_name TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    field_type form_field_type NOT NULL DEFAULT 'text',
    is_required BOOLEAN NOT NULL DEFAULT FALSE,
    display_order INT NOT NULL DEFAULT 0,
    options JSONB,
    category_filter UUID REFERENCES form_categories(id),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

-- ============================================================
-- APPROVAL SETTINGS (admin-configurable)
-- ============================================================

CREATE TABLE approval_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    role approval_role_level NOT NULL UNIQUE,
    max_auto_approve DECIMAL(12, 2) DEFAULT 0,
    requires_approval_from TEXT[] DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    updated_by UUID REFERENCES users(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- UPDATED_AT TRIGGER FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at triggers
CREATE TRIGGER trg_stores_updated_at BEFORE UPDATE ON stores
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_equipment_updated_at BEFORE UPDATE ON equipment
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_tickets_updated_at BEFORE UPDATE ON tickets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================

-- Enable RLS on all tables
ALTER TABLE stores ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_stores ENABLE ROW LEVEL SECURITY;
ALTER TABLE equipment ENABLE ROW LEVEL SECURITY;
ALTER TABLE tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE ticket_photos ENABLE ROW LEVEL SECURITY;
ALTER TABLE ticket_comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE contractors ENABLE ROW LEVEL SECURITY;
ALTER TABLE contractor_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE work_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE form_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE form_urgency_levels ENABLE ROW LEVEL SECURITY;
ALTER TABLE form_fields ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_settings ENABLE ROW LEVEL SECURITY;

-- Allow all authenticated users to read reference tables
CREATE POLICY "Anyone can read stores" ON stores FOR SELECT TO authenticated USING (true);
CREATE POLICY "Anyone can read form_categories" ON form_categories FOR SELECT TO authenticated USING (true);
CREATE POLICY "Anyone can read form_urgency_levels" ON form_urgency_levels FOR SELECT TO authenticated USING (true);
CREATE POLICY "Anyone can read form_fields" ON form_fields FOR SELECT TO authenticated USING (true);
CREATE POLICY "Anyone can read contractors" ON contractors FOR SELECT TO authenticated USING (true);
CREATE POLICY "Anyone can read users" ON users FOR SELECT TO authenticated USING (true);
CREATE POLICY "Anyone can read equipment" ON equipment FOR SELECT TO authenticated USING (true);
CREATE POLICY "Anyone can read approval_settings" ON approval_settings FOR SELECT TO authenticated USING (true);

-- Tickets: users can read tickets for their store or if they're admin/director/property_manager
CREATE POLICY "Users can read relevant tickets" ON tickets FOR SELECT TO authenticated
    USING (
        submitted_by = auth.uid()
        OR assigned_to = auth.uid()
        OR store_id IN (SELECT store_id FROM users WHERE id = auth.uid())
        OR store_id IN (SELECT store_id FROM user_stores WHERE user_id = auth.uid())
        OR EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND role IN ('admin', 'director', 'property_manager'))
    );

-- Tickets: authenticated users can insert
CREATE POLICY "Authenticated users can create tickets" ON tickets FOR INSERT TO authenticated
    WITH CHECK (submitted_by = auth.uid());

-- Tickets: admin/property_manager can update any ticket, others can update their own
CREATE POLICY "Users can update tickets" ON tickets FOR UPDATE TO authenticated
    USING (
        submitted_by = auth.uid()
        OR assigned_to = auth.uid()
        OR EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND role IN ('admin', 'property_manager', 'director'))
    );

-- Photos: follow ticket access
CREATE POLICY "Users can read ticket photos" ON ticket_photos FOR SELECT TO authenticated
    USING (ticket_id IN (SELECT id FROM tickets));
CREATE POLICY "Users can upload photos" ON ticket_photos FOR INSERT TO authenticated
    WITH CHECK (true);

-- Comments: follow ticket access
CREATE POLICY "Users can read comments" ON ticket_comments FOR SELECT TO authenticated
    USING (ticket_id IN (SELECT id FROM tickets));
CREATE POLICY "Users can add comments" ON ticket_comments FOR INSERT TO authenticated
    WITH CHECK (user_id = auth.uid());

-- Approvals: relevant users can read/update
CREATE POLICY "Users can read approvals" ON approvals FOR SELECT TO authenticated USING (true);
CREATE POLICY "Users can update approvals" ON approvals FOR UPDATE TO authenticated
    USING (
        approver_id = auth.uid()
        OR EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND role IN ('admin', 'director'))
    );
CREATE POLICY "System can create approvals" ON approvals FOR INSERT TO authenticated WITH CHECK (true);

-- User stores: readable by all authenticated
CREATE POLICY "Anyone can read user_stores" ON user_stores FOR SELECT TO authenticated USING (true);

-- Reviews
CREATE POLICY "Anyone can read reviews" ON contractor_reviews FOR SELECT TO authenticated USING (true);
CREATE POLICY "Users can add reviews" ON contractor_reviews FOR INSERT TO authenticated
    WITH CHECK (reviewed_by = auth.uid());

-- Work orders
CREATE POLICY "Users can read work orders" ON work_orders FOR SELECT TO authenticated USING (true);
CREATE POLICY "Admin/PM can manage work orders" ON work_orders FOR ALL TO authenticated
    USING (EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND role IN ('admin', 'property_manager')));

-- Admin-only write policies for config tables
CREATE POLICY "Admin can manage stores" ON stores FOR ALL TO authenticated
    USING (EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND role = 'admin'));
CREATE POLICY "Admin can manage users" ON users FOR ALL TO authenticated
    USING (EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND role = 'admin'));
CREATE POLICY "Admin can manage user_stores" ON user_stores FOR ALL TO authenticated
    USING (EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND role = 'admin'));
CREATE POLICY "Admin can manage equipment" ON equipment FOR ALL TO authenticated
    USING (EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND role IN ('admin', 'property_manager')));
CREATE POLICY "Admin can manage contractors" ON contractors FOR ALL TO authenticated
    USING (EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND role IN ('admin', 'property_manager')));
CREATE POLICY "Admin can manage form_categories" ON form_categories FOR ALL TO authenticated
    USING (EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND role = 'admin'));
CREATE POLICY "Admin can manage form_urgency_levels" ON form_urgency_levels FOR ALL TO authenticated
    USING (EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND role = 'admin'));
CREATE POLICY "Admin can manage form_fields" ON form_fields FOR ALL TO authenticated
    USING (EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND role = 'admin'));
CREATE POLICY "Admin can manage approval_settings" ON approval_settings FOR ALL TO authenticated
    USING (EXISTS (SELECT 1 FROM users WHERE id = auth.uid() AND role = 'admin'));

-- Users can insert their own profile (for initial signup)
CREATE POLICY "Users can insert own profile" ON users FOR INSERT TO authenticated
    WITH CHECK (id = auth.uid());

-- Users can update their own profile
CREATE POLICY "Users can update own profile" ON users FOR UPDATE TO authenticated
    USING (id = auth.uid());
