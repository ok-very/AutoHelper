-- Add address fields to contacts hub
ALTER TABLE contacts ADD COLUMN street_address TEXT DEFAULT '';
ALTER TABLE contacts ADD COLUMN city TEXT DEFAULT '';
ALTER TABLE contacts ADD COLUMN state TEXT DEFAULT '';
ALTER TABLE contacts ADD COLUMN postal_code TEXT DEFAULT '';
ALTER TABLE contacts ADD COLUMN country TEXT DEFAULT '';
