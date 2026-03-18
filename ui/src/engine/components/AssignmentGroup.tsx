import type { AssignmentGroup as AssignmentGroupDef } from '../types/manifest';

interface AssignmentGroupProps {
    group: AssignmentGroupDef;
    groupId: string;
    values: string[];
    onToggle: (value: string) => void;
    onClear: () => void;
    disabled?: boolean;
}

export function AssignmentGroup({ group, groupId, values, onToggle, onClear, disabled }: AssignmentGroupProps) {
    return (
        <div className="flex flex-col gap-1">
            <div className="flex flex-wrap gap-1.5">
                {group.options.map((opt) => {
                    const checked = values.includes(opt.value);
                    return (
                        <label
                            key={opt.value}
                            className={`
                                flex items-center gap-1 px-2 py-0.5 rounded text-xs select-none
                                border transition-colors
                                ${disabled ? 'cursor-default opacity-60' : 'cursor-pointer'}
                                ${checked
                                    ? 'bg-blue-50 border-blue-300 text-blue-800'
                                    : 'bg-white border-ws-panel-border text-ws-fg hover:border-blue-200'}
                            `}
                        >
                            <input
                                type="checkbox"
                                name={`assignment-${groupId}`}
                                checked={checked}
                                onChange={() => !disabled && onToggle(opt.value)}
                                disabled={disabled}
                                className="sr-only"
                            />
                            <span>{opt.emoji ? `${opt.emoji} ${opt.label}` : opt.label}</span>
                        </label>
                    );
                })}
            </div>
            {values.length > 0 && !disabled && (
                <button
                    type="button"
                    onClick={onClear}
                    className="text-[10px] text-ws-muted hover:text-ws-fg self-start"
                >
                    Clear
                </button>
            )}
        </div>
    );
}
