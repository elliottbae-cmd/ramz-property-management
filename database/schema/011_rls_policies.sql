-- 011: RLS Policies and Helper Functions

------------------------------------------------------------
-- HELPER FUNCTIONS (SECURITY DEFINER to avoid recursion)
------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.get_user_tier()
RETURNS user_tier AS $$
    SELECT user_tier FROM public.users WHERE id = auth.uid();
$$ LANGUAGE sql SECURITY DEFINER STABLE;

CREATE OR REPLACE FUNCTION public.get_user_client_id()
RETURNS UUID AS $$
    SELECT client_id FROM public.users WHERE id = auth.uid();
$$ LANGUAGE sql SECURITY DEFINER STABLE;

CREATE OR REPLACE FUNCTION public.is_psp_user()
RETURNS BOOLEAN AS $$
    SELECT EXISTS(SELECT 1 FROM public.users WHERE id = auth.uid() AND user_tier = 'psp');
$$ LANGUAGE sql SECURITY DEFINER STABLE;

CREATE OR REPLACE FUNCTION public.get_psp_role()
RETURNS psp_role AS $$
    SELECT psp_role FROM public.users WHERE id = auth.uid();
$$ LANGUAGE sql SECURITY DEFINER STABLE;

CREATE OR REPLACE FUNCTION public.get_client_role()
RETURNS client_role AS $$
    SELECT client_role FROM public.users WHERE id = auth.uid();
$$ LANGUAGE sql SECURITY DEFINER STABLE;

CREATE OR REPLACE FUNCTION public.get_psp_current_client()
RETURNS UUID AS $$
    SELECT client_id FROM public.psp_client_access
    WHERE psp_user_id = auth.uid() AND is_current = TRUE
    LIMIT 1;
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- The "effective client" function: returns the client_id the user should see
CREATE OR REPLACE FUNCTION public.effective_client_id()
RETURNS UUID AS $$
    SELECT CASE
        WHEN public.is_psp_user() THEN public.get_psp_current_client()
        ELSE public.get_user_client_id()
    END;
$$ LANGUAGE sql SECURITY DEFINER STABLE;

------------------------------------------------------------
-- CLIENTS TABLE POLICIES
------------------------------------------------------------

CREATE POLICY "PSP can do everything on clients" ON clients
    FOR ALL TO authenticated
    USING (public.is_psp_user());

CREATE POLICY "Client users can read their own client" ON clients
    FOR SELECT TO authenticated
    USING (id = public.get_user_client_id());

------------------------------------------------------------
-- STORES TABLE POLICIES
------------------------------------------------------------

CREATE POLICY "PSP can manage all stores" ON stores
    FOR ALL TO authenticated
    USING (public.is_psp_user());

CREATE POLICY "Client users can read their stores" ON stores
    FOR SELECT TO authenticated
    USING (client_id = public.get_user_client_id());

------------------------------------------------------------
-- USERS TABLE POLICIES
------------------------------------------------------------

CREATE POLICY "PSP can manage all users" ON users
    FOR ALL TO authenticated
    USING (public.is_psp_user());

CREATE POLICY "Client users can read users in their client" ON users
    FOR SELECT TO authenticated
    USING (
        client_id = public.get_user_client_id()
        OR user_tier = 'psp'  -- Client users can see PSP users (for assignment display)
    );

CREATE POLICY "Users can insert own profile" ON users
    FOR INSERT TO authenticated
    WITH CHECK (id = auth.uid());

CREATE POLICY "Users can update own profile" ON users
    FOR UPDATE TO authenticated
    USING (id = auth.uid() OR public.is_psp_user());

------------------------------------------------------------
-- USER_STORES TABLE POLICIES
------------------------------------------------------------

CREATE POLICY "PSP can manage user_stores" ON user_stores
    FOR ALL TO authenticated
    USING (public.is_psp_user());

CREATE POLICY "Client users can read user_stores" ON user_stores
    FOR SELECT TO authenticated
    USING (
        user_id = auth.uid()
        OR store_id IN (SELECT id FROM stores WHERE client_id = public.get_user_client_id())
    );

------------------------------------------------------------
-- PSP_CLIENT_ACCESS TABLE POLICIES
------------------------------------------------------------

CREATE POLICY "PSP users manage their own access" ON psp_client_access
    FOR ALL TO authenticated
    USING (psp_user_id = auth.uid() AND public.is_psp_user());

------------------------------------------------------------
-- EQUIPMENT TABLE POLICIES
------------------------------------------------------------

CREATE POLICY "PSP can manage all equipment" ON equipment
    FOR ALL TO authenticated
    USING (public.is_psp_user());

CREATE POLICY "Client users can read their equipment" ON equipment
    FOR SELECT TO authenticated
    USING (
        store_id IN (SELECT id FROM stores WHERE client_id = public.get_user_client_id())
    );

CREATE POLICY "Client users can insert equipment" ON equipment
    FOR INSERT TO authenticated
    WITH CHECK (
        store_id IN (SELECT id FROM stores WHERE client_id = public.get_user_client_id())
    );

------------------------------------------------------------
-- EQUIPMENT_WARRANTIES TABLE POLICIES
------------------------------------------------------------

CREATE POLICY "PSP can manage all warranties" ON equipment_warranties
    FOR ALL TO authenticated
    USING (public.is_psp_user());

CREATE POLICY "Client users can read their warranties" ON equipment_warranties
    FOR SELECT TO authenticated
    USING (
        equipment_id IN (
            SELECT e.id FROM equipment e
            JOIN stores s ON e.store_id = s.id
            WHERE s.client_id = public.get_user_client_id()
        )
    );

------------------------------------------------------------
-- TICKETS TABLE POLICIES
------------------------------------------------------------

CREATE POLICY "PSP can manage all tickets" ON tickets
    FOR ALL TO authenticated
    USING (public.is_psp_user());

CREATE POLICY "Client users can read relevant tickets" ON tickets
    FOR SELECT TO authenticated
    USING (
        client_id = public.get_user_client_id()
        AND (
            submitted_by = auth.uid()
            OR assigned_to = auth.uid()
            OR store_id IN (SELECT store_id FROM users WHERE id = auth.uid())
            OR store_id IN (SELECT store_id FROM user_stores WHERE user_id = auth.uid())
            OR public.get_client_role() IN ('coo', 'admin', 'vp', 'doo')
        )
    );

CREATE POLICY "Client users can create tickets" ON tickets
    FOR INSERT TO authenticated
    WITH CHECK (client_id = public.get_user_client_id());

CREATE POLICY "Client users can update tickets" ON tickets
    FOR UPDATE TO authenticated
    USING (
        client_id = public.get_user_client_id()
        AND (
            submitted_by = auth.uid()
            OR assigned_to = auth.uid()
            OR public.get_client_role() IN ('coo', 'admin', 'vp', 'doo', 'dm')
        )
    );

------------------------------------------------------------
-- TICKET_PHOTOS TABLE POLICIES
------------------------------------------------------------

CREATE POLICY "PSP can manage all photos" ON ticket_photos
    FOR ALL TO authenticated
    USING (public.is_psp_user());

CREATE POLICY "Client users can read photos for their tickets" ON ticket_photos
    FOR SELECT TO authenticated
    USING (
        ticket_id IN (SELECT id FROM tickets WHERE client_id = public.get_user_client_id())
    );

CREATE POLICY "Client users can upload photos" ON ticket_photos
    FOR INSERT TO authenticated
    WITH CHECK (
        ticket_id IN (SELECT id FROM tickets WHERE client_id = public.get_user_client_id())
    );

------------------------------------------------------------
-- TICKET_COMMENTS TABLE POLICIES
------------------------------------------------------------

CREATE POLICY "PSP can manage all comments" ON ticket_comments
    FOR ALL TO authenticated
    USING (public.is_psp_user());

CREATE POLICY "Client users can read non-internal comments" ON ticket_comments
    FOR SELECT TO authenticated
    USING (
        ticket_id IN (SELECT id FROM tickets WHERE client_id = public.get_user_client_id())
        AND (is_internal = FALSE OR is_internal IS NULL)
    );

CREATE POLICY "Client users can add comments" ON ticket_comments
    FOR INSERT TO authenticated
    WITH CHECK (
        ticket_id IN (SELECT id FROM tickets WHERE client_id = public.get_user_client_id())
    );

------------------------------------------------------------
-- APPROVALS TABLE POLICIES
------------------------------------------------------------

CREATE POLICY "PSP can manage all approvals" ON approvals
    FOR ALL TO authenticated
    USING (public.is_psp_user());

CREATE POLICY "Client users can read their approvals" ON approvals
    FOR SELECT TO authenticated
    USING (client_id = public.get_user_client_id());

CREATE POLICY "Client users can update approvals assigned to them" ON approvals
    FOR UPDATE TO authenticated
    USING (
        client_id = public.get_user_client_id()
        AND (approver_id = auth.uid() OR public.get_client_role() IN ('coo', 'admin'))
    );

------------------------------------------------------------
-- APPROVAL_CHAIN_CONFIG TABLE POLICIES
------------------------------------------------------------

CREATE POLICY "PSP can manage approval configs" ON approval_chain_config
    FOR ALL TO authenticated
    USING (public.is_psp_user());

CREATE POLICY "Client admins can read their configs" ON approval_chain_config
    FOR SELECT TO authenticated
    USING (client_id = public.get_user_client_id());

------------------------------------------------------------
-- APPROVAL_THRESHOLDS TABLE POLICIES
------------------------------------------------------------

CREATE POLICY "PSP can manage thresholds" ON approval_thresholds
    FOR ALL TO authenticated
    USING (public.is_psp_user());

CREATE POLICY "Client admins can read their thresholds" ON approval_thresholds
    FOR SELECT TO authenticated
    USING (client_id = public.get_user_client_id());

------------------------------------------------------------
-- CONTRACTORS TABLE POLICIES (shared, no client_id)
------------------------------------------------------------

CREATE POLICY "Anyone can read active contractors" ON contractors
    FOR SELECT TO authenticated
    USING (is_active = TRUE OR public.is_psp_user());

CREATE POLICY "PSP can manage contractors" ON contractors
    FOR INSERT TO authenticated
    WITH CHECK (public.is_psp_user());

CREATE POLICY "PSP can update contractors" ON contractors
    FOR UPDATE TO authenticated
    USING (public.is_psp_user());

CREATE POLICY "PSP can delete contractors" ON contractors
    FOR DELETE TO authenticated
    USING (public.is_psp_user());

------------------------------------------------------------
-- CONTRACTOR_GEOGRAPHIC_EXCEPTIONS TABLE POLICIES
------------------------------------------------------------

CREATE POLICY "PSP can manage geo exceptions" ON contractor_geographic_exceptions
    FOR ALL TO authenticated
    USING (public.is_psp_user());

CREATE POLICY "Anyone can read geo exceptions" ON contractor_geographic_exceptions
    FOR SELECT TO authenticated
    USING (TRUE);

------------------------------------------------------------
-- CONTRACTOR_REVIEWS TABLE POLICIES
------------------------------------------------------------

CREATE POLICY "Anyone can read reviews" ON contractor_reviews
    FOR SELECT TO authenticated
    USING (TRUE);

CREATE POLICY "Authenticated users can add reviews" ON contractor_reviews
    FOR INSERT TO authenticated
    WITH CHECK (reviewed_by = auth.uid());

CREATE POLICY "PSP can manage reviews" ON contractor_reviews
    FOR ALL TO authenticated
    USING (public.is_psp_user());

------------------------------------------------------------
-- WORK_ORDERS TABLE POLICIES
------------------------------------------------------------

CREATE POLICY "PSP can manage all work orders" ON work_orders
    FOR ALL TO authenticated
    USING (public.is_psp_user());

CREATE POLICY "Client users can read their work orders" ON work_orders
    FOR SELECT TO authenticated
    USING (client_id = public.get_user_client_id());

------------------------------------------------------------
-- WARRANTY_CLAIMS TABLE POLICIES
------------------------------------------------------------

CREATE POLICY "PSP can manage all warranty claims" ON warranty_claims
    FOR ALL TO authenticated
    USING (public.is_psp_user());

CREATE POLICY "Client users can read their warranty claims" ON warranty_claims
    FOR SELECT TO authenticated
    USING (
        ticket_id IN (SELECT id FROM tickets WHERE client_id = public.get_user_client_id())
    );

------------------------------------------------------------
-- KNOWLEDGE_BASE TABLE POLICIES
------------------------------------------------------------

CREATE POLICY "Anyone can read active KB entries" ON knowledge_base
    FOR SELECT TO authenticated
    USING (is_active = TRUE OR public.is_psp_user());

CREATE POLICY "PSP can manage KB" ON knowledge_base
    FOR ALL TO authenticated
    USING (public.is_psp_user());

------------------------------------------------------------
-- KNOWLEDGE_BASE_FEEDBACK TABLE POLICIES
------------------------------------------------------------

CREATE POLICY "Anyone can read KB feedback" ON knowledge_base_feedback
    FOR SELECT TO authenticated
    USING (TRUE);

CREATE POLICY "Authenticated users can add KB feedback" ON knowledge_base_feedback
    FOR INSERT TO authenticated
    WITH CHECK (user_id = auth.uid());

------------------------------------------------------------
-- FORM CONFIG TABLE POLICIES
------------------------------------------------------------

CREATE POLICY "Anyone can read form categories" ON form_categories
    FOR SELECT TO authenticated
    USING (
        client_id IS NULL
        OR client_id = public.get_user_client_id()
        OR public.is_psp_user()
    );

CREATE POLICY "PSP can manage form categories" ON form_categories
    FOR ALL TO authenticated
    USING (public.is_psp_user());

CREATE POLICY "Anyone can read urgency levels" ON form_urgency_levels
    FOR SELECT TO authenticated
    USING (
        client_id IS NULL
        OR client_id = public.get_user_client_id()
        OR public.is_psp_user()
    );

CREATE POLICY "PSP can manage urgency levels" ON form_urgency_levels
    FOR ALL TO authenticated
    USING (public.is_psp_user());

CREATE POLICY "Anyone can read form fields" ON form_fields
    FOR SELECT TO authenticated
    USING (
        client_id IS NULL
        OR client_id = public.get_user_client_id()
        OR public.is_psp_user()
    );

CREATE POLICY "PSP can manage form fields" ON form_fields
    FOR ALL TO authenticated
    USING (public.is_psp_user());

------------------------------------------------------------
-- AUDIT_LOG TABLE POLICIES
------------------------------------------------------------

CREATE POLICY "PSP can read all audit logs" ON audit_log
    FOR SELECT TO authenticated
    USING (public.is_psp_user());

CREATE POLICY "Client admins can read their audit logs" ON audit_log
    FOR SELECT TO authenticated
    USING (
        client_id = public.get_user_client_id()
        AND public.get_client_role() IN ('coo', 'admin')
    );

CREATE POLICY "Anyone can insert audit logs" ON audit_log
    FOR INSERT TO authenticated
    WITH CHECK (user_id = auth.uid());
