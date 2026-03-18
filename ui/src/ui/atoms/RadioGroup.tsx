import { clsx } from 'clsx';

interface RadioOption {
    value: string;
    label: string;
    description?: string;
}

interface RadioGroupProps {
    value: string | null;
    onChange: (value: string | null) => void;
    options: RadioOption[];
    name: string;
    label?: string;
    nullable?: boolean;
    className?: string;
}

export function RadioGroup({ value, onChange, options, name, label, nullable = true, className }: RadioGroupProps) {
    return (
        <div className={clsx('flex flex-col gap-1', className)}>
            {label && (
                <span className="text-sm font-medium text-ws-fg mb-1">{label}</span>
            )}
            <div className="flex flex-col gap-1.5">
                {nullable && (
                    <label className="flex items-center gap-2 cursor-pointer">
                        <input
                            type="radio"
                            name={name}
                            value=""
                            checked={value === null || value === ''}
                            onChange={() => onChange(null)}
                            className="w-3.5 h-3.5 text-ws-accent border-ws-panel-border focus:ring-ws-accent focus:ring-2"
                        />
                        <span className="text-xs text-ws-text-secondary">None</span>
                    </label>
                )}
                {options.map((option) => (
                    <label key={option.value} className="flex items-start gap-2 cursor-pointer">
                        <input
                            type="radio"
                            name={name}
                            value={option.value}
                            checked={value === option.value}
                            onChange={(e) => onChange(e.target.value)}
                            className="mt-0.5 w-3.5 h-3.5 text-ws-accent border-ws-panel-border focus:ring-ws-accent focus:ring-2"
                        />
                        <div className="flex flex-col">
                            <span className="text-xs font-medium text-ws-fg">{option.label}</span>
                            {option.description && (
                                <span className="text-[11px] text-ws-text-secondary">{option.description}</span>
                            )}
                        </div>
                    </label>
                ))}
            </div>
        </div>
    );
}
