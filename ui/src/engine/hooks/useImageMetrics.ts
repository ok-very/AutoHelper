import { useMemo } from 'react';
import type { ImagePipeline, MetricTier, ViabilityRule } from '../types/manifest';

export interface ComputedMetric {
    tier: MetricTier;
    widthInches: number;
    heightInches: number;
}

export interface ViabilityResult {
    rule: ViabilityRule;
    passed: boolean;
    maxInches: number;
}

export interface ImageMetricsResult {
    metrics: ComputedMetric[];
    viability: ViabilityResult[];
}

/**
 * Compute image print metrics from pixel dimensions using the manifest's imagePipeline config.
 */
export function useImageMetrics(
    pipeline: ImagePipeline | undefined,
    widthPx: number | undefined,
    heightPx: number | undefined,
): ImageMetricsResult {
    return useMemo(() => {
        if (!pipeline || !widthPx || !heightPx) {
            return { metrics: [], viability: [] };
        }

        const metrics: ComputedMetric[] = pipeline.metricTiers.map((tier) => ({
            tier,
            widthInches: (widthPx * tier.scale) / tier.dpi,
            heightInches: (heightPx * tier.scale) / tier.dpi,
        }));

        const viability: ViabilityResult[] = (pipeline.viabilityRules ?? []).map((rule) => {
            const metric = metrics.find((m) => m.tier.id === rule.metric);
            const longSide = metric
                ? Math.max(metric.widthInches, metric.heightInches)
                : 0;
            const shortSide = metric
                ? Math.min(metric.widthInches, metric.heightInches)
                : 0;
            let passed = longSide >= rule.minInches;
            if (passed && rule.minShortInches != null) {
                passed = shortSide >= rule.minShortInches;
            }
            return {
                rule,
                passed,
                maxInches: longSide,
            };
        });

        return { metrics, viability };
    }, [pipeline, widthPx, heightPx]);
}
