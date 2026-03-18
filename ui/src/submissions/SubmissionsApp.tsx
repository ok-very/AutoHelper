import { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import {
    DockviewReact,
    type DockviewReadyEvent,
    type IDockviewPanelProps,
} from 'dockview';
import 'dockview/dist/styles/dockview.css';

import { useManifest, useRecords, useKeyboardShortcuts } from '@engine/hooks';
import { useFilteredRecords } from '@engine/hooks/useFilteredRecords';
import { createReviewStore, type ReviewStoreApi } from '@engine/stores/reviewStore';
import { EngineProvider } from '@engine/EngineContext';
import { FilterBar, TallyBar } from '@engine/components';
import { ListPanel } from '@engine/panels/ListPanel';
import { PreviewPanel } from '@engine/panels/PreviewPanel';
import { DetailPanel } from '@engine/panels/DetailPanel';
import { PANEL_IDS } from '@engine/panels/panelRegistry';
import { Spinner } from '@ui/atoms';
import { useStore } from 'zustand';
import type { Manifest } from '@engine/types/manifest';
import type { SubmissionRecord } from '@engine/types/record';
import { ModuleLayout } from '@/components/ModuleLayout';

function getManifestUrl(): string {
    const params = new URLSearchParams(window.location.search);
    const id = params.get('manifest') ?? 'burnaby-hospital';
    return `/manifests/${id}.json`;
}

// Stable component map — panels read state from EngineContext, not props
const PANEL_COMPONENTS: Record<string, React.FC<IDockviewPanelProps>> = {
    [PANEL_IDS.LIST]: () => <ListPanel />,
    [PANEL_IDS.PREVIEW]: () => <PreviewPanel />,
    [PANEL_IDS.DETAIL]: () => <DetailPanel />,
};

/**
 * Check if image folders are configured before loading the review engine.
 */
function useImageRootsCheck() {
    const [ready, setReady] = useState<boolean | null>(null); // null = loading
    useEffect(() => {
        fetch('/config')
            .then(r => r.json())
            .then(cfg => {
                const roots: string[] = cfg.image_allowed_roots ?? [];
                setReady(roots.length > 0);
            })
            .catch(() => setReady(false));
    }, []);
    return ready;
}

export function SubmissionsApp() {
    const imageRootsReady = useImageRootsCheck();

    const content = (() => {
        if (imageRootsReady === null) {
            return (
                <div className="h-full flex items-center justify-center gap-2 text-ws-muted">
                    <Spinner size="md" />
                </div>
            );
        }
        if (!imageRootsReady) {
            return <SetupPrompt />;
        }
        return <ReviewEngine />;
    })();

    return (
        <ModuleLayout module="image-sorting" activePage="review" flush>
            {content}
        </ModuleLayout>
    );
}

function SetupPrompt() {
    return (
        <div className="h-full flex items-center justify-center">
            <div className="text-center max-w-md">
                <p className="text-lg font-medium text-slate-700 mb-2">
                    Image folders not configured
                </p>
                <p className="text-sm text-slate-500 mb-4">
                    Add at least one image directory in Submissions Settings so the review
                    engine can display images.
                </p>
                <a
                    href="/image-sorting/settings"
                    className="inline-block px-4 py-2 text-sm font-medium rounded bg-blue-600 text-white hover:bg-blue-700 transition-colors"
                >
                    Open Settings
                </a>
            </div>
        </div>
    );
}

function ReviewEngine() {
    const manifestUrl = useMemo(getManifestUrl, []);
    const { manifest, error: manifestError, loading: manifestLoading } = useManifest(manifestUrl);
    const { records, error: recordsError, loading: recordsLoading } = useRecords(manifest);

    const storeRef = useRef<ReviewStoreApi | null>(null);
    if (!storeRef.current && manifest) {
        storeRef.current = createReviewStore(manifest.id);
    }
    const store = storeRef.current;

    if (manifestLoading || recordsLoading) {
        return (
            <div className="h-full flex items-center justify-center gap-2 text-ws-muted">
                <Spinner size="md" />
                <span className="text-sm">Loading...</span>
            </div>
        );
    }

    if (manifestError || recordsError) {
        return (
            <div className="h-full flex items-center justify-center">
                <div className="text-center">
                    <p className="text-sm font-medium text-ws-error">Failed to load</p>
                    <p className="text-xs text-ws-text-secondary mt-1">{manifestError ?? recordsError}</p>
                </div>
            </div>
        );
    }

    if (!manifest || !store) return null;

    return (
        <EngineProvider manifest={manifest} store={store} records={records}>
            <AppInner manifest={manifest} records={records} store={store} />
        </EngineProvider>
    );
}

function AppInner({
    manifest,
    records,
    store,
}: {
    manifest: Manifest;
    records: SubmissionRecord[];
    store: ReviewStoreApi;
}) {
    useEffect(() => {
        if (records.length > 0) {
            store.getState().initRecords(records);
        }
    }, [store, records]);

    const reviewStates = useStore(store, (s) => s.reviewStates);
    const filters = useStore(store, (s) => s.filters);
    const searchText = useStore(store, (s) => s.searchText);

    const filteredRecords = useFilteredRecords(records, manifest, reviewStates, filters, searchText);
    const orderedIds = useMemo(() => filteredRecords.map((r) => r.id), [filteredRecords]);

    useKeyboardShortcuts(manifest, store, orderedIds);

    const onReady = useCallback((event: DockviewReadyEvent) => {
        const api = event.api;

        const listPanel = api.addPanel({
            id: PANEL_IDS.LIST,
            component: PANEL_IDS.LIST,
            title: 'Submissions',
        });

        const previewPanel = api.addPanel({
            id: PANEL_IDS.PREVIEW,
            component: PANEL_IDS.PREVIEW,
            title: 'Preview',
            position: { referencePanel: listPanel, direction: 'right' },
        });

        api.addPanel({
            id: PANEL_IDS.DETAIL,
            component: PANEL_IDS.DETAIL,
            title: 'Detail',
            position: { referencePanel: previewPanel, direction: 'right' },
        });

        api.getPanel(PANEL_IDS.LIST)?.api.setSize({ width: 420 });
        api.getPanel(PANEL_IDS.DETAIL)?.api.setSize({ width: 380 });

        // Force tab headers visible on all groups (dockview v4 hides them for single-panel groups)
        for (const group of api.groups) {
            (group.model as any).header.hidden = false;
        }
    }, []);

    return (
        <div className="h-full flex flex-col">
            <FilterBar manifest={manifest} store={store} />
            <TallyBar
                manifest={manifest}
                records={records}
                reviewStates={reviewStates}
                totalCount={filteredRecords.length}
            />
            <div className="flex-1 min-h-0">
                <DockviewReact
                    className="dockview-theme-light"
                    onReady={onReady}
                    components={PANEL_COMPONENTS}
                />
            </div>
        </div>
    );
}
