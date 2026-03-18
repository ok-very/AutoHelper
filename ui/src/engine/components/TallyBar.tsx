import type { Manifest } from '../types/manifest';
import type { SubmissionRecord, ReviewState } from '../types/record';

interface TallyBarProps {
    manifest: Manifest;
    records: SubmissionRecord[];
    reviewStates: Record<string, ReviewState>;
    totalCount: number;
}

export function TallyBar({ manifest, records, reviewStates, totalCount }: TallyBarProps) {
    if (!manifest.tallies?.length) return null;

    function countMatching(countWhere: Record<string, unknown>): number {
        return records.filter((rec) => {
            const rs = reviewStates[rec.id];
            if (!rs) return false;

            for (const [key, expected] of Object.entries(countWhere)) {
                if (key === 'confirmed') {
                    if (rs.confirmed !== expected) return false;
                } else {
                    // Check assignments (arrays) then fall back to record fields
                    const assignmentArr = rs.assignments[key];
                    if (assignmentArr !== undefined) {
                        if (!assignmentArr.includes(expected as string)) return false;
                    } else {
                        const actual = rec.fields[key];
                        if (actual !== expected) return false;
                    }
                }
            }
            return true;
        }).length;
    }

    return (
        <div className="flex items-center gap-3 px-3 py-1.5 text-[11px] font-mono border-b border-ws-panel-border bg-ws-bg text-ws-muted">
            <span className="font-medium text-ws-fg">
                {totalCount} records
            </span>
            <span className="text-ws-panel-border">|</span>
            {manifest.tallies.map((tally, i) => (
                <span key={i}>
                    {tally.label}: <strong className="text-ws-fg">{countMatching(tally.countWhere)}</strong>
                </span>
            ))}
        </div>
    );
}
