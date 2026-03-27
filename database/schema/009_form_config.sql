-- 009: Form Configuration (Per-Client, with global defaults)

DROP TABLE IF EXISTS form_fields CASCADE;
DROP TABLE IF EXISTS form_urgency_levels CASCADE;
DROP TABLE IF EXISTS form_categories CASCADE;

-- Form Categories
CREATE TABLE form_categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    display_order INT NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    requires_serial BOOLEAN NOT NULL DEFAULT FALSE,
    icon TEXT,
    UNIQUE(client_id, name)
);

-- Form Urgency Levels
CREATE TABLE form_urgency_levels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    display_order INT NOT NULL DEFAULT 0,
    color TEXT NOT NULL DEFAULT '#757575',
    sla_hours INT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE(client_id, name)
);

-- Form Fields (custom fields per category)
CREATE TABLE form_fields (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    field_name TEXT NOT NULL,
    label TEXT NOT NULL,
    field_type form_field_type NOT NULL DEFAULT 'text',
    is_required BOOLEAN NOT NULL DEFAULT FALSE,
    display_order INT NOT NULL DEFAULT 0,
    options JSONB,
    category_filter UUID REFERENCES form_categories(id),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE(client_id, field_name)
);

-- Indexes
CREATE INDEX idx_form_categories_client ON form_categories(client_id);
CREATE INDEX idx_form_urgency_client ON form_urgency_levels(client_id);
CREATE INDEX idx_form_fields_client ON form_fields(client_id);

-- Enable RLS
ALTER TABLE form_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE form_urgency_levels ENABLE ROW LEVEL SECURITY;
ALTER TABLE form_fields ENABLE ROW LEVEL SECURITY;
