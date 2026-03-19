// Mail module types — adapted from autoart/apps/mail/src/lib

export interface MailEmail {
  id: string
  subject: string | null
  sender: string | null
  received_at: string | null
  project_id: string | null
  body_preview: string | null
  body_html: string | null
  metadata: Record<string, unknown> | null
  triage_status: string | null
  triage_notes: string | null
  triaged_at: string | null
  account: string

  // Computed client-side from metadata if available
  fromName?: string
  projectName?: string
  priority?: number
  hasAttachments?: boolean
  attachments?: Attachment[]
  stakeholderType?: string
  triage?: TriageData
}

export interface TriageData {
  bucket: string
  confidence: number
  reasoning: string[]
  preReplyActions: { description: string; type: string }[]
  postReplyActions: { description: string; type: string }[]
  suggestedReplyOpener?: string
}

export interface Attachment {
  id: string
  name: string
  filename: string
  contentType: string
  localPath?: string
  size: number
  url: string
}

export type TriageBucket = string
export type ViewMode = 'triage' | 'requests'
export type RequestTab = 'pending' | 'received' | 'sent'

export interface MailEmailList {
  emails: MailEmail[]
  total: number
  limit: number
  offset: number
}

/** Hydrate a TransientEmail from the API into a MailEmail with computed fields */
export function hydrateEmail(raw: any): MailEmail {
  const meta = raw.metadata ?? {}
  return {
    ...raw,
    fromName: meta.sender_name ?? raw.sender?.split('@')[0] ?? 'Unknown',
    projectName: meta.project_name ?? raw.project_id ?? '',
    priority: meta.priority ?? 2,
    hasAttachments: Boolean(meta.attachment_count || meta.attachments?.length),
    attachments: meta.attachments ?? [],
    stakeholderType: meta.stakeholder_type ?? '',
    triage: meta.triage ?? null,
  }
}
