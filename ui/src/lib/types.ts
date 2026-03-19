// ---------------------------------------------------------------------------
// Identity sub-models
// ---------------------------------------------------------------------------

export interface NameEntry {
  name: string
  type: 'traditional' | 'pseudonym' | 'studio' | 'trade'
}

export interface AffiliationEntry {
  name: string
  type: 'nation' | 'collective' | 'duo_partner' | 'studio_assistant_of' | 'band' | 'organization'
}

export interface LocationEntry {
  place: string
  type: 'origin' | 'home' | 'studio'
}

export interface IdentityTags {
  identities: string[]
  affiliations: AffiliationEntry[]
  locations: LocationEntry[]
}

export interface Identity {
  display_name: string
  first_name: string | null
  last_name: string | null
  names: NameEntry[]
  pronouns: string | null
  career_stage: 'emerging' | 'mid-career' | 'established' | null
  identity_tags: IdentityTags
}

// ---------------------------------------------------------------------------
// Contact / Folder / Document
// ---------------------------------------------------------------------------

export interface Contact {
  email: string | null
  phone: string | null
  website: string | null
  notes: string | null
}

export interface FolderLocation {
  category: string
  folder_path: string
  nation: string | null
  is_primary: boolean
}

export interface DocumentEntry {
  file_path: string
  date: string | null
  is_current: boolean
}

export interface Documents {
  bios: DocumentEntry[]
  cvs: DocumentEntry[]
  tearsheets: DocumentEntry[]
  project_lists: DocumentEntry[]
}

// ---------------------------------------------------------------------------
// Engagement
// ---------------------------------------------------------------------------

export interface PanelEntry {
  date: string | null
  project: string | null
  role: string
}

export interface EOIEntry {
  project_name: string | null
  folder_path: string | null
  file_path: string | null
}

export interface ConceptProposal {
  project_name: string | null
  developer: string | null
  date: string | null
  folder_path: string | null
  file_path: string | null
}

export interface PublicArtProject {
  project_name: string
  developer: string | null
  role: string | null
  status: 'submitted' | 'longlisted' | 'shortlisted' | 'awarded' | 'completed'
  year: string | null
  status_date: string | null
  eoi_ref: string | null
}

export interface Engagement {
  panel_count: number
  panel_history: PanelEntry[]
  public_art_projects: PublicArtProject[]
  eois: EOIEntry[]
  concept_proposals: ConceptProposal[]
}

// ---------------------------------------------------------------------------
// Images / Completeness
// ---------------------------------------------------------------------------

export interface Images {
  count: number
  folder_paths: string[]
}

export interface Completeness {
  has_bio: boolean
  has_cv: boolean
  has_tearsheet: boolean
  has_contact_email: boolean
  has_contact_phone: boolean
  has_website: boolean
  has_images: boolean
  has_pronouns: boolean
  score: number
  gaps: string[]
}

// ---------------------------------------------------------------------------
// AI Enrichment
// ---------------------------------------------------------------------------

export interface AIEnrichment {
  confidence: 'high' | 'med' | 'low'
  model: string
  bio_summary?: string
  medium?: string
  website?: string
}

// ---------------------------------------------------------------------------
// Manifest (full artist detail)
// ---------------------------------------------------------------------------

export interface ArtistManifest {
  artist_id: string
  manifest_version: string
  generated_at: string
  categories: string[]
  identity: Identity
  contact: Contact
  folder_locations: FolderLocation[]
  documents: Documents
  engagement: Engagement
  images: Images
  completeness: Completeness
  _review_notes: string[]
  ai_enrichment?: AIEnrichment
}

// ---------------------------------------------------------------------------
// List view (summary returned by GET /artists)
// ---------------------------------------------------------------------------

export interface ArtistListItem {
  artist_id: string
  display_name: string
  categories: string[]
  completeness: number
  has_bio: boolean
  has_cv: boolean
  has_tearsheet: boolean
  has_contact: boolean
  has_images: boolean
  nations: string[]
  identity_tags: string[]
  review_status: string | null
  // Client-computed
  gap_count: number
  _all_identity: string[]
  primary_identity: string
}

// ---------------------------------------------------------------------------
// Stats (GET /artists/stats)
// ---------------------------------------------------------------------------

export interface ArtistStats {
  total: number
  avg_completeness: number
  needs_review: number
  by_review_status: Record<string, number>
  completeness_by_field: Record<string, number>
}

// ---------------------------------------------------------------------------
// Health report (GET /artists/health)
// ---------------------------------------------------------------------------

export interface HealthRankingItem {
  artist_id: string
  display_name: string
  categories: string[]
  score: number
  gaps: string[]
}

export interface GapAnalysisField {
  missing: number
  total: number
}

export interface BrokenItem {
  artist_id: string
  display_name: string
  reason: string
}

export interface EnrichmentItem {
  artist_id: string
  display_name: string
  missing: string[]
}

export interface ReviewQueueItem {
  artist_id: string
  display_name: string
  review_status: string
  note_count: number
}

export interface HealthReport {
  ranking: HealthRankingItem[]
  gap_analysis: Record<string, GapAnalysisField>
  broken: BrokenItem[]
  enrichment: EnrichmentItem[]
  review_queue: ReviewQueueItem[]
}

// ---------------------------------------------------------------------------
// Reconciliation (GET /artists/reconciliation)
// ---------------------------------------------------------------------------

export interface ReconOrphan {
  artist_id: string
  display_name: string
  project_name: string
  developer?: string
}

export interface ReconStalled {
  artist_id: string
  display_name: string
  project_name: string
  status: string
  project_index: number
}

export interface ReconFuzzy {
  artist_id: string
  display_name: string
  source_name: string
  match_name: string
  score: number
}

export interface ReconPanelGap {
  artist_id: string
  display_name: string
  panel_count: number
}

export interface ReconDuplicate {
  artist_id_a: string
  name_a: string
  artist_id_b: string
  name_b: string
  score: number
}

export interface ReconVariant {
  value_a: string
  count_a: number
  value_b: string
  count_b: number
  score: number
}

export interface ReconAliasArtist {
  artist_id: string
  display_name: string
  type: string
}

export interface ReconAliasConflict {
  shared_name: string
  artists: ReconAliasArtist[]
}

export interface ReconciliationData {
  orphan_eois: ReconOrphan[]
  orphan_proposals: ReconOrphan[]
  stalled_projects: ReconStalled[]
  fuzzy_matches: ReconFuzzy[]
  panel_gaps: ReconPanelGap[]
  duplicate_artists: ReconDuplicate[]
  affiliation_variants: ReconVariant[]
  identity_inconsistencies: ReconVariant[]
  alias_conflicts: ReconAliasConflict[]
  location_variants: ReconVariant[]
}

// ---------------------------------------------------------------------------
// Admin files (GET /artists/admin-files)
// ---------------------------------------------------------------------------

export interface AdminFile {
  file_id: string
  file_name: string
  file_path: string
  folder_name: string
  category: string
  file_type: string
  candidate_artist_id: string | null
  candidate_display_name: string | null
  match_score: number | null
}

// ---------------------------------------------------------------------------
// Config (GET /config, PUT /config)
// ---------------------------------------------------------------------------

export interface AppConfig {
  artist_storage_root: string
  artist_ground_truth_csv: string
  artist_scan_enabled: boolean
  artist_scan_on_change: boolean
  export_output_dir?: string
  [key: string]: unknown
}

// ---------------------------------------------------------------------------
// Scan status (GET /artists/scan/status)
// ---------------------------------------------------------------------------

export interface ScanLastRun {
  status: string
  finished_at: string | null
  stats: { artists?: number } | null
}

export interface ScanStatus {
  is_scanning: boolean
  last_run: ScanLastRun | null
}

// ---------------------------------------------------------------------------
// Lexicon (GET /artists/lexicon)
// ---------------------------------------------------------------------------

export type Lexicon = Record<string, unknown>

// ---------------------------------------------------------------------------
// Electron API (exposed via preload)
// ---------------------------------------------------------------------------

declare global {
  interface Window {
    electronAPI?: {
      selectFolder: () => Promise<string | null>
    }
  }
}

// ---------------------------------------------------------------------------
// Projects module
// ---------------------------------------------------------------------------

export type ProjectType = 'private_development' | 'civic' | 'community'
export type ProjectStatus = 'draft' | 'provisioning' | 'provisioned' | 'active' | 'completed'

export interface IntakeAnswers {
  municipality: string
  project_type: ProjectType
  project_name: string
  developer_name: string | null
  neighbourhood: string | null
  construction_cost: number
  unit_count: number | null
  floor_area_sqm: number | null
  fsr: number | null
  requires_rezoning: boolean
  community_engagement: boolean
  indigenous_engagement: boolean
  conditions: Record<string, boolean>
}

export interface BudgetCalculation {
  contribution_rate: number
  cost_basis: string
  gross_cost: number
  eligible_cost: number
  art_contribution: number
  maintenance_reserve: number
  maintenance_reserve_rate: number
  total: number
}

export interface PolicyNote {
  topic: string
  text: string
}

export interface ResolvedTask {
  temp_id: string
  name: string
  stage: number
  is_milestone: boolean
  parent_temp_id: string | null
  depends_on: string[]
  condition: string | null
  source: 'base' | 'overlay' | 'added'
  policy_notes: PolicyNote[]
}

export interface StageInfo {
  number: number
  name: string
  task_count: number
}

export interface ResolvedManifest {
  tasks: ResolvedTask[]
  stages: StageInfo[]
  municipality: string
  city_name: string
  budget: BudgetCalculation | null
  conditions_applied: Record<string, boolean>
  total_tasks: number
  base_task_count: number
  added_task_count: number
  removed_task_count: number
}

export interface CitySummary {
  city_id: string
  city_name: string
  policy_version: string
  contribution_rate: number
  task_override_count: number
  has_overlay: boolean
}

export interface ProjectRecord {
  id: string
  project_name: string
  developer_name: string | null
  municipality: string
  city_name: string
  project_type: ProjectType
  intake: IntakeAnswers
  budget: BudgetCalculation | null
  resolved_task_count: number
  clickup_list_id: string | null
  clickup_folder_id: string | null
  clickup_workspace_id: string | null
  status: ProjectStatus
  created_at: string
  updated_at: string
  provisioned_at: string | null
}

// ---------------------------------------------------------------------------
// Policy Matrix
// ---------------------------------------------------------------------------

export interface PolicyTopic {
  id: string
  label: string
  stage: number
  maps_to: string[]
  order: number
}

export interface PolicyMatrixData {
  version: string
  topics: PolicyTopic[]
  entries: Record<string, Record<string, string>>
  city_names?: Record<string, string>
}

// ---------------------------------------------------------------------------
// Email Templates
// ---------------------------------------------------------------------------

export type RecipientRole = 'developer' | 'city' | 'artist' | 'panel' | 'internal'

export interface EmailTemplateDef {
  key: string
  title: string
  stage: number
  subject: string
  body_html: string
  merge_fields: string[]
  maps_to: string[]
  order: number
  recipient_role: RecipientRole
}

export interface EmailTemplateData {
  version: string
  templates: EmailTemplateDef[]
}
