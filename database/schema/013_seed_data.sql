-- 013: Seed Data

------------------------------------------------------------
-- INSERT RAM-Z AS FIRST CLIENT
------------------------------------------------------------
INSERT INTO clients (id, name, slug, company_name, tagline, primary_color, secondary_color, accent_color, surface_color)
VALUES (
    'a0000000-0000-0000-0000-000000000001',
    'Ram-Z Restaurant Group',
    'ramz',
    'Ram-Z Restaurant Group',
    'Property Management',
    '#C4A04D',
    '#1B3A4B',
    '#C4A04D',
    '#F7F4EE'
);

------------------------------------------------------------
-- GLOBAL FORM CATEGORIES (client_id = NULL = defaults)
------------------------------------------------------------
INSERT INTO form_categories (client_id, name, display_order, is_active, requires_serial, icon) VALUES
(NULL, 'BOH (Back of House)', 1, TRUE, TRUE, '🍳'),
(NULL, 'FOH (Front of House)', 2, TRUE, FALSE, '🪑'),
(NULL, 'HVAC', 3, TRUE, TRUE, '❄️'),
(NULL, 'Roof', 4, TRUE, FALSE, '🏠'),
(NULL, 'Parking Lot', 5, TRUE, FALSE, '🅿️'),
(NULL, 'Building Exterior', 6, TRUE, FALSE, '🏢'),
(NULL, 'Lighting', 7, TRUE, FALSE, '💡'),
(NULL, 'Landscaping', 8, TRUE, FALSE, '🌿'),
(NULL, 'Plumbing', 9, TRUE, TRUE, '🔧'),
(NULL, 'Electrical', 10, TRUE, TRUE, '⚡'),
(NULL, 'Signage', 11, TRUE, FALSE, '📋'),
(NULL, 'Other', 12, TRUE, FALSE, '📦');

------------------------------------------------------------
-- GLOBAL URGENCY LEVELS (client_id = NULL = defaults)
------------------------------------------------------------
INSERT INTO form_urgency_levels (client_id, name, display_order, color, sla_hours, is_active) VALUES
(NULL, 'Not Urgent', 1, '#4CAF50', 168, TRUE),
(NULL, 'Somewhat Urgent', 2, '#FF9800', 72, TRUE),
(NULL, 'Extremely Urgent', 3, '#F44336', 24, TRUE),
(NULL, '911 Emergency', 4, '#9C27B0', 4, TRUE);

------------------------------------------------------------
-- DEFAULT APPROVAL CHAIN FOR RAM-Z
------------------------------------------------------------
INSERT INTO approval_chain_config (client_id, step_order, role_required, min_amount, max_auto_approve, is_active) VALUES
('a0000000-0000-0000-0000-000000000001', 1, 'gm', 0, 500, TRUE),
('a0000000-0000-0000-0000-000000000001', 2, 'dm', 500, 2500, TRUE),
('a0000000-0000-0000-0000-000000000001', 3, 'vp', 2500, 10000, TRUE),
('a0000000-0000-0000-0000-000000000001', 4, 'coo', 10000, NULL, TRUE);

-- Default approval threshold for Ram-Z
INSERT INTO approval_thresholds (client_id, threshold_amount) VALUES
('a0000000-0000-0000-0000-000000000001', 1000.00);

------------------------------------------------------------
-- SAMPLE STORES FOR RAM-Z
------------------------------------------------------------
INSERT INTO stores (client_id, store_number, name, address, city, state, zip_code, region) VALUES
('a0000000-0000-0000-0000-000000000001', '001', 'Ram-Z - Omaha West', '1234 West Dodge Rd', 'Omaha', 'NE', '68114', 'Nebraska'),
('a0000000-0000-0000-0000-000000000001', '002', 'Ram-Z - Omaha South', '5678 South 72nd St', 'Omaha', 'NE', '68127', 'Nebraska'),
('a0000000-0000-0000-0000-000000000001', '003', 'Ram-Z - Lincoln', '910 O Street', 'Lincoln', 'NE', '68508', 'Nebraska'),
('a0000000-0000-0000-0000-000000000001', '004', 'Ram-Z - Kansas City North', '2345 Barry Rd', 'Kansas City', 'MO', '64154', 'Kansas City'),
('a0000000-0000-0000-0000-000000000001', '005', 'Ram-Z - Kansas City South', '6789 State Line Rd', 'Kansas City', 'MO', '64114', 'Kansas City');

------------------------------------------------------------
-- SAMPLE CONTRACTORS (shared across all clients)
------------------------------------------------------------
INSERT INTO contractors (company_name, contact_name, phone, email, trades, service_cities, service_states, is_preferred, is_active) VALUES
('Midwest HVAC Solutions', 'Mike Johnson', '(402) 555-0101', 'mike@midwesthvac.com',
 ARRAY['HVAC'], ARRAY['Omaha', 'Lincoln'], ARRAY['NE'], TRUE, TRUE),

('KC Plumbing Pros', 'Sarah Williams', '(816) 555-0202', 'sarah@kcplumbing.com',
 ARRAY['Plumbing'], ARRAY['Kansas City'], ARRAY['MO', 'KS'], TRUE, TRUE),

('All-State Roofing', 'Tom Davis', '(402) 555-0303', 'tom@allstateroofing.com',
 ARRAY['Roof'], ARRAY['Omaha', 'Lincoln', 'Kansas City'], ARRAY['NE', 'MO', 'KS'], FALSE, TRUE),

('Bright Lights Electric', 'Jenny Chen', '(816) 555-0404', 'jenny@brightlights.com',
 ARRAY['Electrical', 'Lighting'], ARRAY['Kansas City'], ARRAY['MO', 'KS'], TRUE, TRUE),

('Green Thumb Landscaping', 'Carlos Martinez', '(402) 555-0505', 'carlos@greenthumb.com',
 ARRAY['Landscaping'], ARRAY['Omaha', 'Lincoln'], ARRAY['NE'], FALSE, TRUE),

('Heartland Commercial Kitchen', 'Bob Anderson', '(402) 555-0606', 'bob@heartlandkitchen.com',
 ARRAY['BOH (Back of House)', 'FOH (Front of House)'], ARRAY['Omaha', 'Lincoln'], ARRAY['NE'], TRUE, TRUE),

('Metro Paving & Concrete', 'Lisa Park', '(816) 555-0707', 'lisa@metropaving.com',
 ARRAY['Parking Lot', 'Building Exterior'], ARRAY['Kansas City'], ARRAY['MO', 'KS'], FALSE, TRUE),

('Cornhusker Signs', 'Dave Wilson', '(402) 555-0808', 'dave@cornhuskersigns.com',
 ARRAY['Signage'], ARRAY['Omaha', 'Lincoln'], ARRAY['NE'], FALSE, TRUE);
