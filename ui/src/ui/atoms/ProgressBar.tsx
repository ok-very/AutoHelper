import { clsx } from 'clsx';

/**
 * Segment data for ProgressBar - pure data, no domain knowledge
 */
export interface ProgressSegment {
    /** Unique key for the segment */
    key: string;
    /** Percentage width (0-100) */
    percentage: number;
    /** CSS color value */
    color: string;
    /** Display label for tooltip */
    label: string;
    /** Count of items in this segment */
    count: number;
}

export interface ProgressBarProps {
    /** Array of segments to display (for multi-segment bars) */
    segments?: ProgressSegment[];
    /** Simple percentage value 0-100 (alternative to segments) */
    value?: number;
    /** Height of the bar */
    height?: number | string;
    /** Size preset */
    size?: 'xs' | 'sm' | 'md' | 'lg';
    /** Additional className */
    className?: string;
    /** Whether to show tooltips on hover */
    showTooltip?: boolean;
    /** Color for simple value mode */
    color?: string;
}

/**
 * ProgressBar - Pure presentational component
 * 
 * Displays a segmented progress bar. Receives pre-computed segments
 * with colors and percentages - no domain logic here.
 */
const sizeToHeight = {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
};

export function ProgressBar({
    segments,
    value,
    height,
    size = 'md',
    className,
    showTooltip = true,
    color = 'var(--ws-accent, #3b82f6)',
}: ProgressBarProps) {
    const resolvedHeight = height ?? sizeToHeight[size];

    // Simple value mode (0-100 percentage)
    if (value !== undefined) {
        return (
            <div
                className={clsx("w-full bg-ws-panel-border rounded overflow-hidden", className)}
                style={{ height: resolvedHeight }}
            >
                <div
                    className="h-full transition-all duration-300"
                    style={{
                        width: `${Math.min(100, Math.max(0, value))}%`,
                        backgroundColor: color,
                    }}
                />
            </div>
        );
    }

    // If no segments, show empty bar
    if (!segments || segments.length === 0) {
        return (
            <div
                className={clsx("w-full bg-ws-panel-border rounded overflow-hidden", className)}
                style={{ height: resolvedHeight }}
            />
        );
    }

    return (
        <div
            className={clsx("flex rounded overflow-hidden shadow-sm bg-ws-panel-border w-full", className)}
            style={{ height: resolvedHeight }}
        >
            {segments.map((segment) => (
                <div
                    key={segment.key}
                    className="h-full transition-all duration-500 relative group border-r border-white/20 last:border-0"
                    style={{
                        width: `${segment.percentage}%`,
                        backgroundColor: segment.color
                    }}
                >
                    {showTooltip && (
                        <div className="opacity-0 group-hover:opacity-100 absolute bottom-full mb-1 left-1/2 -translate-x-1/2 bg-slate-800 text-white text-[10px] px-2 py-1 rounded shadow-lg whitespace-nowrap pointer-events-none z-50 transition-opacity">
                            <div className="font-semibold capitalize">{segment.label}</div>
                            <div>{segment.count} items ({Math.round(segment.percentage)}%)</div>
                        </div>
                    )}
                </div>
            ))}
        </div>
    );
}
