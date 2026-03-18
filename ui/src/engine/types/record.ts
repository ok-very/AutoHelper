/**
 * Generic submission record — a flat bag of fields keyed by the manifest's field IDs.
 * The engine never knows what specific fields exist; that's all manifest-driven.
 */
export interface SubmissionRecord {
    /** Unique identifier for this record (derived from manifest.recordId) */
    id: string;
    /** Flat key-value fields matching manifest field IDs */
    fields: Record<string, unknown>;
}

/**
 * Per-record review state, persisted separately from source data.
 * Assignment values are keyed by assignmentGroup ID.
 */
export interface ReviewState {
    assignments: Record<string, string[]>;
    rank: number;
    confirmed: boolean;
    notes: string;
    selectedDpis: string[];
}

/**
 * The full review store state for a single manifest session.
 */
export interface ReviewSessionState {
    /** Review state per record ID */
    reviewStates: Record<string, ReviewState>;
    /** Currently selected record ID (anchor for range selection) */
    selectedId: string | null;
    /** All currently selected record IDs (for multi-select) */
    selectedIds: string[];
    /** Active filter values: filterField → selected value (null = all) */
    filters: Record<string, string | null>;
    /** Global text search */
    searchText: string;
}

/** Create a blank review state for a new record */
export function createEmptyReviewState(): ReviewState {
    return {
        assignments: {},
        rank: 0,
        confirmed: false,
        notes: '',
        selectedDpis: [],
    };
}
