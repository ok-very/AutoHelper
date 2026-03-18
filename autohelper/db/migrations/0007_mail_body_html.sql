-- Migration: 0007_mail_body_html.sql
-- Description: Add body_html column for storing full HTML email content

ALTER TABLE transient_emails ADD COLUMN body_html TEXT;
