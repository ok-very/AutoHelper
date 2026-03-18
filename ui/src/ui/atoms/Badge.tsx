import { clsx } from 'clsx';

export interface BadgeProps {
    variant?: 'project' | 'process' | 'phase' | 'subprocess' | 'task' | 'default' | 'warning' | 'light' | 'success' | 'error' | 'neutral' | 'info';
    size?: 'xs' | 'sm' | 'md';
    children: React.ReactNode;
    className?: string;
}

const variantTokens: Record<string, { bg: string; fg: string; border: string }> = {
    project: {
        bg: 'var(--ws-badge-project-bg)',
        fg: 'var(--ws-badge-project-fg)',
        border: 'var(--ws-badge-project-border)',
    },
    process: {
        bg: 'var(--ws-badge-process-bg)',
        fg: 'var(--ws-badge-process-fg)',
        border: 'var(--ws-badge-process-border)',
    },
    phase: {
        bg: 'var(--ws-badge-phase-bg)',
        fg: 'var(--ws-badge-phase-fg)',
        border: 'var(--ws-badge-phase-border)',
    },
    subprocess: {
        bg: 'var(--ws-badge-subprocess-bg)',
        fg: 'var(--ws-badge-subprocess-fg)',
        border: 'var(--ws-badge-subprocess-border)',
    },
    task: {
        bg: 'var(--ws-badge-task-bg)',
        fg: 'var(--ws-badge-task-fg)',
        border: 'var(--ws-badge-task-border)',
    },
    default: {
        bg: 'var(--ws-badge-default-bg)',
        fg: 'var(--ws-badge-default-fg)',
        border: 'var(--ws-badge-default-border)',
    },
    warning: {
        bg: 'var(--ws-badge-warning-bg)',
        fg: 'var(--ws-badge-warning-fg)',
        border: 'var(--ws-badge-warning-border)',
    },
    light: {
        bg: 'var(--ws-badge-light-bg)',
        fg: 'var(--ws-badge-light-fg)',
        border: 'var(--ws-badge-light-border)',
    },
    success: {
        bg: 'var(--ws-badge-success-bg)',
        fg: 'var(--ws-badge-success-fg)',
        border: 'var(--ws-badge-success-border)',
    },
    error: {
        bg: 'var(--ws-badge-error-bg)',
        fg: 'var(--ws-badge-error-fg)',
        border: 'var(--ws-badge-error-border)',
    },
    neutral: {
        bg: 'var(--ws-badge-neutral-bg)',
        fg: 'var(--ws-badge-neutral-fg)',
        border: 'var(--ws-badge-neutral-border)',
    },
    info: {
        bg: 'var(--ws-badge-info-bg)',
        fg: 'var(--ws-badge-info-fg)',
        border: 'var(--ws-badge-info-border)',
    },
};

const sizeStyles = {
    xs: 'px-1 py-0.5 text-[9px]',
    sm: 'px-1.5 py-0.5 text-[10px]',
    md: 'px-2 py-1 text-xs',
};

export function Badge({ variant = 'default', size = 'sm', children, className }: BadgeProps) {
    const hasCustomColors =
        typeof className === 'string' &&
        (className.includes('bg-') || className.includes('text-') || className.includes('border-'));

    const tokens = hasCustomColors ? null : (variantTokens[variant] ?? variantTokens.default);

    return (
        <span
            className={clsx(
                'inline-flex items-center rounded font-bold uppercase tracking-sans border font-sans',
                sizeStyles[size],
                className
            )}
            style={
                tokens
                    ? {
                          backgroundColor: tokens.bg,
                          color: tokens.fg,
                          borderColor: tokens.border,
                      }
                    : undefined
            }
        >
            {children}
        </span>
    );
}
