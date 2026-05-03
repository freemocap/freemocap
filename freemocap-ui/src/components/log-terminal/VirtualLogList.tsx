import React from 'react';
import {useTheme} from '@mui/material';
import {useTranslation} from 'react-i18next';
import {LogRecord} from '@/services/server/server-helpers/log-store';
import {LogEntryRow} from './LogEntryRow';

interface Props {
    filteredLogs: LogRecord[];
    prefixHeights: number[];
    totalHeight: number;
    startIdx: number;
    endIdx: number;
    offsetY: number;
    isPaused: boolean;
    scrollContainerRef: React.RefObject<HTMLDivElement | null>;
    onScroll: () => void;
}

export const VirtualLogList: React.FC<Props> = ({
    filteredLogs,
    prefixHeights,
    totalHeight,
    startIdx,
    endIdx,
    offsetY,
    isPaused,
    scrollContainerRef,
    onScroll,
}) => {
    const theme = useTheme();
    const {t} = useTranslation();

    return (
        <div
            ref={scrollContainerRef}
            onScroll={onScroll}
            style={{
                flex: 1,
                overflowY: 'auto',
                overflowX: 'auto',
                position: 'relative',
                scrollbarWidth: 'thin' as React.CSSProperties['scrollbarWidth'],
                scrollbarColor: theme.palette.mode === 'dark'
                    ? 'rgba(255, 255, 255, 0.2) transparent'
                    : 'rgba(0, 0, 0, 0.2) transparent',
            }}
        >
            {filteredLogs.length === 0 ? (
                <div
                    style={{
                        display: 'flex',
                        justifyContent: 'center',
                        alignItems: 'center',
                        height: '100%',
                        color: theme.palette.text.disabled,
                    }}
                >
                    {isPaused ? t('loggingPaused') : t('noLogsToDisplay')}
                </div>
            ) : (
                <div style={{height: totalHeight, position: 'relative'}}>
                    <div style={{position: 'absolute', top: offsetY, left: 0, right: 0}}>
                        {filteredLogs.slice(startIdx, endIdx).map((log, i) => {
                            const rowIdx = startIdx + i;
                            const rowHeight = prefixHeights[rowIdx + 1] - prefixHeights[rowIdx];
                            return (
                                <LogEntryRow
                                    key={`${log.created}-${log.thread}-${rowIdx}`}
                                    log={log}
                                    style={{height: rowHeight}}
                                />
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
};
