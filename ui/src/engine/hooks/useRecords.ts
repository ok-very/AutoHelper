import { useState, useEffect } from 'react';
import type { Manifest } from '../types/manifest';
import type { SubmissionRecord } from '../types/record';

interface UseRecordsResult {
    records: SubmissionRecord[];
    loading: boolean;
    error: string | null;
}

/**
 * Fetch records from the manifest's dataSources.records path.
 * Uses manifest.recordId to determine which field serves as the unique identifier.
 */
export function useRecords(manifest: Manifest | null): UseRecordsResult {
    const [records, setRecords] = useState<SubmissionRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!manifest) return;
        let cancelled = false;

        async function load() {
            try {
                const res = await fetch(manifest!.dataSources.records);
                if (!res.ok) throw new Error(`Failed to load records: ${res.status}`);
                const raw: Record<string, unknown>[] = await res.json();

                const idField = manifest!.recordId;
                const parsed: SubmissionRecord[] = raw.map((item, idx) => {
                    const id = String(item[idField] ?? idx + 1);
                    return { id, fields: item };
                });

                if (!cancelled) {
                    setRecords(parsed);
                    setError(null);
                }
            } catch (err) {
                if (!cancelled) {
                    setError(err instanceof Error ? err.message : String(err));
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        }

        load();
        return () => { cancelled = true; };
    }, [manifest]);

    return { records, loading, error };
}
