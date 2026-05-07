import {LogRecord} from '@/services/server/server-helpers/log-store';
import {LINE_HEIGHT, ROW_PADDING} from './constants';

/** Count lines in a message. A message with no newlines has 1 line. */
export const countLines = (text: string): number => {
    if (!text) return 1;
    let count = 1;
    for (let i = 0; i < text.length; i++) {
        if (text[i] === '\n') count++;
    }
    return count;
};

/** Compute the pixel height of a log entry based on its line count. */
export const getRowHeight = (log: LogRecord): number => {
    // Divider entries get a compact fixed height (short horizontal rule).
    if (log.type === 'divider') {
        return LINE_HEIGHT + 8;
    }
    const lines = countLines(log.message);
    if (lines === 1) {
        return LINE_HEIGHT + ROW_PADDING;
    }
    // Multi-line: header line + all message lines + padding
    return LINE_HEIGHT + lines * LINE_HEIGHT + ROW_PADDING;
};

/**
 * Build a prefix-sum array of cumulative heights for variable-height virtualization.
 * prefixHeights[i] = total height of rows 0..i-1 (the Y offset of row i).
 * prefixHeights[n] = total height of all rows.
 */
export const buildPrefixHeights = (logs: LogRecord[]): number[] => {
    const prefixes = new Array<number>(logs.length + 1);
    prefixes[0] = 0;
    for (let i = 0; i < logs.length; i++) {
        prefixes[i + 1] = prefixes[i] + getRowHeight(logs[i]);
    }
    return prefixes;
};

/** Binary search for the first row whose bottom edge is past the given Y offset. */
export const findStartIndex = (prefixHeights: number[], y: number): number => {
    let lo = 0;
    let hi = prefixHeights.length - 2;
    while (lo < hi) {
        const mid = (lo + hi) >>> 1;
        if (prefixHeights[mid + 1] <= y) {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }
    return lo;
};
