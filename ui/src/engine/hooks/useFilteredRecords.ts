import { useMemo } from 'react';
import type { Manifest } from '../types/manifest';
import type { SubmissionRecord, ReviewState } from '../types/record';

/**
 * Filter records based on manifest filter definitions, search text, and current review state.
 * Returns the filtered + sorted list of record IDs.
 */
export function useFilteredRecords(
    records: SubmissionRecord[],
    manifest: Manifest | null,
    reviewStates: Record<string, ReviewState>,
    filters: Record<string, string | null>,
    searchText: string,
): SubmissionRecord[] {
    return useMemo(() => {
        if (!manifest) return records;

        let filtered = records;

        // Text search across searchable fields
        if (searchText.trim()) {
            const query = searchText.toLowerCase();
            const searchableFields = Object.entries(manifest.fields)
                .filter(([, def]) => def.searchable)
                .map(([key]) => key);

            filtered = filtered.filter((rec) =>
                searchableFields.some((field) => {
                    const val = rec.fields[field];
                    return typeof val === 'string' && val.toLowerCase().includes(query);
                })
            );
        }

        // Apply each active filter
        for (const [field, filterValue] of Object.entries(filters)) {
            if (filterValue === null || filterValue === undefined) continue;

            const fieldDef = manifest.fields[field];
            if (!fieldDef) continue;

            if (fieldDef.type === 'assignment' && fieldDef.group) {
                // Filter by assignment group value from review state (arrays)
                const groupId = fieldDef.group;
                if (filterValue === '__unassigned__') {
                    filtered = filtered.filter((rec) => {
                        const rs = reviewStates[rec.id];
                        return !rs?.assignments[groupId]?.length;
                    });
                } else {
                    filtered = filtered.filter((rec) => {
                        const rs = reviewStates[rec.id];
                        return rs?.assignments[groupId]?.includes(filterValue) ?? false;
                    });
                }
            } else if (fieldDef.type === 'boolean') {
                filtered = filtered.filter((rec) => {
                    const val = rec.fields[field];
                    return filterValue === 'true' ? !!val : !val;
                });
            } else if (fieldDef.type === 'enum') {
                filtered = filtered.filter((rec) =>
                    rec.fields[field] === filterValue
                );
            } else {
                // Generic equality
                filtered = filtered.filter((rec) =>
                    String(rec.fields[field] ?? '') === filterValue
                );
            }
        }

        return filtered;
    }, [records, manifest, reviewStates, filters, searchText]);
}
