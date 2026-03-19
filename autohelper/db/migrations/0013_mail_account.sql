-- Migration: 0013_mail_account.sql
-- Description: Track which Outlook account/mailbox each email came from

ALTER TABLE transient_emails ADD COLUMN account TEXT DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_transient_emails_account ON transient_emails(account);
