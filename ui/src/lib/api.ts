import type {
  ArtistListItem,
  ArtistManifest,
  ArtistStats,
  HealthReport,
  ReconciliationData,
  AdminFile,
  AppConfig,
  ScanStatus,
  Lexicon,
  PolicyMatrixData,
} from './types'

const API = '/artists'
const CONFIG_API = '/config'

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init)
  if (!res.ok) throw new Error(`${init?.method ?? 'GET'} ${path}: ${res.status}`)
  return res.json() as Promise<T>
}

function post(path: string, body?: unknown): Promise<Response> {
  return fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body != null ? JSON.stringify(body) : undefined,
  })
}

function put(path: string, body: unknown): Promise<Response> {
  return fetch(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

// -- Integration status types --

export interface IntegrationFieldStatus {
  value: string
  source: 'env' | 'config' | 'none'
}

export interface OAuthProviderStatus {
  oauth_available?: boolean
  configured: boolean
  account?: string
}

export interface IntegrationStatus {
  clickup: {
    configured: boolean
    source: 'env' | 'config' | 'none'
    token_hint?: string | null
    oauth_available?: boolean
    workspace_id: IntegrationFieldStatus
    space_id: IntegrationFieldStatus
    list_id: IntegrationFieldStatus
  }
  google: OAuthProviderStatus
  monday: OAuthProviderStatus
  exchange: {
    configured: boolean
    source: 'env' | 'config' | 'none'
    email: IntegrationFieldStatus
  }
  autoart: {
    paired: boolean
    connections?: Record<string, { connected: boolean }>
  }
}

export const api = {
  artists: {
    list: (limit = 5000) =>
      fetchJson<ArtistListItem[]>(`${API}?limit=${limit}`),

    get: (id: string) =>
      fetchJson<ArtistManifest>(`${API}/${id}`),

    bioContent: (id: string) =>
      fetchJson<{ content: string }>(`${API}/${id}/bio-content`),

    stats: () =>
      fetchJson<ArtistStats>(`${API}/stats`),

    health: () =>
      fetchJson<HealthReport>(`${API}/health`),

    reconciliation: () =>
      fetchJson<ReconciliationData>(`${API}/reconciliation`),

    adminFiles: () =>
      fetchJson<AdminFile[]>(`${API}/admin-files`),

    updateReview: (id: string, status: string) =>
      put(`${API}/${id}/review`, { status }),

    saveManifest: (id: string, data: { identity: Partial<ArtistManifest['identity']>; contact: Partial<ArtistManifest['contact']> }) =>
      put(`${API}/${id}/manifest`, data),

    rescan: (id: string) =>
      post(`${API}/${id}/rescan`),

    resolveNote: (id: string, index: number) =>
      post(`${API}/${id}/resolve-note`, { index }),

    addPanel: (id: string, entry: { date: string; project: string; role: string }) =>
      post(`${API}/${id}/panel`, entry),

    addProject: (id: string, project: { project_name: string; developer?: string | null; year?: string | null; role?: string | null; status?: string }) =>
      post(`${API}/${id}/project`, project),

    openFolder: (id: string) =>
      fetch(`${API}/${id}/open-folder`),

    openFile: (path: string) =>
      fetch(`${API}/open-file?path=${encodeURIComponent(path)}`),

    attributeFile: (fileId: string, artistId: string) =>
      post(`${API}/admin-files/${encodeURIComponent(fileId)}/attribute`, { artist_id: artistId }),

    resolveRecon: (body: Record<string, unknown>) =>
      post(`${API}/reconciliation/resolve`, body),

    merge: (keepId: string, removeId: string) =>
      post(`${API}/reconciliation/merge`, { keep_id: keepId, remove_id: removeId }).then(r => r.json()),

    autoMerge: (threshold: number, dryRun: boolean) =>
      post(`${API}/reconciliation/auto-merge`, { threshold, dry_run: dryRun }).then(r => r.json()),
  },

  scan: {
    trigger: () => post(`${API}/scan`),
    stop: () => post(`${API}/scan/stop`),
    status: () => fetchJson<ScanStatus>(`${API}/scan/status`),
    logUrl: `${API}/scan/log`,
  },

  lexicon: {
    get: () => fetchJson<Lexicon>(`${API}/lexicon`),
    save: (data: Lexicon) => put(`${API}/lexicon`, data),
  },

  config: {
    get: () => fetchJson<AppConfig>(CONFIG_API),
    save: (data: Partial<AppConfig>) => put(CONFIG_API, data),
    selectFolder: () => post(`${CONFIG_API}/select-folder`).then(r => r.json() as Promise<{ path: string | null }>),
  },

  clickup: {
    validate: () => fetchJson<{ ok: boolean; workspace?: string; workspace_id?: string; error?: string }>('/clickup/validate'),
    auth: () => fetchJson<{ url: string; state: string }>('/clickup/auth'),
    members: () => fetchJson<{ id: number; username: string; initials: string; email: string }[]>('/clickup/members'),
    artistSync: (listId: string, dryRun: boolean, artistIds?: string[]) =>
      post(`/clickup/artist-sync?list_id=${encodeURIComponent(listId)}&dry_run=${dryRun}`, { artist_ids: artistIds ?? null }).then(r => r.json()),
  },

  google: {
    auth: () => fetchJson<{ url: string; state: string }>('/api/google/auth'),
  },

  monday: {
    auth: () => fetchJson<{ url: string; state: string }>('/api/monday/auth'),
  },

  integrations: {
    status: () => fetchJson<IntegrationStatus>('/integrations/status'),
  },

  contacts: {
    status: () => fetchJson<Record<string, unknown>>('/contacts/status'),
    history: () => fetchJson<Record<string, unknown>[]>('/contacts/history'),
    testExchange: () => post('/contacts/exchange/test').then(r => r.json()),
    sync: () => post('/contacts/sync').then(r => r.json()),
  },

  projects: {
    cities: () => fetchJson<any[]>('/api/projects/cities'),
    city: (cityId: string) => fetchJson<any>(`/api/projects/cities/${cityId}`),
    preview: (intake: any) =>
      fetch('/api/projects/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(intake),
      }).then(r => r.json()),
    list: () => fetchJson<any[]>('/api/projects'),
    create: (intake: any) =>
      fetch('/api/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(intake),
      }).then(r => r.json()),
    get: (id: string) => fetchJson<any>(`/api/projects/${id}`),
    provision: (id: string) => post(`/api/projects/${id}/provision`).then(r => r.json()),
    status: (id: string) => fetchJson<any>(`/api/projects/${id}/status`),
    delete: (id: string) =>
      fetch(`/api/projects/${id}`, { method: 'DELETE' }).then(r => r.json()),
    policyMatrix: {
      get: () => fetchJson<PolicyMatrixData>('/api/projects/policy-matrix'),
      save: (data: PolicyMatrixData) => put('/api/projects/policy-matrix', data),
      updateTopics: (topics: PolicyMatrixData['topics']) =>
        put('/api/projects/policy-matrix/topics', { topics }),
      updateEntry: (cityId: string, topicId: string, text: string) =>
        put('/api/projects/policy-matrix/entry', { city_id: cityId, topic_id: topicId, text }),
      importXlsx: (path: string) =>
        post('/api/projects/policy-matrix/import', { path }).then(r => r.json()),
    },
  },

  bfaTodo: {
    status: () => fetchJson<any>('/api/bfa-todo/status'),
    projects: () => fetchJson<any[]>('/api/bfa-todo/projects'),
    project: (uid: string) => fetchJson<any>(`/api/bfa-todo/projects/${uid}`),
    render: () => post('/api/bfa-todo/render').then(r => r.json()),
    importExcel: (filepath: string) =>
      post('/api/bfa-todo/import-excel', { filepath }).then(r => r.json()),
    importHtml: (path: string) =>
      post('/api/bfa-todo/import-html', { path }).then(r => r.json()),
    deploy: (docId: string) =>
      post('/api/bfa-todo/deploy', { doc_id: docId }).then(r => r.json()),
    updateProject: (uid: string, changes: Record<string, any>) =>
      put(`/api/bfa-todo/projects/${uid}`, changes).then(r => r.json()),
    deploySelected: (docId: string, uids: string[]) =>
      post('/api/bfa-todo/deploy-selected', { doc_id: docId, uids }).then(r => r.json()),
    updateSection: (uid: string, sectionName: string, html: string) =>
      put(`/api/bfa-todo/projects/${uid}/sections/${sectionName}`, { html }).then(r => r.json()),
    updatePhase: (uid: string, phase: string) =>
      put(`/api/bfa-todo/projects/${uid}/phase`, { phase }).then(r => r.json()),
    preambles: () => fetchJson<any[]>('/api/bfa-todo/preambles'),
    preambleHtml: (uid: string) =>
      fetch(`/api/bfa-todo/preambles/${uid}/html`).then(r => {
        if (!r.ok) throw new Error(`${r.status}`)
        return r.text()
      }),
    updatePreambleSection: (uid: string, sectionName: string, html: string) =>
      put(`/api/bfa-todo/preambles/${uid}/sections/${sectionName}`, { html }).then(r => r.json()),
  },

  health: () => fetchJson<Record<string, unknown>>('/health'),
  status: () => fetchJson<Record<string, unknown>>('/status'),
}
