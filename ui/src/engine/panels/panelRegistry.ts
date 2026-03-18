/**
 * Panel definitions for the Dockview layout.
 * These are generic — the actual content is manifest-driven.
 */
export const PANEL_IDS = {
    LIST: 'submission-list',
    PREVIEW: 'preview',
    DETAIL: 'detail',
} as const;

export type PanelId = (typeof PANEL_IDS)[keyof typeof PANEL_IDS];
