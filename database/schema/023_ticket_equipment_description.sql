-- 023: Add equipment_description to tickets
-- Stores free-text equipment info when a GM submits a ticket for unlisted
-- equipment. PSP reviews and promotes to the equipment inventory if valid.

ALTER TABLE tickets ADD COLUMN IF NOT EXISTS equipment_description TEXT;
