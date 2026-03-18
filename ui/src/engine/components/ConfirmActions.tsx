import { Button, Badge } from '@ui/atoms';
import type { Manifest } from '../types/manifest';
import type { ReviewState, SubmissionRecord } from '../types/record';

interface ConfirmActionsProps {
    manifest: Manifest;
    record: SubmissionRecord;
    reviewState: ReviewState;
    onConfirm: () => void;
    onUnconfirm: () => void;
}

function validateConfirmation(
    manifest: Manifest,
    record: SubmissionRecord,
    rs: ReviewState,
): string | null {
    const conf = manifest.confirmation;
    if (!conf) return null;

    // Check reject: uses manifest-declared rejectGroup + rejectValue
    if (conf.rejectGroup && conf.rejectValue) {
        const assignedValues = rs.assignments[conf.rejectGroup] ?? [];
        if (assignedValues.includes(conf.rejectValue)) {
            return null;
        }
    }

    for (const field of conf.requiredFields) {
        const fieldDef = manifest.fields[field];
        if (!fieldDef) continue;

        // Check requiredUnless exceptions
        if (conf.requiredUnless?.[field]) {
            const exceptions = conf.requiredUnless[field];
            const isExempt = Object.entries(exceptions).some(([exField, exValue]) => {
                return (rs.assignments[exField] ?? []).includes(exValue as string);
            });
            if (isExempt) continue;
        }

        if (fieldDef.type === 'assignment' && fieldDef.group) {
            if (!rs.assignments[fieldDef.group]?.length) {
                return `${fieldDef.label} is required`;
            }
        } else if (fieldDef.type === 'image_path') {
            // Check image availability via manifest preview config
            const preview = manifest.preview;
            if (preview?.availabilityField && preview.missingValue) {
                if (!record.fields[field] || record.fields[preview.availabilityField] === preview.missingValue) {
                    return `${fieldDef.label} is required`;
                }
            } else if (!record.fields[field]) {
                return `${fieldDef.label} is required`;
            }
        }
    }

    return null;
}

export function ConfirmActions({ manifest, record, reviewState, onConfirm, onUnconfirm }: ConfirmActionsProps) {
    const error = validateConfirmation(manifest, record, reviewState);

    return (
        <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
                <Button
                    variant="primary"
                    size="sm"
                    color="green"
                    onClick={onConfirm}
                    disabled={!!error || reviewState.confirmed}
                    title={error ?? undefined}
                    className={!error && !reviewState.confirmed ? 'bg-green-600 hover:bg-green-700 text-white' : ''}
                >
                    Save
                </Button>
                <Button
                    variant="secondary"
                    size="sm"
                    onClick={onUnconfirm}
                    disabled={!reviewState.confirmed}
                >
                    Edit
                </Button>
            </div>
            {reviewState.confirmed && (
                <Badge variant="success" size="md">SAVED</Badge>
            )}
            {error && !reviewState.confirmed && (
                <span className="text-[11px] text-ws-error">{error}</span>
            )}
        </div>
    );
}
