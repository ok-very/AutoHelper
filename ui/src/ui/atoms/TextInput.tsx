import { clsx } from 'clsx';
import { forwardRef, InputHTMLAttributes } from 'react';

interface TextInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'size'> {
    label?: string;
    error?: string;
    size?: 'sm' | 'md' | 'lg';
}

export const TextInput = forwardRef<HTMLInputElement, TextInputProps>(
    ({ className, label, error, required, size = 'md', id, ...props }, ref) => {
        const inputId = id || label?.toLowerCase().replace(/\s+/g, '-');
        return (
            <div className="flex flex-col gap-1">
                {label && (
                    <label htmlFor={inputId} className="text-sm font-medium text-ws-fg">
                        {label}
                        {required && <span className="text-ws-error ml-0.5">*</span>}
                    </label>
                )}
                <input
                    ref={ref}
                    id={inputId}
                    className={clsx(
                        'w-full rounded-lg border transition-colors font-sans',
                        'focus:outline-none focus:ring-2 focus:ring-ws-accent focus:border-ws-accent',
                        'disabled:bg-ws-bg disabled:text-ws-text-disabled disabled:cursor-not-allowed',
                        error ? 'border-ws-error' : 'border-ws-panel-border',
                        {
                            'px-2 py-1 text-xs': size === 'sm',
                            'px-3 py-2 text-sm': size === 'md',
                            'px-4 py-2.5 text-base': size === 'lg',
                        },
                        className
                    )}
                    {...props}
                />
                {error && <p className="text-xs text-ws-error">{error}</p>}
            </div>
        );
    }
);

TextInput.displayName = 'TextInput';
