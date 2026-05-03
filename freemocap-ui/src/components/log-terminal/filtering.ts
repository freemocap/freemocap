import {LogRecord} from '@/services/server/server-helpers/log-store';

export function applyFilters(
    entries: LogRecord[],
    selectedLevels: string[],
    searchText: string,
): LogRecord[] {
    let filtered = entries;

    if (selectedLevels.length > 0) {
        filtered = filtered.filter((log) =>
            selectedLevels.includes(log.levelname.toLowerCase())
        );
    }

    if (searchText) {
        const searchLower = searchText.toLowerCase();
        filtered = filtered.filter((log) =>
            log.message.toLowerCase().includes(searchLower) ||
            log.module.toLowerCase().includes(searchLower) ||
            log.funcName.toLowerCase().includes(searchLower) ||
            log.formatted_message?.toLowerCase().includes(searchLower)
        );
    }

    return filtered;
}
