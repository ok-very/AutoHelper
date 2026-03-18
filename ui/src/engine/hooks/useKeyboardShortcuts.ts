import { useEffect } from 'react';
import type { Manifest } from '../types/manifest';
import type { ReviewStoreApi } from '../stores/reviewStore';
import { useStore } from 'zustand';

/**
 * Bind keyboard shortcuts from manifest assignment groups.
 * Also binds arrow keys / comma / period for navigation and c/u for confirm/unconfirm.
 */
export function useKeyboardShortcuts(
    manifest: Manifest | null,
    store: ReviewStoreApi,
    orderedIds: string[],
) {
    const selectedId = useStore(store, (s) => s.selectedId);
    const toggleAssignment = useStore(store, (s) => s.toggleAssignment);
    const clearAssignment = useStore(store, (s) => s.clearAssignment);
    const confirm = useStore(store, (s) => s.confirm);
    const unconfirm = useStore(store, (s) => s.unconfirm);
    const selectRelative = useStore(store, (s) => s.selectRelative);

    useEffect(() => {
        if (!manifest) return;

        // Build shortcut map: key → { groupId, value }
        const shortcutMap = new Map<string, { groupId: string; value: string | null }>();
        for (const [groupId, group] of Object.entries(manifest.assignmentGroups)) {
            if (group.shortcutKeys) {
                for (const [key, value] of Object.entries(group.shortcutKeys)) {
                    shortcutMap.set(key, { groupId, value });
                }
            }
        }

        function handleKeyDown(e: KeyboardEvent) {
            // Skip when focus is in an input/textarea
            const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
            if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
            if ((e.target as HTMLElement)?.isContentEditable) return;

            // Ctrl+S: prevent default (save handled by persist)
            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                return;
            }

            // Navigation
            if (e.key === 'ArrowLeft' || e.key === ',') {
                e.preventDefault();
                selectRelative(-1, orderedIds);
                return;
            }
            if (e.key === 'ArrowRight' || e.key === '.') {
                e.preventDefault();
                selectRelative(1, orderedIds);
                return;
            }

            // Confirm / Unconfirm
            if (e.key === 'c' && selectedId) {
                confirm(selectedId);
                return;
            }
            if (e.key === 'u' && selectedId) {
                unconfirm(selectedId);
                return;
            }

            // Assignment shortcuts
            const mapping = shortcutMap.get(e.key);
            if (mapping && selectedId) {
                if (mapping.value === null) {
                    // null shortcut clears the group
                    clearAssignment(selectedId, mapping.groupId);
                } else {
                    toggleAssignment(selectedId, mapping.groupId, mapping.value);
                }
                return;
            }
        }

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [manifest, selectedId, orderedIds, toggleAssignment, clearAssignment, confirm, unconfirm, selectRelative]);
}
