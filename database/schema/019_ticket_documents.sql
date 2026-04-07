-- 019: Ticket Documents (estimates, invoices, warranty docs, etc.)

CREATE TABLE IF NOT EXISTS ticket_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES clients(id),
    document_type TEXT NOT NULL DEFAULT 'other',
    -- document_type values: 'estimate', 'invoice', 'warranty', 'photo', 'other'
    file_name TEXT NOT NULL,
    file_url TEXT NOT NULL,
    file_size_bytes INT,
    uploaded_by UUID REFERENCES auth.users(id),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ticket_docs_ticket ON ticket_documents(ticket_id);
CREATE INDEX IF NOT EXISTS idx_ticket_docs_client ON ticket_documents(client_id);
CREATE INDEX IF NOT EXISTS idx_ticket_docs_type ON ticket_documents(document_type);

ALTER TABLE ticket_documents ENABLE ROW LEVEL SECURITY;

-- PSP can manage all documents
CREATE POLICY "PSP can manage all ticket documents" ON ticket_documents
    FOR ALL TO authenticated
    USING (public.is_psp_user());

-- Client users can read documents for their tickets
CREATE POLICY "Client users can read their ticket documents" ON ticket_documents
    FOR SELECT TO authenticated
    USING (client_id = public.get_user_client_id());

-- Client users can upload documents
CREATE POLICY "Client users can upload ticket documents" ON ticket_documents
    FOR INSERT TO authenticated
    WITH CHECK (client_id = public.get_user_client_id());
