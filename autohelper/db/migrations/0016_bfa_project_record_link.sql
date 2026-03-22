-- Add durable identity link from BFA entries to ProjectRecords.
-- Eliminates fragile name-based matching between ClickUp and BFA Todo.
ALTER TABLE bfa_projects ADD COLUMN project_record_id TEXT;
CREATE INDEX idx_bfa_projects_record_id ON bfa_projects(project_record_id);
