/**
 * FilterChip - Muted badge with remove button for active filters
 *
 * Design: pill-shaped, 24px tall, muted workspace colors, X icon
 * Used inside FilterBar to display active filters.
 */

import { X } from 'lucide-react';
import { clsx } from 'clsx';

export interface FilterChipProps {
    /** Filter label (e.g., "Status", "Phase") */
    label: string;
    /** Optional filter value (e.g., "Complete", "Planning") */
    value?: string;
    /** Called when X icon is clicked */
    onRemove: () => void;
    className?: string;
}

export function FilterChip({ label, value, onRemove, className }: FilterChipProps) {
    return (
        <span
            className={clsx(
                'inline-flex items-center gap-1.5 h-6 px-2.5 rounded-full border font-sans text-xs',
                className
            )}
            style={{
                backgroundColor: 'var(--ws-bg)',
                borderColor: 'var(--ws-panel-border)',
                color: 'var(--ws-text-secondary)',
            }}
        >
            <span className="flex items-center gap-1">
                <span className="font-medium">{label}</span>
                {value && <span>{value}</span>}
            </span>
            <button
                type="button"
                onClick={onRemove}
                className="flex-shrink-0 hover:opacity-60 transition-opacity"
                aria-label={`Remove ${label} filter`}
            >
                <X size={12} />
            </button>
        </span>
    );
}
