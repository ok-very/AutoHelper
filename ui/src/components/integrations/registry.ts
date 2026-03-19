export type AuthMethod = 'oauth' | 'token' | 'credentials' | 'pairing'
export type SourceType = 'env' | 'config' | 'oauth' | 'pairing' | 'none'

export interface ProviderCapability {
  key: string
  label: string
}

export interface ProviderDef {
  id: string
  name: string
  authMethod: AuthMethod
  capabilities: ProviderCapability[]
  iconColor: string
}

export const PROVIDERS: Record<string, ProviderDef> = {
  google: {
    id: 'google',
    name: 'Google Workspace',
    authMethod: 'oauth',
    capabilities: [
      { key: 'docs', label: 'Docs' },
      { key: 'sheets', label: 'Sheets' },
    ],
    iconColor: 'icon-blue',
  },
  clickup: {
    id: 'clickup',
    name: 'ClickUp',
    authMethod: 'oauth',
    capabilities: [
      { key: 'tasks', label: 'Tasks' },
      { key: 'templates', label: 'Templates' },
      { key: 'artists', label: 'Artists' },
      { key: 'email', label: 'Email' },
    ],
    iconColor: 'icon-purple',
  },
  monday: {
    id: 'monday',
    name: 'Monday.com',
    authMethod: 'oauth',
    capabilities: [
      { key: 'boards', label: 'Boards' },
      { key: 'context', label: 'Context' },
    ],
    iconColor: 'icon-amber',
  },
  exchange: {
    id: 'exchange',
    name: 'Exchange',
    authMethod: 'credentials',
    capabilities: [
      { key: 'contacts', label: 'Contacts' },
      { key: 'mail', label: 'Mail' },
    ],
    iconColor: 'icon-blue',
  },
  autoart: {
    id: 'autoart',
    name: 'AutoArt',
    authMethod: 'pairing',
    capabilities: [
      { key: 'sync', label: 'Sync' },
      { key: 'commands', label: 'Commands' },
    ],
    iconColor: 'icon-blue',
  },
}
