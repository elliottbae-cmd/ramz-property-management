-- 016: Add manufacture_date and serial_decode_method to equipment table
--
-- manufacture_date: the date the unit was manufactured, decoded from the
--   serial number by our Python serial decoder. Separate from install_date
--   (when it was installed at the store). Used for warranty start calculation
--   when no install date is available, and for equipment age tracking.
--
-- serial_decode_method: records how the manufacture date was determined
--   (e.g. "Hoshizaki [year_letter][seq][month_letter] format, verified")
--   so PSP can audit the source of the date.
--
-- Run this in Supabase SQL editor.

ALTER TABLE equipment
    ADD COLUMN IF NOT EXISTS manufacture_date DATE,
    ADD COLUMN IF NOT EXISTS serial_decode_method TEXT;

COMMENT ON COLUMN equipment.manufacture_date IS
    'Date unit was manufactured, decoded from serial number. '
    'Separate from install_date (when installed at store).';

COMMENT ON COLUMN equipment.serial_decode_method IS
    'How manufacture_date was determined — e.g. serial decoder method or manual entry.';
