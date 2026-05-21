-- 022: Fix ticket_comments.user_id FK to reference public.users
-- PostgREST cannot auto-join across auth.users → public.users boundary,
-- so the select("*, users(full_name)") query was throwing an exception every
-- time, causing cache poisoning (empty list cached for 120s) and comments
-- never rendering.

ALTER TABLE ticket_comments
    DROP CONSTRAINT IF EXISTS ticket_comments_user_id_fkey,
    ADD CONSTRAINT ticket_comments_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;
