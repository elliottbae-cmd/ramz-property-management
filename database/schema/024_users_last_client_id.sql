-- 024: Remember last-used client for PSP users
-- Stored on the user profile so it survives session resets and redeploys.
-- Hydrated automatically on login so PSP users never land on a blank page.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS last_client_id UUID REFERENCES clients(id) ON DELETE SET NULL;
