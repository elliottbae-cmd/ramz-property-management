-- 001: Enum Types for Property Management SaaS
-- Drop old enums if they exist
DROP TYPE IF EXISTS user_role CASCADE;
DROP TYPE IF EXISTS ticket_status CASCADE;
DROP TYPE IF EXISTS approval_status CASCADE;
DROP TYPE IF EXISTS approval_role_level CASCADE;
DROP TYPE IF EXISTS work_order_status CASCADE;
DROP TYPE IF EXISTS form_field_type CASCADE;

-- New enums
CREATE TYPE user_tier AS ENUM ('psp', 'client');

CREATE TYPE psp_role AS ENUM ('admin', 'svp', 'project_manager', 'assistant_project_manager');

CREATE TYPE client_role AS ENUM ('coo', 'admin', 'vp', 'doo', 'dm', 'gm');

CREATE TYPE ticket_status AS ENUM (
    'submitted', 'troubleshooting', 'warranty_check', 'pending_approval',
    'approved', 'assigned', 'in_progress', 'completed', 'closed', 'rejected'
);

CREATE TYPE approval_status AS ENUM ('pending', 'approved', 'rejected', 'skipped');

CREATE TYPE work_order_status AS ENUM ('issued', 'in_progress', 'completed', 'invoiced', 'paid');

CREATE TYPE form_field_type AS ENUM ('text', 'textarea', 'dropdown', 'number', 'date', 'checkbox');

CREATE TYPE warranty_status AS ENUM ('active', 'expired', 'claim_pending', 'claim_approved', 'claim_denied');
