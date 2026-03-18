export type SourceType = 'bfa-html' | 'monday-excel' | 'clickup'
export type TargetType = 'none' | 'google-docs' | 'clickup'

export interface BfaTodoStatus {
  project_count: number
  last_render: string | null
  has_html: boolean
  has_json: boolean
  has_gdocs: boolean
}

export interface ValidationItem {
  field: string
  level: 'error' | 'warning'
  code: string
  message: string
  suggestion: string | null
}

export interface Validation {
  error_count: number
  warning_count: number
  items: ValidationItem[]
}

export interface BfaTodoProject {
  uid: string
  slug: string
  client: string
  project_name: string
  city: string
  phase: string
  owner_team: string
  status: 'active' | 'on_hold'
  validation: Validation
}

export interface BfaTodoPreamble {
  uid: string
  slug: string
  type: 'preamble' | 'preamble-lists'
  title: string
}
