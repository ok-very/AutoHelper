import { useEngine } from '../EngineContext';
import { useStore } from 'zustand';
import { useImageMetrics } from '../hooks/useImageMetrics';
import { AssignmentGroup, ImageMetricsDisplay, ConfirmActions } from '../components';
import { Label } from '@ui/atoms';
import { createEmptyReviewState } from '../types/record';

export function DetailPanel() {
    const { manifest, store, records } = useEngine();
    const selectedId = useStore(store, (s) => s.selectedId);
    const selectedIds = useStore(store, (s) => s.selectedIds);
    const reviewStates = useStore(store, (s) => s.reviewStates);
    const toggleAssignment = useStore(store, (s) => s.toggleAssignment);
    const clearAssignment = useStore(store, (s) => s.clearAssignment);
    const setRank = useStore(store, (s) => s.setRank);
    const setNotes = useStore(store, (s) => s.setNotes);
    const toggleDpi = useStore(store, (s) => s.toggleDpi);
    const confirm = useStore(store, (s) => s.confirm);
    const unconfirm = useStore(store, (s) => s.unconfirm);

    const isMultiSelect = selectedIds.length > 1;
    const record = records.find((r) => r.id === selectedId) ?? null;
    const rs = record ? (reviewStates[record.id] ?? createEmptyReviewState()) : createEmptyReviewState();
    const { fields } = record ?? { fields: {} as Record<string, unknown> };

    // Read image dimension fields from manifest pipeline config (not hardcoded)
    const pipeline = manifest.imagePipeline;
    const widthPx = pipeline && record ? (fields[pipeline.widthField] as number | undefined) : undefined;
    const heightPx = pipeline && record ? (fields[pipeline.heightField] as number | undefined) : undefined;
    const fileBytes = pipeline?.fileSizeField && record ? (fields[pipeline.fileSizeField] as number | undefined) : undefined;
    // Hook must be called unconditionally (before any early returns)
    const metricsResult = useImageMetrics(pipeline, widthPx, heightPx);

    // Multi-select placeholder
    if (isMultiSelect) {
        return (
            <div className="h-full flex items-center justify-center text-ws-muted text-sm">
                {selectedIds.length} items selected
            </div>
        );
    }

    if (!record) {
        return (
            <div className="h-full flex items-center justify-center text-ws-muted text-sm">
                Select a submission
            </div>
        );
    }

    // Lock editing when confirmed
    const locked = rs.confirmed === true;

    // Group detail fields by section
    const detailFields = Object.entries(manifest.fields).filter(([, def]) => def.detail);
    const sections = new Map<string, [string, typeof manifest.fields[string]][]>();
    for (const [fieldId, def] of detailFields) {
        const section = def.section ?? 'general';
        if (!sections.has(section)) sections.set(section, []);
        sections.get(section)!.push([fieldId, def]);
    }

    return (
        <div className="h-full overflow-y-auto">
            <div className="px-4 py-3 flex flex-col gap-4">
                {/* Info section */}
                {sections.has('info') && (
                    <Section title="Submission Info">
                        {sections.get('info')!.map(([fieldId, def]) => (
                            <FieldDisplay key={fieldId} def={def} value={fields[fieldId]} />
                        ))}
                    </Section>
                )}

                {/* Image metrics */}
                {pipeline && (
                    <Section title="Image Metrics">
                        <ImageMetricsDisplay
                            widthPx={widthPx}
                            heightPx={heightPx}
                            fileBytes={fileBytes}
                            metrics={metricsResult}
                            selectedDpis={rs.selectedDpis}
                            onToggleDpi={(tierId) => toggleDpi(record.id, tierId)}
                            disabled={locked}
                        />
                        {sections.has('image') && sections.get('image')!.map(([fieldId, def]) => (
                            <FieldDisplay key={fieldId} def={def} value={fields[fieldId]} />
                        ))}
                    </Section>
                )}

                {/* Assignment groups */}
                {Object.entries(manifest.assignmentGroups).map(([groupId, group]) => (
                    <Section key={groupId} title={group.label}>
                        <AssignmentGroup
                            group={group}
                            groupId={groupId}
                            values={rs.assignments[groupId] ?? []}
                            onToggle={(val) => toggleAssignment(record.id, groupId, val)}
                            onClear={() => clearAssignment(record.id, groupId)}
                            disabled={locked}
                        />
                    </Section>
                ))}

                {/* Rat Rating */}
                <Section title="Rat Rating">
                    <div className="flex items-center gap-0.5">
                        {[1, 2, 3, 4].map((n) => (
                            <button
                                key={n}
                                onClick={() => !locked && setRank(record.id, rs.rank === n ? 0 : n)}
                                disabled={locked}
                                className={`text-lg transition-opacity ${locked ? 'cursor-default' : 'cursor-pointer'} ${n <= rs.rank ? 'opacity-100' : 'opacity-25 grayscale'}`}
                                title={`${n} rat${n > 1 ? 's' : ''}`}
                            >
                                🐀
                            </button>
                        ))}
                    </div>
                </Section>

                {/* Notes */}
                <Section title="Notes">
                    <textarea
                        value={rs.notes}
                        onChange={(e) => setNotes(record.id, e.target.value)}
                        disabled={locked}
                        rows={3}
                        className={`w-full px-2 py-1.5 text-xs border border-ws-panel-border rounded bg-white text-ws-fg resize-y ${locked ? 'opacity-60 cursor-default' : ''}`}
                        placeholder="Reviewer notes..."
                    />
                </Section>

                {/* Confirm */}
                <Section title="Actions">
                    <ConfirmActions
                        manifest={manifest}
                        record={record}
                        reviewState={rs}
                        onConfirm={() => confirm(record.id)}
                        onUnconfirm={() => unconfirm(record.id)}
                    />
                </Section>
            </div>
        </div>
    );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <div className="flex flex-col gap-1.5">
            <Label size="sm" className="text-ws-muted uppercase tracking-wide text-[10px]">
                {title}
            </Label>
            {children}
        </div>
    );
}

interface FieldDisplayProps {
    def: { label: string; type: string; readonly?: boolean; editable?: boolean };
    value: unknown;
}

function FieldDisplay({ def, value }: FieldDisplayProps) {
    if (value === null || value === undefined) return null;

    if (def.type === 'text') {
        return (
            <div className="flex flex-col gap-0.5">
                <span className="text-[11px] font-medium text-ws-text-secondary">{def.label}</span>
                <p className="text-xs text-ws-fg whitespace-pre-wrap bg-ws-bg rounded p-1.5 max-h-24 overflow-y-auto">
                    {String(value)}
                </p>
            </div>
        );
    }

    return (
        <div className="flex items-baseline gap-2">
            <span className="text-[11px] font-medium text-ws-text-secondary shrink-0">{def.label}:</span>
            <span className="text-xs text-ws-fg">{String(value)}</span>
        </div>
    );
}
