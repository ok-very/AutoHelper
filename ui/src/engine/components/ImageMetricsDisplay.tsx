import { Badge } from '@ui/atoms';
import type { ImageMetricsResult } from '../hooks/useImageMetrics';

interface ImageMetricsDisplayProps {
    widthPx?: number;
    heightPx?: number;
    fileBytes?: number;
    metrics: ImageMetricsResult;
    selectedDpis?: string[];
    onToggleDpi?: (tierId: string) => void;
    disabled?: boolean;
}

function formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatInches(inches: number): string {
    return inches.toFixed(1);
}

export function ImageMetricsDisplay({ widthPx, heightPx, fileBytes, metrics, selectedDpis, onToggleDpi, disabled }: ImageMetricsDisplayProps) {
    if (!widthPx || !heightPx) {
        return <p className="text-xs text-ws-text-secondary italic">No image dimensions available</p>;
    }

    const selected = selectedDpis ?? [];

    return (
        <div className="flex flex-col gap-1.5">
            <div className="text-xs text-ws-fg">
                <span className="font-medium">{widthPx} x {heightPx}</span> px
                {fileBytes != null && (
                    <span className="ml-2 text-ws-text-secondary">({formatBytes(fileBytes)})</span>
                )}
            </div>

            {metrics.metrics.map((m) => {
                const isSelected = selected.includes(m.tier.id);
                return (
                    <label
                        key={m.tier.id}
                        className={`
                            flex items-center gap-1.5 px-2 py-0.5 rounded text-xs select-none
                            border transition-colors
                            ${disabled ? 'cursor-default opacity-60' : 'cursor-pointer'}
                            ${isSelected
                                ? 'bg-blue-50 border-blue-300 text-blue-800 font-medium'
                                : 'bg-white border-ws-panel-border text-ws-text-secondary hover:border-blue-200'}
                        `}
                    >
                        {onToggleDpi && (
                            <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={() => !disabled && onToggleDpi(m.tier.id)}
                                disabled={disabled}
                                className="sr-only"
                            />
                        )}
                        <span>
                            {m.tier.label}: {formatInches(m.widthInches)} x {formatInches(m.heightInches)} in
                        </span>
                    </label>
                );
            })}

            {metrics.viability.map((v) => (
                <Badge
                    key={v.rule.id}
                    variant={v.passed ? 'success' : 'error'}
                    size="xs"
                >
                    {v.rule.label} {v.passed ? '\u2713' : '\u2717'}
                </Badge>
            ))}
        </div>
    );
}
