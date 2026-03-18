import { MODULES } from '@/components/moduleRegistry';
import { Settings } from 'lucide-react';

export function HomePage() {
  const modules = Object.entries(MODULES);

  return (
    <div className="home-page">
      <div className="home-header">
        <h1>AutoHelper</h1>
        <p>Select a module to get started.</p>
        <a href="/system-settings" className="home-global-settings">
          <Settings size={16} /> System Settings
        </a>
      </div>

      <div className="home-grid">
        {modules.map(([key, mod]) => {
          const isActive = mod.status === 'active';
          const href = mod.pages[0]?.href ?? '#';

          return isActive ? (
            <div
              key={key}
              className="module-card"
              onClick={() => { window.location.href = href; }}
            >
              {mod.settingsHref && (
                <a
                  href={mod.settingsHref}
                  className="module-card-gear"
                  title={`${mod.name} Settings`}
                  onClick={(e) => e.stopPropagation()}
                >
                  <Settings size={16} />
                </a>
              )}
              <div className="module-card-header">
                <span className="module-card-icon">{mod.emoji}</span>
                <span className="module-card-name">{mod.name}</span>
              </div>
              <div className="module-card-desc">{mod.description}</div>
              <div className="module-card-footer">
                <span className="module-status active">Active</span>
              </div>
            </div>
          ) : (
            <div key={key} className="module-card placeholder">
              <div className="module-card-header">
                <span className="module-card-icon">{mod.emoji}</span>
                <span className="module-card-name">{mod.name}</span>
              </div>
              <div className="module-card-desc">{mod.description}</div>
              <div className="module-card-footer">
                <span className="module-status placeholder">Coming Soon</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
