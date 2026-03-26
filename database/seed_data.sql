-- ============================================================
-- Ram-Z Property Management App — Seed Data
-- Run this after schema.sql to populate initial data
-- ============================================================

-- ============================================================
-- FORM CATEGORIES
-- ============================================================

INSERT INTO form_categories (name, display_order, is_active, requires_serial, icon) VALUES
    ('BOH (Back of House)', 1, true, true, '🍳'),
    ('FOH (Front of House)', 2, true, true, '🪑'),
    ('HVAC', 3, true, true, '❄️'),
    ('Roof', 4, true, false, '🏠'),
    ('Parking Lot', 5, true, false, '🅿️'),
    ('Building Exterior', 6, true, false, '🏢'),
    ('Lighting', 7, true, false, '💡'),
    ('Landscaping', 8, true, false, '🌿'),
    ('Plumbing', 9, true, false, '🔧'),
    ('Electrical', 10, true, false, '⚡'),
    ('Signage', 11, true, false, '📋'),
    ('Other', 99, true, false, '📝');

-- ============================================================
-- FORM URGENCY LEVELS
-- ============================================================

INSERT INTO form_urgency_levels (name, display_order, color, sla_hours, is_active) VALUES
    ('Not Urgent', 1, '#4CAF50', 168, true),         -- 7 days
    ('Somewhat Urgent', 2, '#FF9800', 72, true),      -- 3 days
    ('Extremely Urgent', 3, '#F44336', 24, true),     -- 1 day
    ('911 Emergency', 4, '#B71C1C', 4, true);         -- 4 hours

-- ============================================================
-- APPROVAL SETTINGS (all three tiers required initially)
-- ============================================================

INSERT INTO approval_settings (role, max_auto_approve, requires_approval_from, is_active) VALUES
    ('gm', 0, '{"dm", "director"}', true),
    ('dm', 0, '{"director"}', true),
    ('director', 0, '{}', true);

-- ============================================================
-- SAMPLE STORES (replace with actual Ram-Z locations)
-- ============================================================

INSERT INTO stores (store_number, name, address, city, state, region) VALUES
    ('001', 'Ram-Z #001 - Sample Downtown', '123 Main St', 'Omaha', 'NE', 'Nebraska'),
    ('002', 'Ram-Z #002 - Sample West', '456 West Blvd', 'Omaha', 'NE', 'Nebraska'),
    ('003', 'Ram-Z #003 - Sample East', '789 East Ave', 'Lincoln', 'NE', 'Nebraska'),
    ('004', 'Ram-Z #004 - Sample KC North', '101 North Rd', 'Kansas City', 'MO', 'Missouri'),
    ('005', 'Ram-Z #005 - Sample KC South', '202 South Dr', 'Kansas City', 'MO', 'Missouri');

-- ============================================================
-- SAMPLE CONTRACTORS
-- ============================================================

INSERT INTO contractors (company_name, contact_name, phone, email, trades, service_regions, is_active, is_preferred) VALUES
    ('Midwest HVAC Solutions', 'John Smith', '402-555-0101', 'john@midwesthvac.com',
     '{"HVAC"}', '{"Nebraska", "Missouri"}', true, true),
    ('Pro Roof Repair', 'Sarah Johnson', '402-555-0102', 'sarah@proroof.com',
     '{"Roof"}', '{"Nebraska"}', true, true),
    ('All-Star Plumbing', 'Mike Davis', '816-555-0103', 'mike@allstarplumbing.com',
     '{"Plumbing"}', '{"Missouri", "Kansas"}', true, false),
    ('Heartland Electric', 'Lisa Brown', '402-555-0104', 'lisa@heartlandelectric.com',
     '{"Electrical", "Lighting"}', '{"Nebraska", "Missouri"}', true, true),
    ('Green Thumb Landscaping', 'Tom Wilson', '402-555-0105', 'tom@greenthumb.com',
     '{"Landscaping"}', '{"Nebraska"}', true, false),
    ('Metro Paving Co', 'Chris Anderson', '816-555-0106', 'chris@metropaving.com',
     '{"Parking Lot"}', '{"Missouri", "Kansas"}', true, false),
    ('ABC General Contractors', 'Dan Martinez', '402-555-0107', 'dan@abcgeneral.com',
     '{"BOH (Back of House)", "FOH (Front of House)", "Building Exterior", "Other"}',
     '{"Nebraska", "Missouri"}', true, true),
    ('Sign Masters', 'Amy Taylor', '402-555-0108', 'amy@signmasters.com',
     '{"Signage"}', '{"Nebraska", "Missouri"}', true, false);

-- ============================================================
-- NOTE: User accounts must be created through Supabase Auth first,
-- then the users table is populated with their profile info.
-- The first admin user should be created manually:
--
-- 1. Sign up via the app login page
-- 2. Run this SQL to promote to admin:
--    UPDATE users SET role = 'admin' WHERE email = 'your-admin@email.com';
-- ============================================================
