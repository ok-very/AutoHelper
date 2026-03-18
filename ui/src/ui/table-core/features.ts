/**
 * Table Features
 *
 * Features are plugins that can:
 * - Add toolbar content (left/right slots)
 * - Decorate columns (e.g., add indent/chevron for hierarchy)
 * - Transform rows (e.g., add metadata)
 *
 * Features allow wrappers to extend core behavior without modifying it.
 */

import type { ReactNode } from 'react';

import type { TableColumn, TableRow, RowModel } from './types';

// ============================================================================
// TABLE CONTEXT
// ============================================================================

/**
 * Context passed to features for rendering decisions.
 */
export type TableCtx = {
    rowModel: RowModel;
    columns: TableColumn[];
};

// ============================================================================
// TABLE FEATURE
// ============================================================================

/**
 * A feature that can extend the table's behavior.
 */
export type TableFeature = {
    /** Unique feature identifier */
    id: string;

    /**
     * Render content in the left side of the toolbar.
     * Example: row count, selection summary
     */
    renderToolbarLeft?: (ctx: TableCtx) => ReactNode;

    /**
     * Render content in the right side of the toolbar.
     * Example: column picker, filter controls
     */
    renderToolbarRight?: (ctx: TableCtx) => ReactNode;

    /**
     * Decorate columns before rendering.
     * Example: prepend indent/chevron column for hierarchy
     */
    decorateColumns?: (cols: TableColumn[], ctx: TableCtx) => TableColumn[];

    /**
     * Transform a row before rendering.
     * Example: add computed metadata
     */
    decorateRow?: (row: TableRow, ctx: TableCtx) => TableRow;
};

/**
 * Apply all feature column decorators in order.
 */
export function applyColumnDecorators(
    columns: TableColumn[],
    features: TableFeature[],
    ctx: TableCtx
): TableColumn[] {
    return features.reduce((cols, feature) => {
        if (feature.decorateColumns) {
            return feature.decorateColumns(cols, ctx);
        }
        return cols;
    }, columns);
}

/**
 * Apply all feature row decorators in order.
 */
export function applyRowDecorators(
    row: TableRow,
    features: TableFeature[],
    ctx: TableCtx
): TableRow {
    return features.reduce((r, feature) => {
        if (feature.decorateRow) {
            return feature.decorateRow(r, ctx);
        }
        return r;
    }, row);
}
