import { clsx } from 'clsx';
import { forwardRef, HTMLAttributes } from 'react';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
    shadow?: 'none' | 'sm' | 'md' | 'lg';
    padding?: 'none' | 'sm' | 'md' | 'lg';
    radius?: 'none' | 'sm' | 'md' | 'lg';
}

const shadowClasses = {
    none: '',
    sm: 'shadow-sm',
    md: 'shadow',
    lg: 'shadow-lg',
};

const paddingClasses = {
    none: '',
    sm: 'p-2',
    md: 'p-4',
    lg: 'p-6',
};

const radiusClasses = {
    none: '',
    sm: 'rounded',
    md: 'rounded-lg',
    lg: 'rounded-xl',
};

export const Card = forwardRef<HTMLDivElement, CardProps>(
    ({ shadow = 'sm', padding = 'md', radius = 'md', className, children, ...props }, ref) => {
        return (
            <div
                ref={ref}
                className={clsx(
                    'bg-ws-panel-bg border border-ws-panel-border',
                    shadowClasses[shadow],
                    paddingClasses[padding],
                    radiusClasses[radius],
                    className
                )}
                {...props}
            >
                {children}
            </div>
        );
    }
);

Card.displayName = 'Card';
