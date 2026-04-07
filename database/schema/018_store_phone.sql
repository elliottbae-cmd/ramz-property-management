-- Migration 018: Add phone number to stores table

ALTER TABLE stores
    ADD COLUMN IF NOT EXISTS phone TEXT;
