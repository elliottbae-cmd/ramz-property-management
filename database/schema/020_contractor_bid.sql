-- 020: Add contractor_bid to tickets
-- Tracks what the contractor quoted separately from PSP's internal estimate
-- and the final invoiced amount. Enables bid accuracy reporting per contractor.

ALTER TABLE tickets
    ADD COLUMN IF NOT EXISTS contractor_bid NUMERIC(10, 2);

COMMENT ON COLUMN tickets.contractor_bid IS
    'The amount the contractor bid/quoted for the job, entered when PSP receives the estimate. '
    'Compared against actual_cost at closeout to measure contractor bid accuracy.';
