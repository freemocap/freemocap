import React from 'react';
import {Box, useTheme} from '@mui/material';
import {Warning as WarningIcon} from '@mui/icons-material';
import {useLogTerminal} from './useLogTerminal';
import {LogToolbar} from './LogToolbar';
import {LogSearchBar} from './LogSearchBar';
import {VirtualLogList} from './VirtualLogList';
import {LogSnapshot, LogRecord} from '@/services/server/server-helpers/log-store';
import {LOG_COLORS} from './constants';

const LogCollapsedView: React.FC<{snapshot: LogSnapshot; filteredLogs: LogRecord[]}> = ({snapshot, filteredLogs}) => {
    const theme = useTheme();
    const mostRecent = filteredLogs[filteredLogs.length - 1] ?? snapshot.entries[snapshot.entries.length - 1];
    const color = mostRecent
        ? (LOG_COLORS[mostRecent.levelname.toUpperCase()] ?? theme.palette.text.primary)
        : theme.palette.text.secondary;

    return (
        <Box sx={{
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            px: 1,
            overflow: 'hidden',
            backgroundColor: theme.palette.mode === 'dark' ? '#1a1a1a' : theme.palette.grey[100],
        }}>
            <span style={{fontSize: '0.8em', fontWeight: 'bold', color: theme.palette.text.primary as string, flexShrink: 0}}>
                Server Logs
            </span>
            {snapshot.hasErrors && (
                <WarningIcon sx={{color: LOG_COLORS.ERROR, fontSize: '1em', flexShrink: 0}}/>
            )}
            <span style={{fontSize: '0.75em', color, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>
                {mostRecent ? `[${mostRecent.levelname}] ${mostRecent.message}` : 'No logs yet'}
            </span>
        </Box>
    );
};

export const LogTerminal: React.FC<{isCollapsed?: boolean}> = ({isCollapsed = false}) => {
    const theme = useTheme();
    const terminal = useLogTerminal();

    if (isCollapsed) {
        return <LogCollapsedView snapshot={terminal.snapshot} filteredLogs={terminal.filteredLogs}/>;
    }

    return (
        <Box
            sx={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                backgroundColor: theme.palette.mode === 'dark' ? '#1a1a1a' : theme.palette.grey[100],
            }}
        >
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
        </Box>
    );
};
