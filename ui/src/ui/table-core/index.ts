/**
 * Table Core Module
 *
 * A domain-agnostic table rendering engine.
 *
 * Usage:
 * - Wrappers provide cell() functions that return ReactNodes
 * - Core handles rendering, sorting, resizing, and states
 *
 * Copied from autoart/frontend/src/ui/table-core/ (domain-agnostic subset)
 */

// Core types
export type {
    RowId,
    TableRow,
    TableColumn,
    RowModel,
    RowModelCapabilities,
    SortState,
    SortDirection,
} from './types';

// Feature system
export type { TableFeature, TableCtx } from './features';
export { applyColumnDecorators, applyRowDecorators } from './features';

// Main component
export { UniversalTableCore, type UniversalTableCoreProps } from './UniversalTableCore';

// Adapters
export { makeFlatRowModel, type FlatRecord } from './adapters/FlatRowModelAdapter';
