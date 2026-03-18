import type { ReactNode } from 'react';
import { ModuleSidebar } from './ModuleSidebar';
import { MODULES } from './moduleRegistry';

interface ModuleLayoutProps {
  module: string;
  activePage: string;
  children: ReactNode;
  /** Skip .module-content padding/overflow for full-bleed layouts (e.g. Dockview) */
  flush?: boolean;
}

export function ModuleLayout({ module, activePage, children, flush }: ModuleLayoutProps) {
  const config = MODULES[module];
  if (!config) return <>{children}</>;

  return (
    <div className="module-layout">
      <ModuleSidebar
        moduleName={config.name}
        pages={config.pages}
        settingsHref={config.settingsHref}
        activePage={activePage}
      />
      {flush ? (
        <main style={{ flex: 1, minWidth: 0, height: '100%', overflow: 'hidden' }}>
          {children}
        </main>
      ) : (
        <main className="module-content">
          {children}
        </main>
      )}
    </div>
  );
}
