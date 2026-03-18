import { useMemo, useCallback, useRef, useState, useEffect } from 'react';
import { clsx } from 'clsx';

import {
    UniversalTableCore,
    makeFlatRowModel,
    type TableColumn,
    type TableRow,
} from '@ui/table-core';
import type { Manifest, FieldDef } from '../types/manifest';
import type { SubmissionRecord, ReviewState } from '../types/record';
import { useEngine } from '../EngineContext';
import { useStore } from 'zustand';
import { useFilteredRecords } from '../hooks/useFilteredRecords';

// ============================================================================
// COLUMN BUILDER
// ============================================================================

/** Sensible default widths when manifest doesn't specify */
function defaultWidth(fieldDef: FieldDef): number | 'flex' {
    switch (fieldDef.type) {
        case 'number': return 50;
        case 'boolean': return 50;
        case 'enum': return 80;
        case 'badge': return 60;
        case 'assignment': return 120;
        case 'string': return 160;
        default: return 'flex';
    }
}

// ============================================================================
// INLINE ASSIGNMENT DROPDOWN (multi-select popover for table cells)
// ============================================================================

function AssignmentDropdown({
    options,
    selected,
    onToggle,
    disabled,
}: {
    options: { value: string; label: string; emoji?: string }[];
    selected: string[];
    onToggle: (value: string) => void;
    disabled: boolean;
}) {
    const [open, setOpen] = useState(false);
    const ref = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!open) return;
        const onClickOutside = (e: MouseEvent) => {
            if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
        };
        document.addEventListener('mousedown', onClickOutside);
        return () => document.removeEventListener('mousedown', onClickOutside);
    }, [open]);

    const summary = selected.length === 0
        ? '\u2014'
        : selected.map((v) => {
            const opt = options.find((o) => o.value === v);
            return opt?.emoji ?? opt?.label ?? v;
        }).join(' ');

    return (
        <div ref={ref} className="relative" onClick={(e) => e.stopPropagation()}>
            <button
                onClick={() => !disabled && setOpen(!open)}
                disabled={disabled}
                className={clsx(
                    'text-[11px] leading-tight px-1 py-0.5 rounded border w-full text-left truncate',
                    disabled ? 'cursor-default' : 'cursor-pointer hover:border-blue-300',
                    selected.length > 0
                        ? 'border-blue-200 bg-blue-50/50 text-ws-fg'
                        : 'border-transparent text-ws-muted',
                )}
            >
                {summary}
            </button>
            {open && (
                <div className="absolute z-50 top-full left-0 mt-0.5 bg-white border border-ws-panel-border rounded shadow-lg py-0.5 min-w-[120px]">
                    {options.map((opt) => {
                        const active = selected.includes(opt.value);
                        return (
                            <button
                                key={opt.value}
                                onClick={() => onToggle(opt.value)}
                                className={clsx(
                                    'flex items-center gap-1.5 w-full px-2 py-1 text-[11px] text-left hover:bg-blue-50 transition-colors',
                                    active ? 'text-blue-800 font-medium' : 'text-ws-fg',
                                )}
                            >
                                <span className={clsx(
                                    'w-3 h-3 rounded-sm border flex items-center justify-center text-[9px] shrink-0',
                                    active ? 'bg-blue-500 border-blue-500 text-white' : 'border-gray-300',
                                )}>
                                    {active ? '✓' : ''}
                                </span>
                                {opt.emoji && <span>{opt.emoji}</span>}
                                <span className="truncate">{opt.label}</span>
                            </button>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

interface StoreActions {
    toggleAssignment: (recordId: string, groupId: string, value: string) => void;
    setRank: (recordId: string, rank: number) => void;
}

function buildColumns(
    manifest: Manifest,
    reviewStates: Record<string, ReviewState>,
    actions: StoreActions,
): TableColumn[] {
    const cols: TableColumn[] = [];

    for (const [fieldId, fieldDef] of Object.entries(manifest.fields)) {
        if (!fieldDef.column) continue;

        cols.push({
            id: fieldId,
            header: fieldDef.label,
            width: fieldDef.width ?? defaultWidth(fieldDef),
            minWidth: 40,
            resizable: true,
            align: 'left',

            cell: (row: TableRow) => {
                const record = row.data as SubmissionRecord;
                const rs = reviewStates[record.id];
                const locked = rs?.confirmed ?? false;

                // Interactive rank cell
                if (fieldId === 'rank') {
                    const rank = rs?.rank ?? (typeof record.fields[fieldId] === 'number' ? record.fields[fieldId] as number : 0);
                    return (
                        <div className="flex items-center gap-0" onClick={(e) => e.stopPropagation()}>
                            {[1, 2, 3, 4].map((n) => (
                                <button
                                    key={n}
                                    onClick={() => !locked && actions.setRank(record.id, rank === n ? 0 : n)}
                                    disabled={locked}
                                    className={`text-sm leading-none transition-opacity ${locked ? 'cursor-default' : 'cursor-pointer hover:scale-110'} ${n <= rank ? 'opacity-100' : 'opacity-20 grayscale'}`}
                                >
                                    🐀
                                </button>
                            ))}
                        </div>
                    );
                }

                // Interactive assignment cell (multi-select dropdown)
                if (fieldDef.type === 'assignment' && fieldDef.group) {
                    const arr = rs?.assignments[fieldDef.group] ?? [];
                    const group = manifest.assignmentGroups[fieldDef.group];
                    if (!group) return <span className="text-ws-muted">{'\u2014'}</span>;

                    return (
                        <AssignmentDropdown
                            options={group.options}
                            selected={arr}
                            onToggle={(val) => actions.toggleAssignment(record.id, fieldDef.group!, val)}
                            disabled={locked}
                        />
                    );
                }

                // Default: display-only
                const value = getCellValue(record, fieldId, fieldDef, reviewStates);
                return formatCellDisplay(value, fieldDef, manifest);
            },

            sortKey: (row: TableRow) => {
                const record = row.data as SubmissionRecord;
                const value = getCellValue(record, fieldId, fieldDef, reviewStates);
                if (value == null) return null;
                if (typeof value === 'number') return value;
                if (typeof value === 'string') return value;
                if (Array.isArray(value)) return value.join(',');
                return String(value);
            },
        });
    }

    return cols;
}

// ============================================================================
// CELL VALUE HELPERS (unchanged from original)
// ============================================================================

function getCellValue(
    record: SubmissionRecord,
    fieldId: string,
    fieldDef: FieldDef,
    reviewStates: Record<string, ReviewState>,
): unknown {
    if (fieldDef.type === 'assignment' && fieldDef.group) {
        return reviewStates[record.id]?.assignments[fieldDef.group] ?? [];
    }
    if (fieldId === 'rank') {
        const rank = reviewStates[record.id]?.rank ?? record.fields[fieldId] ?? 0;
        const n = typeof rank === 'number' ? rank : 0;
        return n > 0 ? '\uD83D\uDC00'.repeat(Math.min(n, 4)) : '';
    }
    return record.fields[fieldId];
}

function formatCellDisplay(
    value: unknown,
    fieldDef: FieldDef,
    manifest: Manifest,
): React.ReactNode {
    if (value === null || value === undefined) return (
        <span className="text-ws-muted">{'\u2014'}</span>
    );

    if (fieldDef.type === 'assignment' && fieldDef.group) {
        const arr = Array.isArray(value) ? value : [];
        if (arr.length === 0) return <span className="text-ws-muted">{'\u2014'}</span>;
        const group = manifest.assignmentGroups[fieldDef.group];
        const text = arr.map((v) => {
            const opt = group?.options.find((o) => o.value === v);
            return opt ? (opt.emoji ? `${opt.emoji} ${opt.label}` : opt.label) : String(v);
        }).join(', ');
        return <span className="text-xs truncate">{text}</span>;
    }

    if (fieldDef.type === 'boolean') {
        return <span className="text-xs">{value ? '\u2713' : ''}</span>;
    }

    return <span className="text-xs truncate">{String(value)}</span>;
}

// ============================================================================
// ROW STYLE EVALUATOR (unchanged from original)
// ============================================================================

function evaluateRowRule(
    rule: { field: string; condition: string; value?: unknown; className: string },
    record: SubmissionRecord,
    rs: ReviewState | undefined,
): boolean {
    let fieldValue: unknown;
    const assignmentArr = rs?.assignments[rule.field];
    if (assignmentArr !== undefined) {
        if (rule.condition === 'equals') return assignmentArr.includes(rule.value as string);
        if (rule.condition === 'notEquals') return !assignmentArr.includes(rule.value as string);
        if (rule.condition === 'truthy') return assignmentArr.length > 0;
        if (rule.condition === 'falsy') return assignmentArr.length === 0;
        return false;
    } else if (rule.field === 'confirmed') {
        fieldValue = rs?.confirmed ?? false;
    } else {
        fieldValue = record.fields[rule.field];
    }

    switch (rule.condition) {
        case 'equals': return fieldValue === rule.value;
        case 'notEquals': return fieldValue !== rule.value;
        case 'truthy': return !!fieldValue;
        case 'falsy': return !fieldValue;
        default: return false;
    }
}

// ============================================================================
// LIST PANEL
// ============================================================================

export function ListPanel() {
    const { manifest, store, records } = useEngine();
    const selectedId = useStore(store, (s) => s.selectedId);
    const selectedIds = useStore(store, (s) => s.selectedIds);
    const reviewStates = useStore(store, (s) => s.reviewStates);
    const filters = useStore(store, (s) => s.filters);
    const searchText = useStore(store, (s) => s.searchText);
    const select = useStore(store, (s) => s.select);
    const selectToggle = useStore(store, (s) => s.selectToggle);
    const selectRange = useStore(store, (s) => s.selectRange);
    const selectRangeAdd = useStore(store, (s) => s.selectRangeAdd);

    const toggleAssignment = useStore(store, (s) => s.toggleAssignment);
    const setRank = useStore(store, (s) => s.setRank);

    const filteredRecords = useFilteredRecords(records, manifest, reviewStates, filters, searchText);
    const orderedIds = useMemo(() => filteredRecords.map((r) => r.id), [filteredRecords]);

    // Track last click event for modifier key detection
    const lastClickEvent = useRef<MouseEvent | null>(null);

    const storeActions = useMemo<StoreActions>(
        () => ({ toggleAssignment, setRank }),
        [toggleAssignment, setRank]
    );

    const columns = useMemo(
        () => buildColumns(manifest, reviewStates, storeActions),
        [manifest, reviewStates, storeActions]
    );

    const rowModel = useMemo(
        () => makeFlatRowModel(filteredRecords),
        [filteredRecords]
    );

    const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);
    const rowStyles = manifest.rowStyles ?? [];

    // Capture the native click event for modifier keys BEFORE it reaches the row handler
    // (UniversalTableCore's onRowClick only passes rowId, not the event)
    const handleNativeClick = useCallback((e: React.MouseEvent) => {
        lastClickEvent.current = e.nativeEvent;
    }, []);

    const handleRowClick = useCallback((rowId: string) => {
        const e = lastClickEvent.current;
        if (e?.ctrlKey && e?.shiftKey) {
            selectRangeAdd(rowId, orderedIds);
        } else if (e?.shiftKey) {
            selectRange(rowId, orderedIds);
        } else if (e?.ctrlKey) {
            selectToggle(rowId);
        } else {
            select(rowId);
        }
    }, [orderedIds, select, selectToggle, selectRange, selectRangeAdd]);

    const getRowClassName = useCallback((row: TableRow) => {
        const record = row.data as SubmissionRecord;
        const rs = reviewStates[record.id];
        const isSelected = selectedSet.has(record.id);
        const isConfirmed = rs?.confirmed;

        // Manifest-driven row style rules
        const matchedStyles = rowStyles
            .filter((rule) => evaluateRowRule(rule, record, rs))
            .sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0));
        const dynamicClass = matchedStyles.length > 0 ? matchedStyles[0].className : '';

        return clsx(
            'select-none',
            isSelected && 'bg-blue-100 ring-1 ring-inset ring-blue-300 hover:bg-blue-100',
            !isSelected && isConfirmed && 'bg-green-50/60',
            !isSelected && dynamicClass,
        );
    }, [reviewStates, selectedSet, rowStyles]);

    return (
        // onClickCapture fires in capture phase (before row onClick bubbles)
        <div className="h-full" onClickCapture={handleNativeClick}>
            <UniversalTableCore
                rowModel={rowModel}
                columns={columns}
                compact
                stickyHeader
                onRowClick={handleRowClick}
                getRowClassName={getRowClassName}
            />
        </div>
    );
}
