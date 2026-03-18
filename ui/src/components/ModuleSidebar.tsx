import { useState } from 'react';
import type { ModulePage } from './moduleRegistry';
import { SIDEBAR_ICONS, Home, Settings, PanelLeftClose, PanelLeftOpen } from './sidebarIcons';

const STORAGE_KEY = 'sidebar-collapsed';

interface ModuleSidebarProps {
  moduleName: string;
  pages: ModulePage[];
  settingsHref?: string;
  activePage: string;
}

export function ModuleSidebar({ moduleName, pages, settingsHref, activePage }: ModuleSidebarProps) {
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(STORAGE_KEY) === 'true');

  const toggle = () => {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem(STORAGE_KEY, String(next));
  };

  return (
    <aside className={`module-sidebar${collapsed ? ' collapsed' : ''}`}>
      <button className="sidebar-collapse-btn" onClick={toggle} title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
        {collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
      </button>

      <a href="/" className="sidebar-back" title="Home">
        <Home size={16} />
        <span className="sidebar-back-label">Home</span>
      </a>

      <div className="sidebar-title">{moduleName}</div>

      <nav className="sidebar-nav">
        {pages.map((p) => {
          const Icon = SIDEBAR_ICONS[p.icon];
          return (
            <a
              key={p.key}
              href={p.href}
              className={`sidebar-link${p.key === activePage ? ' active' : ''}`}
              title={collapsed ? p.label : undefined}
            >
              {Icon && <span className="sidebar-link-icon"><Icon size={16} /></span>}
              <span className="sidebar-link-label">{p.label}</span>
            </a>
          );
        })}
      </nav>

      {settingsHref && (
        <div className="sidebar-footer">
          <a
            href={settingsHref}
            className={`sidebar-link sidebar-settings${activePage === 'settings' ? ' active' : ''}`}
            title={collapsed ? 'Settings' : undefined}
          >
            <span className="sidebar-link-icon"><Settings size={16} /></span>
            <span className="sidebar-link-label">Settings</span>
          </a>
        </div>
      )}
    </aside>
  );
}
