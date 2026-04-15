-- Fix contractor_reviews FK to cascade on ticket delete
ALTER TABLE contractor_reviews
  DROP CONSTRAINT IF EXISTS contractor_reviews_ticket_id_fkey,
  ADD CONSTRAINT contractor_reviews_ticket_id_fkey
    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE;
