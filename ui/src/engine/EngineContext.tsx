import { createContext, useContext } from 'react';
import type { Manifest } from './types/manifest';
import type { ReviewStoreApi } from './stores/reviewStore';
import type { SubmissionRecord } from './types/record';

interface EngineContextValue {
    manifest: Manifest;
    store: ReviewStoreApi;
    records: SubmissionRecord[];
}

const EngineContext = createContext<EngineContextValue | null>(null);

export function EngineProvider({
    manifest,
    store,
    records,
    children,
}: EngineContextValue & { children: React.ReactNode }) {
    return (
        <EngineContext.Provider value={{ manifest, store, records }}>
            {children}
        </EngineContext.Provider>
    );
}

export function useEngine(): EngineContextValue {
    const ctx = useContext(EngineContext);
    if (!ctx) throw new Error('useEngine must be used within EngineProvider');
    return ctx;
}
