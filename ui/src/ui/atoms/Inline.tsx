import { clsx } from 'clsx';
import { forwardRef, HTMLAttributes } from 'react';

interface InlineProps extends HTMLAttributes<HTMLDivElement> {
    gap?: 'none' | 'xs' | 'sm' | 'md' | 'lg';
    justify?: 'start' | 'center' | 'end' | 'between' | 'around';
    align?: 'start' | 'center' | 'end' | 'stretch';
    wrap?: boolean;
}

const gapClasses = {
    none: 'gap-0',
    xs: 'gap-1',
    sm: 'gap-2',
    md: 'gap-4',
    lg: 'gap-6',
};

const justifyClasses = {
    start: 'justify-start',
    center: 'justify-center',
    end: 'justify-end',
    between: 'justify-between',
    around: 'justify-around',
};

const alignClasses = {
    start: 'items-start',
    center: 'items-center',
    end: 'items-end',
    stretch: 'items-stretch',
};

export const Inline = forwardRef<HTMLDivElement, InlineProps>(
    ({ gap = 'md', justify = 'start', align = 'center', wrap = true, className, children, ...props }, ref) => {
        return (
            <div
                ref={ref}
                className={clsx(
                    'flex flex-row',
                    gapClasses[gap],
                    justifyClasses[justify],
                    alignClasses[align],
                    wrap ? 'flex-wrap' : 'flex-nowrap',
                    className
                )}
                {...props}
            >
                {children}
            </div>
        );
    }
);

Inline.displayName = 'Inline';

