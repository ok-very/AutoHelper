import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Badge } from '@ui/atoms';
import type { Manifest, BadgeDef } from '../types/manifest';
import type { ReviewState } from '../types/record';
import { useEngine } from '../EngineContext';
import { useStore } from 'zustand';
import { createEmptyReviewState } from '../types/record';
import { useFilteredRecords } from '../hooks/useFilteredRecords';
import { useMemo } from 'react';

export function PreviewPanel() {
    const { manifest, store, records } = useEngine();
    const selectedId = useStore(store, (s) => s.selectedId);
    const selectedIds = useStore(store, (s) => s.selectedIds);
    const reviewStates = useStore(store, (s) => s.reviewStates);
    const selectRelative = useStore(store, (s) => s.selectRelative);
    const filters = useStore(store, (s) => s.filters);
    const searchText = useStore(store, (s) => s.searchText);

    const filteredRecords = useFilteredRecords(records, manifest, reviewStates, filters, searchText);
    const orderedIds = useMemo(() => filteredRecords.map((r) => r.id), [filteredRecords]);

    const isMultiSelect = selectedIds.length > 1;

    // Multi-select: hide preview
    if (isMultiSelect) {
        return (
            <div className="h-full flex items-center justify-center text-ws-muted text-sm">
                {selectedIds.length} items selected
            </div>
        );
    }

    const record = records.find((r) => r.id === selectedId) ?? null;

    if (!record) {
        return (
            <div className="h-full flex items-center justify-center text-ws-muted text-sm">
                Select a submission to preview
            </div>
        );
    }

    const preview = manifest.preview;
    if (!preview) {
        return (
            <div className="h-full flex items-center justify-center text-ws-muted text-sm">
                No preview configuration
            </div>
        );
    }

    const { fields } = record;
    const rs = reviewStates[record.id] ?? createEmptyReviewState();

    const imagePath = fields[preview.imageField] as string | null;
    const primaryLabel = String(fields[preview.primaryLabel] ?? '');
    const secondaryLabel = preview.secondaryLabel
        ? String(fields[preview.secondaryLabel] ?? '')
        : '';

    // Determine image availability
    const isMissing = preview.availabilityField && preview.missingValue
        ? fields[preview.availabilityField] === preview.missingValue
        : false;
    const hasImage = imagePath && !isMissing;

    // Navigation state
    const currentIdx = orderedIds.indexOf(record.id);
    const hasPrev = currentIdx > 0;
    const hasNext = currentIdx >= 0 && currentIdx < orderedIds.length - 1;

    return (
        <div className="h-full flex flex-col">
            {/* Image area */}
            <div className="flex-1 flex items-center justify-center bg-slate-50 min-h-0 overflow-hidden p-4 relative">
                {/* Back arrow */}
                <button
                    onClick={() => selectRelative(-1, orderedIds)}
                    disabled={!hasPrev}
                    className="absolute left-2 top-1/2 -translate-y-1/2 z-10 w-8 h-8 flex items-center justify-center rounded-full bg-white/80 border border-slate-200 shadow-sm text-slate-500 hover:bg-white hover:text-slate-700 disabled:opacity-30 disabled:cursor-default transition-all cursor-pointer"
                    title="Previous (← or ,)"
                >
                    <ChevronLeft size={18} />
                </button>

                {hasImage ? (
                    <div className="relative max-h-full max-w-full flex items-center justify-center">
                        <img
                            src={`/api/image?path=${encodeURIComponent(imagePath!)}`}
                            alt={`${primaryLabel}${secondaryLabel ? ` - ${secondaryLabel}` : ''}`}
                            className="max-h-full max-w-full object-contain rounded shadow-sm"
                            onError={(e) => {
                                (e.target as HTMLImageElement).style.display = 'none';
                                (e.target as HTMLImageElement).nextElementSibling?.classList.remove('hidden');
                            }}
                        />
                        <div className="hidden text-center p-4">
                            <p className="text-xs text-ws-muted mb-1">Image not accessible in browser:</p>
                            <p className="text-[10px] text-ws-text-secondary font-mono break-all">{imagePath}</p>
                        </div>
                    </div>
                ) : (
                    <div className="text-center text-ws-muted">
                        <p className="text-sm font-medium">No image</p>
                        <p className="text-xs">{isMissing ? 'Image not found' : 'No path available'}</p>
                    </div>
                )}

                {/* Forward arrow */}
                <button
                    onClick={() => selectRelative(1, orderedIds)}
                    disabled={!hasNext}
                    className="absolute right-2 top-1/2 -translate-y-1/2 z-10 w-8 h-8 flex items-center justify-center rounded-full bg-white/80 border border-slate-200 shadow-sm text-slate-500 hover:bg-white hover:text-slate-700 disabled:opacity-30 disabled:cursor-default transition-all cursor-pointer"
                    title="Next (→ or .)"
                >
                    <ChevronRight size={18} />
                </button>
            </div>

            {/* Info bar */}
            <div className="px-4 py-3 border-t border-ws-panel-border bg-ws-panel-bg">
                <div className="flex items-center justify-between">
                    <div>
                        <p className="text-sm font-medium text-ws-fg">{primaryLabel}</p>
                        {secondaryLabel && (
                            <p className="text-xs text-ws-text-secondary">{secondaryLabel}</p>
                        )}
                    </div>
                    {orderedIds.length > 0 && (
                        <span className="text-[10px] text-ws-muted tabular-nums">
                            {currentIdx + 1} / {orderedIds.length}
                        </span>
                    )}
                </div>
                {preview.badges && preview.badges.length > 0 && (
                    <div className="flex items-center gap-2 mt-1.5">
                        {preview.badges.map((badgeDef, i) => (
                            <PreviewBadge
                                key={i}
                                badgeDef={badgeDef}
                                manifest={manifest}
                                fields={fields}
                                reviewState={rs}
                            />
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

function PreviewBadge({
    badgeDef,
    manifest,
    fields,
    reviewState,
}: {
    badgeDef: BadgeDef;
    manifest: Manifest;
    fields: Record<string, unknown>;
    reviewState: ReviewState;
}) {
    // Resolve the value(s): check assignment groups first, then raw fields
    let rawValues: string[] = [];

    if (badgeDef.fromGroup) {
        rawValues = reviewState.assignments[badgeDef.fromGroup] ?? [];
    } else {
        const fieldDef = manifest.fields[badgeDef.field];
        if (fieldDef?.type === 'assignment' && fieldDef.group) {
            rawValues = reviewState.assignments[fieldDef.group] ?? [];
        } else {
            const v = fields[badgeDef.field];
            rawValues = v != null ? [String(v)] : [];
        }
    }

    if (rawValues.length === 0) return null;

    // Build display text from all values
    const labels = rawValues.map((rawValue) => {
        let displayText = rawValue;
        if (badgeDef.fromGroup) {
            const group = manifest.assignmentGroups[badgeDef.fromGroup];
            const opt = group?.options.find((o) => o.value === rawValue);
            if (opt) displayText = opt.emoji ? `${opt.emoji} ${opt.label}` : opt.label;
        }
        if (badgeDef.transform === 'uppercase') displayText = displayText.toUpperCase();
        else if (badgeDef.transform === 'capitalize') displayText = displayText.charAt(0).toUpperCase() + displayText.slice(1);
        return displayText;
    });

    const displayText = labels.join(', ');
    const variant = badgeDef.variantMap?.[rawValues[0]] ?? 'default';

    return (
        <Badge variant={variant as 'success' | 'error' | 'warning' | 'info' | 'default'} size="xs">
            {displayText}
        </Badge>
    );
}
