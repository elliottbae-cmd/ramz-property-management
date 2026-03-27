-- 012: Reporting Views

-- Ticket metrics view for reporting
CREATE OR REPLACE VIEW v_ticket_metrics AS
SELECT
    t.client_id,
    t.store_id,
    s.store_number,
    s.name AS store_name,
    s.city AS store_city,
    s.state AS store_state,
    t.id AS ticket_id,
    t.ticket_number,
    t.category,
    t.urgency,
    t.status,
    t.estimated_cost,
    t.actual_cost,
    t.submitted_by,
    t.assigned_to,
    t.created_at,
    t.resolved_at,
    t.warranty_checked,
    t.troubleshooting_resolved,
    CASE
        WHEN t.resolved_at IS NOT NULL
        THEN EXTRACT(EPOCH FROM (t.resolved_at - t.created_at)) / 3600
        ELSE NULL
    END AS hours_to_resolve,
    DATE_TRUNC('week', t.created_at) AS week,
    DATE_TRUNC('month', t.created_at) AS month,
    DATE_TRUNC('year', t.created_at) AS year
FROM tickets t
JOIN stores s ON t.store_id = s.id;

-- Store spend summary view
CREATE OR REPLACE VIEW v_store_spend AS
SELECT
    t.client_id,
    t.store_id,
    s.store_number,
    s.name AS store_name,
    COUNT(t.id) AS total_tickets,
    COUNT(CASE WHEN t.status = 'completed' THEN 1 END) AS completed_tickets,
    COUNT(CASE WHEN t.status NOT IN ('completed', 'closed', 'rejected') THEN 1 END) AS open_tickets,
    COALESCE(SUM(t.actual_cost), 0) AS total_actual_spend,
    COALESCE(SUM(t.estimated_cost), 0) AS total_estimated_spend,
    COALESCE(AVG(
        CASE WHEN t.resolved_at IS NOT NULL
        THEN EXTRACT(EPOCH FROM (t.resolved_at - t.created_at)) / 3600
        END
    ), 0) AS avg_hours_to_resolve
FROM tickets t
JOIN stores s ON t.store_id = s.id
GROUP BY t.client_id, t.store_id, s.store_number, s.name;

-- Contractor performance view
CREATE OR REPLACE VIEW v_contractor_performance AS
SELECT
    c.id AS contractor_id,
    c.company_name,
    c.trades,
    c.service_states,
    c.is_preferred,
    c.avg_rating,
    c.total_jobs,
    COUNT(wo.id) AS work_order_count,
    COUNT(CASE WHEN wo.status = 'completed' THEN 1 END) AS completed_count,
    COALESCE(SUM(wo.amount), 0) AS total_billed,
    COALESCE(AVG(wo.amount), 0) AS avg_job_cost
FROM contractors c
LEFT JOIN work_orders wo ON c.id = wo.contractor_id
GROUP BY c.id, c.company_name, c.trades, c.service_states, c.is_preferred, c.avg_rating, c.total_jobs;
