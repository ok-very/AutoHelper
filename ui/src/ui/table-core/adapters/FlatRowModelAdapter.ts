/**
 * Flat Row Model Adapter
 *
 * Adapts DataRecord[] to RowModel for use with UniversalTableCore.
 * Used by DataTableFlat composite.
 */

import type { RowModel, TableRow } from '../types';

/**
 * Minimal DataRecord type - keep this adapter loosely coupled
 */
export interface FlatRecord {
    id: string;
}

/**
 * Create a RowModel from an array of flat records (DataRecord[]).
 *
 * @param records - Array of records with at least an `id` property
 * @returns RowModel for use with UniversalTableCore
 */
export function makeFlatRowModel<T extends FlatRecord>(records: T[]): RowModel {
    const rows: TableRow[] = records.map((r) => ({
        id: r.id,
        data: r,
    }));

    const rowMap = new Map(rows.map((r) => [r.id, r]));

    return {
        getRows: () => rows,
        getRowById: (id) => rowMap.get(id),
        capabilities: {
            selectable: true,
            expandable: false,
        },
    };
}
