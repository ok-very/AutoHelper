import { clsx } from 'clsx';
import { forwardRef, HTMLAttributes } from 'react';

interface StackProps extends HTMLAttributes<HTMLDivElement> {
    gap?: 'none' | 'xs' | 'sm' | 'md' | 'lg';
    align?: 'start' | 'center' | 'end' | 'stretch';
}

const gapClasses = {
    none: 'gap-0',
    xs: 'gap-1',
    sm: 'gap-2',
    md: 'gap-4',
    lg: 'gap-6',
};

const alignClasses = {
    start: 'items-start',
    center: 'items-center',
    end: 'items-end',
    stretch: 'items-stretch',
};

export const Stack = forwardRef<HTMLDivElement, StackProps>(
    ({ gap = 'md', align, className, children, ...props }, ref) => {
        return (
            <div
                ref={ref}
                className={clsx(
                    'flex flex-col',
                    gapClasses[gap] ?? gapClasses.md,
                    align && alignClasses[align],
                    className
                )}
                {...props}
            >
                {children}
            </div>
        );
    }
);

Stack.displayName = 'Stack';
