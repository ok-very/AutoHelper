/**
 * Table Core Types
 *
 * Domain-agnostic contracts for the Universal Table Core.
 * These types are unaware of "flat vs hierarchy" and unaware of FieldViewModel.
 *
 * Key principle: The core renders ReactNodes provided by wrappers.
 * Wrappers are responsible for building FieldViewModels and calling domain factories.
 */

import type { ReactNode } from 'react';

// ============================================================================
// ROW TYPES
// ============================================================================

export type RowId = string;

/**
 * A row in the table.
 * - `id`: Unique row identifier
 * - `data`: The underlying data (DataRecord, ActionView, HierarchyNode, etc.)
 * - `meta`: Optional metadata for rendering (depth, hasChildren, parentId)
 */
export type TableRow = {
    id: RowId;
    data: unknown;
    meta?: Record<string, unknown>;
};

// ============================================================================
// CELL RENDER CONTEXT
// ============================================================================

/**
 * Context passed to cell render functions.
 * Allows the core to communicate display settings to cell renderers.
 */
export interface CellRenderContext {
    /** Whether text should wrap instead of truncate */
    wrapText?: boolean;
}

// ============================================================================
// COLUMN TYPES
// ============================================================================

/**
 * Column definition for the table.
 *
 * Note: `cell` returns a ReactNode, not a value. The wrapper is responsible
 * for building and rendering EditableCell or any other component.
 */
export type TableColumn = {
    /** Unique column identifier */
    id: string;
    /** Header display text */
    header: string;
    /**
     * Custom header renderer. If provided, overrides the default text header.
     * Useful for checkbox columns, icons, etc.
     */
    renderHeader?: () => ReactNode;
    /** Width in pixels or 'flex' for flexible */
    width?: number | 'flex';
    /** Minimum width when resizing */
    minWidth?: number;
    /**
     * Cell renderer - returns ReactNode.
     * The wrapper provides this function, typically returning <EditableCell viewModel={...} />
     * @param row - The row data
     * @param context - Optional render context (e.g., wrapText flag)
     */
    cell: (row: TableRow, context?: CellRenderContext) => ReactNode;
    /**
     * Sort key extractor. If provided, column is sortable.
     * Returns the value to sort by, or null for unsortable rows.
     */
    sortKey?: (row: TableRow) => string | number | null;
    /** Text alignment */
    align?: 'left' | 'center' | 'right';
    /** Whether column is resizable */
    resizable?: boolean;
};

// ============================================================================
// ROW MODEL
// ============================================================================

/**
 * Capabilities that a RowModel can support.
 */
export type RowModelCapabilities = {
    /** Whether rows can be selected */
    selectable?: boolean;
    /** Whether rows can be expanded (for hierarchy) */
    expandable?: boolean;
};

/**
 * RowModel provides the rows to render and optional expand/collapse behavior.
 *
 * Adapters (FlatRowModelAdapter, HierarchyRowModelAdapter, ActionViewRowModelAdapter)
 * implement this interface to bridge domain data to the core.
 */
export type RowModel = {
    /** Get all visible rows */
    getRows: () => TableRow[];
    /** Get a specific row by ID */
    getRowById?: (id: RowId) => TableRow | undefined;
    /** Capabilities of this row model */
    capabilities: RowModelCapabilities;

    // Expand/collapse (for hierarchy)
    /** Check if a row is expanded */
    isExpanded?: (id: RowId) => boolean;
    /** Toggle expansion state */
    toggleExpanded?: (id: RowId) => void;
};

// ============================================================================
// SORT STATE
// ============================================================================

export type SortDirection = 'asc' | 'desc';

export type SortState = {
    columnId: string;
    direction: SortDirection;
} | null;
