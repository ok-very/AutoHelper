-- Migration: 0006_mail_triage.sql
-- Description: Add triage columns to transient_emails for manual triage workflow

ALTER TABLE transient_emails ADD COLUMN triage_status TEXT DEFAULT 'pending';
ALTER TABLE transient_emails ADD COLUMN triage_notes TEXT;
ALTER TABLE transient_emails ADD COLUMN triaged_at DATETIME;
