export interface ModulePage {
  key: string;
  label: string;
  href: string;
  icon: string; // lucide-react icon name
}

export interface ModuleConfig {
  name: string;
  description: string;
  emoji: string;
  pages: ModulePage[];
  settingsHref?: string;
  status: 'active' | 'placeholder';
}

export const MODULES: Record<string, ModuleConfig> = {
  'artist-directory': {
    name: 'Artist Directory',
    description: 'Artist records, health checks, reconciliation',
    emoji: '\uD83D\uDCDA',
    pages: [
      { key: 'directory', label: 'Directory', href: '/artist-directory', icon: 'BookOpen' },
      { key: 'health', label: 'Health', href: '/artist-directory/health', icon: 'HeartPulse' },
      { key: 'recon', label: 'Reconciliation', href: '/artist-directory/recon', icon: 'GitCompare' },
    ],
    settingsHref: '/artist-directory/settings',
    status: 'active',
  },
  'image-sorting': {
    name: 'Image Sorting',
    description: 'Review and sort image submissions by manifest',
    emoji: '\uD83D\uDDBC\uFE0F',
    pages: [
      { key: 'review', label: 'Review', href: '/image-sorting', icon: 'Image' },
    ],
    settingsHref: '/image-sorting/settings',
    status: 'active',
  },
  'art-collector': {
    name: 'Art Collector',
    description: 'Collect artist images, bios, and metadata from the web',
    emoji: '\uD83D\uDD0D',
    pages: [
      { key: 'collector', label: 'Collector', href: '/art-collector', icon: 'Search' },
    ],
    status: 'placeholder',
  },
  'contacts': {
    name: 'Contacts',
    description: 'Exchange contact sync and management',
    emoji: '\uD83D\uDCC7',
    pages: [
      { key: 'contacts', label: 'Contacts', href: '/contacts', icon: 'Users' },
    ],
    settingsHref: '/contacts/settings',
    status: 'active',
  },
  'mail': {
    name: 'Mail',
    description: 'Email polling and inbox monitoring',
    emoji: '\uD83D\uDCEC',
    pages: [
      { key: 'inbox', label: 'Inbox', href: '/mail', icon: 'Mail' },
    ],
    settingsHref: '/mail/settings',
    status: 'active',
  },
  'projects': {
    name: 'Projects',
    description: 'Project templates, intake, and ClickUp provisioning',
    emoji: '\uD83D\uDCC1',
    pages: [
      { key: 'list', label: 'Projects', href: '/projects', icon: 'FolderOpen' },
      { key: 'new', label: 'New Project', href: '/projects/new', icon: 'PlusCircle' },
    ],
    status: 'active',
  },
  'bfa-todo': {
    name: 'BFA To Do List',
    description: 'Weekly project pipeline — Excel import, render, deploy to Google Docs',
    emoji: '\uD83D\uDCCB',
    pages: [
      { key: 'overview', label: 'Overview', href: '/bfa-todo', icon: 'ListChecks' },
    ],
    status: 'active',
  },
  'systems': {
    name: 'Systems',
    description: 'Policy matrix, data tools, and system configuration',
    emoji: '\u2699\uFE0F',
    pages: [
      { key: 'policy-matrix', label: 'Policy Matrix', href: '/systems/policy-matrix', icon: 'Grid3X3' },
      { key: 'email-templates', label: 'Email Templates', href: '/systems/email-templates', icon: 'Mail' },
    ],
    status: 'active',
  },
  'legal-letters': {
    name: 'Legal Letters',
    description: 'Generate close-out legal documents for provisioned projects',
    emoji: '\uD83D\uDCDD',
    pages: [
      { key: 'overview', label: 'Legal Letters', href: '/legal-letters', icon: 'FileText' },
    ],
    status: 'active',
  },
  'analytics': {
    name: 'Analytics',
    description: 'Usage metrics, service health, and system overview',
    emoji: '\uD83D\uDCCA',
    pages: [
      { key: 'overview', label: 'Overview', href: '/analytics', icon: 'BarChart3' },
    ],
    status: 'placeholder',
  },
};
