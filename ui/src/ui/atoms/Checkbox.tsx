import { clsx } from 'clsx';
import { forwardRef, useEffect, useRef, InputHTMLAttributes } from 'react';

interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'onChange'> {
    label?: string;
    description?: string;
    indeterminate?: boolean;
    onChange?: (checked: boolean) => void;
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
    ({ className, label, description, id, indeterminate, onChange, ...props }, ref) => {
        const inputId = id || label?.toLowerCase().replace(/\s+/g, '-');
        const internalRef = useRef<HTMLInputElement>(null);
        const resolvedRef = (ref as React.RefObject<HTMLInputElement>) || internalRef;

        useEffect(() => {
            if (resolvedRef.current) {
                resolvedRef.current.indeterminate = !!indeterminate;
            }
        }, [indeterminate, resolvedRef]);

        const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
            onChange?.(e.target.checked);
        };

        return (
            <div className="flex items-start gap-2">
                <input
                    ref={resolvedRef}
                    type="checkbox"
                    id={inputId}
                    onChange={handleChange}
                    className={clsx(
                        'mt-0.5 h-4 w-4 rounded border-ws-panel-border text-ws-accent',
                        'focus:ring-2 focus:ring-ws-accent focus:ring-offset-1',
                        'disabled:opacity-50 disabled:cursor-not-allowed',
                        className
                    )}
                    {...props}
                />
                {(label || description) && (
                    <div className="flex flex-col">
                        {label && (
                            <label
                                htmlFor={inputId}
                                className="text-sm font-medium text-ws-fg cursor-pointer"
                            >
                                {label}
                            </label>
                        )}
                        {description && (
                            <p className="text-xs text-ws-text-secondary">{description}</p>
                        )}
                    </div>
                )}
            </div>
        );
    }
);

Checkbox.displayName = 'Checkbox';
