import { useState, useEffect } from 'react';
import { ManifestSchema, type Manifest } from '../types/manifest';

interface UseManifestResult {
    manifest: Manifest | null;
    error: string | null;
    loading: boolean;
}

/**
 * Load and validate a manifest JSON file.
 */
export function useManifest(manifestUrl: string): UseManifestResult {
    const [manifest, setManifest] = useState<Manifest | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;

        async function load() {
            try {
                const res = await fetch(manifestUrl);
                if (!res.ok) throw new Error(`Failed to load manifest: ${res.status}`);
                const json = await res.json();
                const parsed = ManifestSchema.parse(json);
                if (!cancelled) {
                    setManifest(parsed);
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
    }, [manifestUrl]);

    return { manifest, error, loading };
}
