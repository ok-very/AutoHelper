import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ReviewSessionState, ReviewState, SubmissionRecord } from '../types/record';

interface ReviewStoreActions {
    /** Initialize with loaded records (sets up empty review states for new records) */
    initRecords: (records: SubmissionRecord[], saved?: Record<string, Partial<ReviewState>>) => void;
    /** Select a single record by ID (clears multi-select) */
    select: (id: string | null) => void;
    /** Ctrl+click: toggle a record in the multi-selection */
    selectToggle: (id: string) => void;
    /** Shift+click: select range from anchor to target */
    selectRange: (id: string, orderedIds: string[]) => void;
    /** Ctrl+Shift+click: add range from anchor to target */
    selectRangeAdd: (id: string, orderedIds: string[]) => void;
    /** Toggle a value in an assignment group for a record (multi-select) */
    toggleAssignment: (recordId: string, groupId: string, value: string) => void;
    /** Clear all values in an assignment group for a record */
    clearAssignment: (recordId: string, groupId: string) => void;
    /** Set rank for a record */
    setRank: (recordId: string, rank: number) => void;
    /** Set reviewer notes for a record */
    setNotes: (recordId: string, notes: string) => void;
    /** Toggle a DPI tier selection for a record */
    toggleDpi: (recordId: string, tierId: string) => void;
    /** Mark a record as confirmed */
    confirm: (recordId: string) => void;
    /** Remove confirmation from a record */
    unconfirm: (recordId: string) => void;
    /** Set a filter value */
    setFilter: (field: string, value: string | null) => void;
    /** Set global search text */
    setSearchText: (text: string) => void;
    /** Navigate to next/previous record in a given ID list */
    selectRelative: (direction: 1 | -1, orderedIds: string[]) => void;
}

type ReviewStore = ReviewSessionState & ReviewStoreActions;

const EMPTY_STATE: ReviewState = { assignments: {}, rank: 0, confirmed: false, notes: '', selectedDpis: [] };

/** Migrate old string|null assignment values to string[] and clean corrupted data */
function migrateAssignments(raw: Record<string, unknown>): Record<string, string[]> {
    const result: Record<string, string[]> = {};
    for (const [key, val] of Object.entries(raw)) {
        if (Array.isArray(val)) {
            // Filter out single-char garbage from old string-spread corruption
            result[key] = val.filter((v): v is string => typeof v === 'string' && v.length > 1);
        } else if (typeof val === 'string' && val) {
            result[key] = [val];
        } else {
            result[key] = [];
        }
    }
    return result;
}

function ensureState(
    states: Record<string, ReviewState>,
    recordId: string
): ReviewState {
    const s = states[recordId];
    if (!s) return EMPTY_STATE;
    return {
        ...EMPTY_STATE,
        ...s,
        assignments: migrateAssignments((s.assignments ?? {}) as Record<string, unknown>),
        selectedDpis: s.selectedDpis ?? [],
    };
}

/**
 * Create a review store scoped to a manifest ID.
 * The persist key includes the manifest ID so different jobs don't collide.
 */
export function createReviewStore(manifestId: string) {
    return create<ReviewStore>()(
        persist(
            (set, get) => ({
                reviewStates: {},
                selectedId: null,
                selectedIds: [],
                filters: {},
                searchText: '',

                initRecords: (records, saved) => {
                    const existing = get().reviewStates;
                    const merged: Record<string, ReviewState> = {};

                    // Migrate existing persisted states (may have old string assignments)
                    for (const [id, rs] of Object.entries(existing)) {
                        merged[id] = ensureState(existing, id);
                    }

                    for (const rec of records) {
                        if (!merged[rec.id]) {
                            merged[rec.id] = { assignments: {}, rank: 0, confirmed: false, notes: '', selectedDpis: [] };
                        }
                    }

                    // Overlay any saved state from the data source
                    if (saved) {
                        for (const [id, partial] of Object.entries(saved)) {
                            if (merged[id]) {
                                const partialAssignments = partial.assignments
                                    ? migrateAssignments(partial.assignments as Record<string, unknown>)
                                    : {};
                                merged[id] = {
                                    ...merged[id],
                                    ...partial,
                                    assignments: { ...merged[id].assignments, ...partialAssignments },
                                    selectedDpis: merged[id].selectedDpis ?? [],
                                };
                            }
                        }
                    }

                    set({ reviewStates: merged });
                    // Auto-select first if nothing selected
                    if (!get().selectedId && records.length > 0) {
                        set({ selectedId: records[0].id, selectedIds: [records[0].id] });
                    }
                },

                select: (id) => set({ selectedId: id, selectedIds: id ? [id] : [] }),

                selectToggle: (id) => {
                    const { selectedIds, selectedId } = get();
                    const has = selectedIds.includes(id);
                    if (has) {
                        const next = selectedIds.filter((x) => x !== id);
                        set({
                            selectedIds: next,
                            selectedId: next.length > 0 ? next[next.length - 1] : null,
                        });
                    } else {
                        set({
                            selectedIds: [...selectedIds, id],
                            selectedId: id,
                        });
                    }
                },

                selectRange: (id, orderedIds) => {
                    const anchor = get().selectedId;
                    if (!anchor) { set({ selectedId: id, selectedIds: [id] }); return; }
                    const a = orderedIds.indexOf(anchor);
                    const b = orderedIds.indexOf(id);
                    if (a === -1 || b === -1) return;
                    const start = Math.min(a, b);
                    const end = Math.max(a, b);
                    const range = orderedIds.slice(start, end + 1);
                    set({ selectedIds: range, selectedId: anchor });
                },

                selectRangeAdd: (id, orderedIds) => {
                    const { selectedIds, selectedId } = get();
                    const anchor = selectedId;
                    if (!anchor) { set({ selectedId: id, selectedIds: [id] }); return; }
                    const a = orderedIds.indexOf(anchor);
                    const b = orderedIds.indexOf(id);
                    if (a === -1 || b === -1) return;
                    const start = Math.min(a, b);
                    const end = Math.max(a, b);
                    const range = orderedIds.slice(start, end + 1);
                    const merged = [...new Set([...selectedIds, ...range])];
                    set({ selectedIds: merged, selectedId: anchor });
                },

                toggleAssignment: (recordId, groupId, value) =>
                    set((s) => {
                        const current = ensureState(s.reviewStates, recordId);
                        const arr = current.assignments[groupId] ?? [];
                        const has = arr.includes(value);
                        return {
                            reviewStates: {
                                ...s.reviewStates,
                                [recordId]: {
                                    ...current,
                                    assignments: {
                                        ...current.assignments,
                                        [groupId]: has ? arr.filter((v) => v !== value) : [...arr, value],
                                    },
                                },
                            },
                        };
                    }),

                clearAssignment: (recordId, groupId) =>
                    set((s) => ({
                        reviewStates: {
                            ...s.reviewStates,
                            [recordId]: {
                                ...ensureState(s.reviewStates, recordId),
                                assignments: {
                                    ...ensureState(s.reviewStates, recordId).assignments,
                                    [groupId]: [],
                                },
                            },
                        },
                    })),

                setRank: (recordId, rank) =>
                    set((s) => ({
                        reviewStates: {
                            ...s.reviewStates,
                            [recordId]: {
                                ...ensureState(s.reviewStates, recordId),
                                rank,
                            },
                        },
                    })),

                setNotes: (recordId, notes) =>
                    set((s) => ({
                        reviewStates: {
                            ...s.reviewStates,
                            [recordId]: {
                                ...ensureState(s.reviewStates, recordId),
                                notes,
                            },
                        },
                    })),

                toggleDpi: (recordId, tierId) =>
                    set((s) => {
                        const current = ensureState(s.reviewStates, recordId);
                        const has = current.selectedDpis.includes(tierId);
                        return {
                            reviewStates: {
                                ...s.reviewStates,
                                [recordId]: {
                                    ...current,
                                    selectedDpis: has
                                        ? current.selectedDpis.filter((d) => d !== tierId)
                                        : [...current.selectedDpis, tierId],
                                },
                            },
                        };
                    }),

                confirm: (recordId) =>
                    set((s) => ({
                        reviewStates: {
                            ...s.reviewStates,
                            [recordId]: {
                                ...ensureState(s.reviewStates, recordId),
                                confirmed: true,
                            },
                        },
                    })),

                unconfirm: (recordId) =>
                    set((s) => ({
                        reviewStates: {
                            ...s.reviewStates,
                            [recordId]: {
                                ...ensureState(s.reviewStates, recordId),
                                confirmed: false,
                            },
                        },
                    })),

                setFilter: (field, value) =>
                    set((s) => ({
                        filters: { ...s.filters, [field]: value },
                    })),

                setSearchText: (text) => set({ searchText: text }),

                selectRelative: (direction, orderedIds) => {
                    const current = get().selectedId;
                    if (!current || orderedIds.length === 0) return;
                    const idx = orderedIds.indexOf(current);
                    const next = idx + direction;
                    if (next >= 0 && next < orderedIds.length) {
                        const nextId = orderedIds[next];
                        set({ selectedId: nextId, selectedIds: [nextId] });
                    }
                },
            }),
            {
                name: `review-state-${manifestId}`,
                version: 1,
                partialize: (state) => ({
                    reviewStates: state.reviewStates,
                    selectedId: state.selectedId,
                    selectedIds: state.selectedIds,
                }),
            }
        )
    );
}

export type ReviewStoreApi = ReturnType<typeof createReviewStore>;
