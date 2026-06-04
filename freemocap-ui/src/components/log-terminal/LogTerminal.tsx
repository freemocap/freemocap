import React from 'react';
import {useLogTerminal} from './useLogTerminal';
import {LogToolbar} from './LogToolbar';
import {LogSearchBar} from './LogSearchBar';
import {VirtualLogList} from './VirtualLogList';
import {LogSnapshot, LogRecord} from '@/services/server/server-helpers/log-store';
import {LOG_COLORS} from './constants';

const LogCollapsedView: React.FC<{snapshot: LogSnapshot; filteredLogs: LogRecord[]}> = ({snapshot, filteredLogs}) => {
    const mostRecent = filteredLogs[filteredLogs.length - 1] ?? snapshot.entries[snapshot.entries.length - 1];
    const color = mostRecent
        ? (LOG_COLORS[mostRecent.levelname.toUpperCase()] ?? 'var(--color-text-primary)')
        : 'var(--color-text-secondary)';

    return (
        <div className="flex flex-row items-center gap-1" style={{height: '100%', overflow: 'hidden', backgroundColor: '#1a1a1a', paddingLeft: 8, paddingRight: 8}}>
            <span style={{fontSize: '0.8em', fontWeight: 'bold', color: 'var(--color-text-primary)', flexShrink: 0}}>
                Server Logs
            </span>
            {snapshot.hasErrors && (
                <span className="icon warning-icon icon-size-20" style={{flexShrink: 0}}/>
            )}
            <span style={{fontSize: '0.75em', color, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>
                {mostRecent ? `[${mostRecent.levelname}] ${mostRecent.message}` : 'No logs yet'}
            </span>
        </div>
    );
};

export const LogTerminal: React.FC<{isCollapsed?: boolean}> = ({isCollapsed = false}) => {
    const terminal = useLogTerminal();

    if (isCollapsed) {
        return <LogCollapsedView snapshot={terminal.snapshot} filteredLogs={terminal.filteredLogs}/>;
    }

    return (
        <div className="log-terminal flex flex-col" style={{height: '100%'}}>
            <LogToolbar
                snapshot={terminal.snapshot}
                isPaused={terminal.isPaused}
                copyFeedback={terminal.copyFeedback}
                showSearch={terminal.showSearch}
                showLevelFilters={terminal.showLevelFilters}
                selectedLevels={terminal.selectedLevels}
                onLevelToggle={terminal.handleLevelToggle}
                onPauseToggle={terminal.handlePauseToggle}
                onClear={terminal.handleClear}
                onCopyToClipboard={terminal.handleCopyToClipboard}
                onSaveToDisk={terminal.handleSaveToDisk}
                onScrollToBottom={terminal.scrollToBottom}
                onToggleSearch={() => terminal.setShowSearch((prev) => !prev)}
                onToggleLevelFilters={() => terminal.setShowLevelFilters((prev) => !prev)}
            />

            {terminal.showSearch && (
                <LogSearchBar
                    searchText={terminal.searchText}
                    onSearchChange={terminal.setSearchText}
                />
            )}

            <VirtualLogList
                filteredLogs={terminal.filteredLogs}
                prefixHeights={terminal.prefixHeights}
                totalHeight={terminal.totalHeight}
                startIdx={terminal.startIdx}
                endIdx={terminal.endIdx}
                offsetY={terminal.offsetY}
                isPaused={terminal.isPaused}
                scrollContainerRef={terminal.scrollContainerRef}
                onScroll={terminal.handleScroll}
            />
        </div>
    );
};
