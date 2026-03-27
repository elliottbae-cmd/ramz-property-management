-- 000: Drop all existing tables and types from v1
-- Run this FIRST before running the new schema

-- Drop all old policies (ignore errors if they don't exist)
DROP POLICY IF EXISTS "Anyone can read users" ON users;
DROP POLICY IF EXISTS "Admin can manage users" ON users;
DROP POLICY IF EXISTS "Users can insert own profile" ON users;
DROP POLICY IF EXISTS "Users can update own profile" ON users;
DROP POLICY IF EXISTS "Anyone can read stores" ON stores;
DROP POLICY IF EXISTS "Admin can manage stores" ON stores;
DROP POLICY IF EXISTS "Admin can manage user_stores" ON user_stores;
DROP POLICY IF EXISTS "Admin can manage equipment" ON equipment;
DROP POLICY IF EXISTS "Admin can manage contractors" ON contractors;
DROP POLICY IF EXISTS "Admin can manage form_categories" ON form_categories;
DROP POLICY IF EXISTS "Admin can manage form_urgency_levels" ON form_urgency_levels;
DROP POLICY IF EXISTS "Admin can manage form_fields" ON form_fields;
DROP POLICY IF EXISTS "Admin can manage approval_settings" ON approval_settings;

-- Drop all old tables
DROP TABLE IF EXISTS audit_log CASCADE;
DROP TABLE IF EXISTS knowledge_base_feedback CASCADE;
DROP TABLE IF EXISTS knowledge_base CASCADE;
DROP TABLE IF EXISTS warranty_claims CASCADE;
DROP TABLE IF EXISTS work_orders CASCADE;
DROP TABLE IF EXISTS contractor_reviews CASCADE;
DROP TABLE IF EXISTS contractor_geographic_exceptions CASCADE;
DROP TABLE IF EXISTS contractors CASCADE;
DROP TABLE IF EXISTS approvals CASCADE;
DROP TABLE IF EXISTS approval_thresholds CASCADE;
DROP TABLE IF EXISTS approval_chain_config CASCADE;
DROP TABLE IF EXISTS approval_settings CASCADE;
DROP TABLE IF EXISTS ticket_comments CASCADE;
DROP TABLE IF EXISTS ticket_photos CASCADE;
DROP TABLE IF EXISTS tickets CASCADE;
DROP TABLE IF EXISTS equipment_warranties CASCADE;
DROP TABLE IF EXISTS equipment CASCADE;
DROP TABLE IF EXISTS form_fields CASCADE;
DROP TABLE IF EXISTS form_urgency_levels CASCADE;
DROP TABLE IF EXISTS form_categories CASCADE;
DROP TABLE IF EXISTS psp_client_access CASCADE;
DROP TABLE IF EXISTS user_stores CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS stores CASCADE;
DROP TABLE IF EXISTS clients CASCADE;

-- Drop old enums
DROP TYPE IF EXISTS user_role CASCADE;
DROP TYPE IF EXISTS user_tier CASCADE;
DROP TYPE IF EXISTS psp_role CASCADE;
DROP TYPE IF EXISTS client_role CASCADE;
DROP TYPE IF EXISTS ticket_status CASCADE;
DROP TYPE IF EXISTS approval_status CASCADE;
DROP TYPE IF EXISTS approval_role_level CASCADE;
DROP TYPE IF EXISTS work_order_status CASCADE;
DROP TYPE IF EXISTS form_field_type CASCADE;
DROP TYPE IF EXISTS warranty_status CASCADE;

-- Drop old helper functions
DROP FUNCTION IF EXISTS public.get_my_role() CASCADE;
DROP FUNCTION IF EXISTS public.get_user_tier() CASCADE;
DROP FUNCTION IF EXISTS public.get_user_client_id() CASCADE;
DROP FUNCTION IF EXISTS public.is_psp_user() CASCADE;
DROP FUNCTION IF EXISTS public.get_psp_role() CASCADE;
DROP FUNCTION IF EXISTS public.get_client_role() CASCADE;
DROP FUNCTION IF EXISTS public.get_psp_current_client() CASCADE;
DROP FUNCTION IF EXISTS public.effective_client_id() CASCADE;

-- Drop old views
DROP VIEW IF EXISTS v_ticket_metrics CASCADE;
DROP VIEW IF EXISTS v_store_spend CASCADE;
DROP VIEW IF EXISTS v_contractor_performance CASCADE;
