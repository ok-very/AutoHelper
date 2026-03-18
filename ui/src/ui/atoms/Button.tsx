import { clsx } from 'clsx';
import { forwardRef, ButtonHTMLAttributes } from 'react';

export type ButtonColor = 'gray' | 'red' | 'orange' | 'yellow' | 'green' | 'teal' | 'cyan' | 'blue' | 'indigo' | 'violet' | 'pink' | 'rose';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'light' | 'subtle';
    size?: 'xs' | 'sm' | 'md' | 'lg';
    color?: ButtonColor;
    leftSection?: React.ReactNode;
    rightSection?: React.ReactNode;
}

const colorStyles = {
    gray: {
        light: 'bg-slate-100 text-slate-700 hover:bg-slate-200',
        subtle: 'text-slate-600 hover:bg-slate-100',
    },
    red: {
        light: 'bg-red-50 text-red-700 hover:bg-red-100',
        subtle: 'text-red-600 hover:bg-red-50',
    },
    orange: {
        light: 'bg-orange-50 text-orange-700 hover:bg-orange-100',
        subtle: 'text-orange-600 hover:bg-orange-50',
    },
    yellow: {
        light: 'bg-amber-50 text-amber-700 hover:bg-amber-100',
        subtle: 'text-amber-600 hover:bg-amber-50',
    },
    green: {
        light: 'bg-green-50 text-green-700 hover:bg-green-100',
        subtle: 'text-green-600 hover:bg-green-50',
    },
    teal: {
        light: 'bg-teal-50 text-teal-700 hover:bg-teal-100',
        subtle: 'text-teal-600 hover:bg-teal-50',
    },
    cyan: {
        light: 'bg-cyan-50 text-cyan-700 hover:bg-cyan-100',
        subtle: 'text-cyan-600 hover:bg-cyan-50',
    },
    blue: {
        light: 'bg-blue-50 text-blue-700 hover:bg-blue-100',
        subtle: 'text-blue-600 hover:bg-blue-50',
    },
    indigo: {
        light: 'bg-indigo-50 text-indigo-700 hover:bg-indigo-100',
        subtle: 'text-indigo-600 hover:bg-indigo-50',
    },
    violet: {
        light: 'bg-violet-50 text-violet-700 hover:bg-violet-100',
        subtle: 'text-violet-600 hover:bg-violet-50',
    },
    pink: {
        light: 'bg-pink-50 text-pink-700 hover:bg-pink-100',
        subtle: 'text-pink-600 hover:bg-pink-50',
    },
    rose: {
        light: 'bg-rose-50 text-rose-700 hover:bg-rose-100',
        subtle: 'text-rose-600 hover:bg-rose-50',
    },
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
    ({ className, variant = 'primary', size = 'md', color = 'gray', leftSection, rightSection, children, ...props }, ref) => {
        const getVariantClasses = () => {
            if (variant === 'light') return colorStyles[color].light;
            if (variant === 'subtle') return colorStyles[color].subtle;
            return {
                primary: 'bg-ws-accent text-ws-accent-fg hover:opacity-90 focus:ring-ws-accent',
                secondary: 'bg-ws-panel-bg text-ws-fg border border-ws-panel-border hover:bg-ws-bg focus:ring-ws-accent',
                ghost: 'text-ws-text-secondary hover:bg-ws-row-expanded-bg focus:ring-ws-accent',
                danger: 'bg-ws-error text-ws-accent-fg hover:opacity-90 focus:ring-ws-error',
            }[variant] || '';
        };

        return (
            <button
                ref={ref}
                className={clsx(
                    'inline-flex items-center justify-center gap-1.5 font-sans font-medium rounded-lg transition-colors',
                    'focus:outline-none focus:ring-2 focus:ring-offset-2',
                    'disabled:opacity-50 disabled:cursor-not-allowed',
                    getVariantClasses(),
                    {
                        'px-2 py-0.5 text-xs': size === 'xs',
                        'px-2 py-1 text-xs': size === 'sm',
                        'px-3 py-2 text-sm': size === 'md',
                        'px-4 py-2.5 text-base': size === 'lg',
                    },
                    className
                )}
                {...props}
            >
                {leftSection}
                {children}
                {rightSection}
            </button>
        );
    }
);

Button.displayName = 'Button';
