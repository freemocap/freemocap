import React from 'react';
import {Box, useTheme} from '@mui/material';
import {useLogTerminal} from './useLogTerminal';
import {LogToolbar} from './LogToolbar';
import {LogSearchBar} from './LogSearchBar';
import {VirtualLogList} from './VirtualLogList';

export const LogTerminal: React.FC = () => {
    const theme = useTheme();
    const terminal = useLogTerminal();

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
                selectedLevels={terminal.selectedLevels}
                onLevelToggle={terminal.handleLevelToggle}
                onPauseToggle={terminal.handlePauseToggle}
                onClear={terminal.handleClear}
                onCopyToClipboard={terminal.handleCopyToClipboard}
                onSaveToDisk={terminal.handleSaveToDisk}
                onScrollToBottom={terminal.scrollToBottom}
                onToggleSearch={() => terminal.setShowSearch((prev) => !prev)}
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
