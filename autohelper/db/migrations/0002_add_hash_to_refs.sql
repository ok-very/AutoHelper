-- Add content_hash to refs for robust resolution
ALTER TABLE refs ADD COLUMN content_hash TEXT;
CREATE INDEX idx_refs_hash ON refs(content_hash);
