-- 008: Knowledge Base (Troubleshooting Tips) and Feedback

-- Knowledge Base
CREATE TABLE knowledge_base (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    equipment_type TEXT NOT NULL,
    issue_category TEXT NOT NULL,
    title TEXT NOT NULL,
    steps JSONB NOT NULL,
    difficulty_level TEXT DEFAULT 'basic',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Knowledge Base Feedback
CREATE TABLE knowledge_base_feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    knowledge_base_id UUID NOT NULL REFERENCES knowledge_base(id) ON DELETE CASCADE,
    ticket_id UUID REFERENCES tickets(id),
    was_helpful BOOLEAN NOT NULL,
    user_id UUID NOT NULL REFERENCES auth.users(id),
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_kb_lookup ON knowledge_base(equipment_type, issue_category);
CREATE INDEX idx_kb_active ON knowledge_base(is_active);
CREATE INDEX idx_kb_feedback_kb ON knowledge_base_feedback(knowledge_base_id);
CREATE INDEX idx_kb_feedback_helpful ON knowledge_base_feedback(was_helpful);

-- Enable RLS
ALTER TABLE knowledge_base ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_base_feedback ENABLE ROW LEVEL SECURITY;
