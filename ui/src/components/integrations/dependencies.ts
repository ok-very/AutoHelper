export interface ModuleDep {
  provider: string
  purpose: string
}

export const MODULE_DEPS: Record<string, ModuleDep[]> = {
  'bfa-todo': [
    { provider: 'google', purpose: 'Deploy to Google Docs' },
    { provider: 'clickup', purpose: 'Resolve team member names' },
  ],
  'projects': [
    { provider: 'clickup', purpose: 'Provision tasks and templates' },
  ],
  'contacts': [
    { provider: 'exchange', purpose: 'Contact sync' },
  ],
}
