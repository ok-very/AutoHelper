import { Search, Settings, FileText } from 'lucide-react';
import type { Manifest, FilterDef } from '../types/manifest';
import type { ReviewStoreApi } from '../stores/reviewStore';
import { useStore } from 'zustand';

interface FilterBarProps {
    manifest: Manifest;
    store: ReviewStoreApi;
}

export function FilterBar({ manifest, store }: FilterBarProps) {
    const filters = useStore(store, (s) => s.filters);
    const searchText = useStore(store, (s) => s.searchText);
    const setFilter = useStore(store, (s) => s.setFilter);
    const setSearchText = useStore(store, (s) => s.setSearchText);
    const reviewStates = useStore(store, (s) => s.reviewStates);

    function getOptions(filterDef: FilterDef): { value: string; label: string }[] {
        if (filterDef.type === 'assignment') {
            const group = manifest.assignmentGroups[filterDef.field];
            if (!group) return [];
            return [
                { value: '__unassigned__', label: 'Unassigned' },
                ...group.options.map((o) => ({
                    value: o.value,
                    label: o.emoji ? `${o.emoji} ${o.label}` : o.label,
                })),
            ];
        }
        if (filterDef.type === 'enum') {
            return (filterDef.options ?? []).map((v) => ({ value: v, label: v.toUpperCase() }));
        }
        if (filterDef.type === 'boolean') {
            return [
                { value: 'true', label: 'Yes' },
                { value: 'false', label: 'No' },
            ];
        }
        return [];
    }

    async function openReport() {
        try {
            const resp = await fetch(`/api/documents/submission-report`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    manifest: manifest.id,
                    review_states: reviewStates,
                }),
            });
            if (!resp.ok) {
                const text = await resp.text().catch(() => resp.statusText);
                console.error(`Report failed (${resp.status}):`, text);
                alert(`Report generation failed (${resp.status}). Check server logs.`);
                return;
            }
            const html = await resp.text();
            const win = window.open('', '_blank');
            if (win) {
                win.document.write(html);
                win.document.close();
            }
        } catch (err) {
            console.error('Report error:', err);
            alert('Report generation failed. Is the server running?');
        }
    }

    return (
        <div className="flex items-center gap-2 shrink-0 px-3 py-2 border-b border-ws-panel-border bg-ws-panel-bg">
            {/* Search */}
            <div className="flex items-center gap-1.5 border border-ws-panel-border rounded-lg px-2 py-1 bg-white min-w-[180px]">
                <Search size={14} className="text-ws-muted shrink-0" />
                <input
                    type="text"
                    value={searchText}
                    onChange={(e) => setSearchText(e.target.value)}
                    placeholder="Search..."
                    className="text-xs bg-transparent outline-none w-full text-ws-fg placeholder:text-ws-muted"
                />
            </div>

            {/* Filter dropdowns */}
            {manifest.filters?.map((filterDef: FilterDef) => {
                const options = getOptions(filterDef);
                const currentValue = filters[filterDef.field] ?? '';

                return (
                    <div key={filterDef.field} className="flex items-center gap-1">
                        <span className="text-[11px] font-medium text-ws-muted">{filterDef.label}:</span>
                        <select
                            value={currentValue}
                            onChange={(e) => setFilter(filterDef.field, e.target.value || null)}
                            className="text-xs border border-ws-panel-border rounded px-1.5 py-0.5 bg-white text-ws-fg outline-none"
                        >
                            <option value="">All</option>
                            {options.map((opt) => (
                                <option key={opt.value} value={opt.value}>{opt.label}</option>
                            ))}
                        </select>
                    </div>
                );
            })}

            {/* Spacer pushes actions to far right */}
            <div className="flex-1" />

            {/* Right-side actions */}
            <div className="flex items-center gap-2 shrink-0">
                <button
                    onClick={openReport}
                    className="flex items-center gap-1 text-xs text-ws-muted hover:text-ws-fg transition-colors"
                    title="Open HTML report"
                >
                    <FileText size={14} />
                    <span>Report</span>
                </button>
                <a
                    href="/submissions-settings"
                    className="text-ws-muted hover:text-ws-fg transition-colors"
                    title="Submissions settings"
                >
                    <Settings size={16} />
                </a>
            </div>
        </div>
    );
}
