-- 017: Add CofO date, opening date, and health permit fields to stores table
--
-- cofo_date         : Certificate of Occupancy date — issued by the city/jurisdiction
--                     when construction is complete and the building is approved for use.
-- opening_date      : Date the store opened for business (may be days/weeks after CofO).
-- health_permit_number : State/county health department permit number.
-- health_permit_expiry : Health permit expiration date (needs annual renewal).
-- closeout_imported_at : Timestamp when a closeout package was last imported for this store.
--
-- Run this in Supabase SQL editor.

ALTER TABLE stores
    ADD COLUMN IF NOT EXISTS cofo_date DATE,
    ADD COLUMN IF NOT EXISTS opening_date DATE,
    ADD COLUMN IF NOT EXISTS health_permit_number TEXT,
    ADD COLUMN IF NOT EXISTS health_permit_expiry DATE,
    ADD COLUMN IF NOT EXISTS closeout_imported_at TIMESTAMPTZ;

COMMENT ON COLUMN stores.cofo_date IS
    'Certificate of Occupancy date — issued by jurisdiction when construction is complete.';

COMMENT ON COLUMN stores.opening_date IS
    'Date store opened for business. May be days/weeks after cofo_date.';

COMMENT ON COLUMN stores.health_permit_number IS
    'State/county health department permit number.';

COMMENT ON COLUMN stores.health_permit_expiry IS
    'Health permit expiration date — typically annual renewal required.';

COMMENT ON COLUMN stores.closeout_imported_at IS
    'Timestamp of last closeout package import for this store (via PSP app importer).';
