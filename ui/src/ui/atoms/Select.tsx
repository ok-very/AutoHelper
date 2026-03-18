import { clsx } from 'clsx';
import { forwardRef } from 'react';

interface SelectOption {
    value: string;
    label: string;
}

interface SelectProps {
    value: string | null;
    onChange: (value: string | null) => void;
    data: SelectOption[];
    placeholder?: string;
    label?: string;
    description?: string;
    disabled?: boolean;
    className?: string;
    id?: string;
    size?: 'sm' | 'md' | 'lg';
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
    ({ className, value, onChange, data, placeholder, label, description, disabled, size = 'md', id, ...props }, ref) => {
        const selectId = id || label?.toLowerCase().replace(/\s+/g, '-');

        return (
            <div className="flex flex-col gap-1">
                {label && (
                    <label
                        htmlFor={selectId}
                        className="text-sm font-medium text-ws-fg"
                    >
                        {label}
                    </label>
                )}
                {description && (
                    <p className="text-xs text-ws-text-secondary">{description}</p>
                )}
                <select
                    ref={ref}
                    id={selectId}
                    value={value || ''}
                    onChange={(e) => onChange(e.target.value || null)}
                    disabled={disabled}
                    className={clsx(
                        'w-full rounded-lg border transition-colors bg-ws-panel-bg font-sans',
                        'focus:outline-none focus:ring-2 focus:ring-ws-accent focus:border-ws-accent',
                        'disabled:bg-ws-bg disabled:text-ws-text-disabled disabled:cursor-not-allowed',
                        'border-ws-panel-border',
                        {
                            'px-2 py-1 text-xs': size === 'sm',
                            'px-3 py-2 text-sm': size === 'md',
                            'px-4 py-2.5 text-base': size === 'lg',
                        },
                        className
                    )}
                    {...props}
                >
                    {placeholder && (
                        <option value="" disabled>
                            {placeholder}
                        </option>
                    )}
                    {data.map((option) => (
                        <option key={option.value} value={option.value}>
                            {option.label}
                        </option>
                    ))}
                </select>
            </div>
        );
    }
);

Select.displayName = 'Select';
