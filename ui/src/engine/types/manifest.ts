import { z } from 'zod/v4';

// --- Field Schema ---

const FieldTypeSchema = z.enum([
    'string', 'number', 'text', 'boolean', 'badge', 'assignment', 'enum', 'image_path',
]);

const FieldDefSchema = z.object({
    type: FieldTypeSchema,
    label: z.string(),
    /** Show as a column in the list table */
    column: z.boolean().optional(),
    /** Column width hint in px */
    width: z.number().optional(),
    /** Show in the detail panel */
    detail: z.boolean().optional(),
    /** Include in text search */
    searchable: z.boolean().optional(),
    /** User can edit this field */
    editable: z.boolean().optional(),
    /** Read-only display */
    readonly: z.boolean().optional(),
    /** For assignment fields: which assignmentGroup drives this */
    group: z.string().optional(),
    /** For number fields */
    min: z.number().optional(),
    max: z.number().optional(),
    /** For enum fields: allowed values */
    options: z.array(z.string()).optional(),
    /** Detail panel section grouping */
    section: z.string().optional(),
});

// --- Assignment Groups ---

const AssignmentOptionSchema = z.object({
    value: z.string(),
    label: z.string(),
    emoji: z.string().optional(),
    description: z.string().optional(),
});

const AssignmentGroupSchema = z.object({
    label: z.string(),
    options: z.array(AssignmentOptionSchema),
    /** Map keyboard key → option value (or null to clear) */
    shortcutKeys: z.record(z.string(), z.string().nullable()).optional(),
});

// --- Image Pipeline ---

const MetricTierSchema = z.object({
    id: z.string(),
    label: z.string(),
    dpi: z.number(),
    scale: z.number().default(1),
});

const ViabilityRuleSchema = z.object({
    id: z.string(),
    label: z.string(),
    /** Which metric tier to evaluate */
    metric: z.string(),
    /** Minimum inches on the long side */
    minInches: z.number(),
    /** Minimum inches on the short side (optional) */
    minShortInches: z.number().optional(),
});

const ImagePipelineSchema = z.object({
    metricTiers: z.array(MetricTierSchema),
    viabilityRules: z.array(ViabilityRuleSchema).optional(),
    /** Field ID containing pixel width */
    widthField: z.string().default('width'),
    /** Field ID containing pixel height */
    heightField: z.string().default('height'),
    /** Field ID containing file size in bytes */
    fileSizeField: z.string().optional(),
});

// --- Preview Panel Config ---

const BadgeDefSchema = z.object({
    /** Field ID to read the value from. For assignment fields, reads from reviewState. */
    field: z.string(),
    /** Map of field values to badge variants (success, error, warning, info, default) */
    variantMap: z.record(z.string(), z.string()).optional(),
    /** Whether to look up label from an assignment group */
    fromGroup: z.string().optional(),
    /** Transform applied to the raw value for display */
    transform: z.enum(['uppercase', 'capitalize', 'none']).optional(),
});

const PreviewSchema = z.object({
    /** Field ID for the image path */
    imageField: z.string(),
    /** Field ID for the primary label (large text) */
    primaryLabel: z.string(),
    /** Field ID for the secondary label (small text) */
    secondaryLabel: z.string().optional(),
    /** Badge definitions to show in the info bar */
    badges: z.array(BadgeDefSchema).optional(),
    /** Field ID that indicates image availability status (e.g. source_type) */
    availabilityField: z.string().optional(),
    /** Value of availabilityField that means "image missing" */
    missingValue: z.string().optional(),
});

// --- Row Styling ---

const RowStyleRuleSchema = z.object({
    /** CSS class(es) to apply */
    className: z.string(),
    /** Field to check (reads from record.fields or reviewState) */
    field: z.string(),
    /** Condition type */
    condition: z.enum(['equals', 'notEquals', 'truthy', 'falsy']),
    /** Value to compare against (for equals/notEquals) */
    value: z.unknown().optional(),
    /** Priority — higher wins when multiple rules match. Default 0. */
    priority: z.number().default(0),
});

// --- Filters ---

const FilterDefSchema = z.object({
    field: z.string(),
    label: z.string(),
    type: z.enum(['assignment', 'enum', 'boolean']),
    /** For enum filters: explicit option list. If omitted, derived from data. */
    options: z.array(z.string()).optional(),
});

// --- Tallies ---

const TallyDefSchema = z.object({
    label: z.string(),
    /** Simple equality conditions ANDed together */
    countWhere: z.record(z.string(), z.unknown()),
});

// --- Confirmation ---

const ConfirmationSchema = z.object({
    /** Fields that must have a non-null value to confirm */
    requiredFields: z.array(z.string()),
    /** Exceptions: field X is not required when field Y has a specific value */
    requiredUnless: z.record(z.string(), z.record(z.string(), z.string())).optional(),
    /** Assignment group whose value can block confirmation */
    rejectGroup: z.string().optional(),
    /** Value within rejectGroup that means "rejected" */
    rejectValue: z.string().optional(),
});

// --- Output ---

const OutputSchema = z.object({
    basePath: z.string(),
    /** Template using field names in braces */
    structure: z.string(),
    /** Filename template using field names in braces */
    filenameTemplate: z.string(),
    /** Override paths for specific assignment values */
    specialPaths: z.record(z.string(), z.string()).optional(),
});

// --- Data Sources ---

const DataSourcesSchema = z.object({
    records: z.string(),
    reviewState: z.string().optional(),
    /** Allowed base directories for serving images */
    imageBases: z.array(z.string()).optional(),
});

// --- Root Manifest ---

export const ManifestSchema = z.object({
    id: z.string(),
    name: z.string(),
    version: z.number().default(1),

    dataSources: DataSourcesSchema,

    /** Field ID to use as the unique record identifier. Defaults to "id". */
    recordId: z.string().default('id'),

    fields: z.record(z.string(), FieldDefSchema),
    assignmentGroups: z.record(z.string(), AssignmentGroupSchema),

    /** Preview panel configuration */
    preview: PreviewSchema.optional(),

    imagePipeline: ImagePipelineSchema.optional(),

    /** Conditional row styling rules for the list table */
    rowStyles: z.array(RowStyleRuleSchema).optional(),

    filters: z.array(FilterDefSchema).optional(),
    tallies: z.array(TallyDefSchema).optional(),
    confirmation: ConfirmationSchema.optional(),
    output: OutputSchema.optional(),
});

export type Manifest = z.infer<typeof ManifestSchema>;
export type FieldDef = z.infer<typeof FieldDefSchema>;
export type AssignmentGroup = z.infer<typeof AssignmentGroupSchema>;
export type AssignmentOption = z.infer<typeof AssignmentOptionSchema>;
export type MetricTier = z.infer<typeof MetricTierSchema>;
export type ViabilityRule = z.infer<typeof ViabilityRuleSchema>;
export type FilterDef = z.infer<typeof FilterDefSchema>;
export type TallyDef = z.infer<typeof TallyDefSchema>;
export type ImagePipeline = z.infer<typeof ImagePipelineSchema>;
export type PreviewConfig = z.infer<typeof PreviewSchema>;
export type BadgeDef = z.infer<typeof BadgeDefSchema>;
export type RowStyleRule = z.infer<typeof RowStyleRuleSchema>;
