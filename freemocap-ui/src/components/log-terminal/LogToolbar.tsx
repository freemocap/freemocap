import React, {memo} from 'react';
import {useTranslation} from 'react-i18next';
import {LogSnapshot} from '@/services/server/server-helpers/log-store';
import {LOG_COLORS} from './constants';

interface Props {
    snapshot: LogSnapshot;
    isPaused: boolean;
    copyFeedback: boolean;
    showSearch: boolean;
    showLevelFilters: boolean;
    selectedLevels: string[];
    onLevelToggle: (e: React.MouseEvent<HTMLElement>, newLevels: string[]) => void;
    onPauseToggle: () => void;
    onClear: () => void;
    onCopyToClipboard: () => Promise<void>;
    onSaveToDisk: () => void;
    onScrollToBottom: () => void;
    onToggleSearch: () => void;
    onToggleLevelFilters: () => void;
}

export const LogToolbar = memo(function LogToolbar({
    snapshot,
    isPaused,
    copyFeedback,
    showSearch,
    showLevelFilters,
    selectedLevels,
    onLevelToggle,
    onPauseToggle,
    onClear,
    onCopyToClipboard,
    onSaveToDisk,
    onScrollToBottom,
    onToggleSearch,
    onToggleLevelFilters,
}: Props) {
    const {t} = useTranslation();

    return (
        <div className="log-toolbar flex flex-row items-center gap-1" style={{flexWrap: 'wrap'}}>
            <span style={{color: 'var(--color-text-primary)', fontSize: '0.9em', fontWeight: 'bold'}}>
                {t('serverLogs')}
            </span>

            {snapshot.hasErrors && (
                <span
                    title={t('errorsDetected')}
                    className="icon warning-icon icon-size-20"
                />
            )}

            {showLevelFilters && (
                <div className="log-level-filter flex flex-row gap-1" style={{flexWrap: 'wrap'}}>
                    {Object.entries(LOG_COLORS).map(([level, color]) => {
                        const count = snapshot.countsByLevel[level] || 0;
                        const isSelected = selectedLevels.includes(level.toLowerCase());
                        return (
                            <button
                                key={level}
                                className={`button sm ${isSelected ? 'primary' : 'secondary'}`}
                                style={{fontSize: '0.75em', color: isSelected ? undefined : color}}
                                onClick={(e) => {
                                    const newLevels = isSelected
                                        ? selectedLevels.filter(l => l !== level.toLowerCase())
                                        : [...selectedLevels, level.toLowerCase()];
                                    onLevelToggle(e as unknown as React.MouseEvent<HTMLElement>, newLevels);
                                }}
                            >
                                {level}
                                {count > 0 && (
                                    <span style={{marginLeft: '4px', fontSize: '0.8em', opacity: 0.7}}>
                                        ({count})
                                    </span>
                                )}
                            </button>
                        );
                    })}
                </div>
            )}

            <div className="log-actions flex flex-row gap-1" style={{marginLeft: 'auto'}}>
                <button
                    title={copyFeedback ? t('copied') : t('copyLogsToClipboard')}
                    className="button icon-button br-1"
                    onClick={onCopyToClipboard}
                >
                    <span className="icon clear-icon icon-size-20"/>
                </button>

                <button
                    title={t('saveLogsToFile')}
                    className="button icon-button br-1"
                    onClick={onSaveToDisk}
                >
                    <span className="icon save-icon icon-size-20"/>
                </button>

                <button
                    title="Scroll to bottom"
                    className="button icon-button br-1"
                    onClick={onScrollToBottom}
                >
                    <span className="icon load-icon icon-size-20"/>
                </button>

                <button
                    className="button icon-button br-1"
                    onClick={onToggleLevelFilters}
                    style={{color: showLevelFilters ? 'var(--color-info)' : undefined}}
                >
                    <span className="icon settings-icon icon-size-20"/>
                </button>

                <button
                    className="button icon-button br-1"
                    onClick={onToggleSearch}
                    style={{color: showSearch ? 'var(--color-info)' : undefined}}
                >
                    <span className="icon search-icon icon-size-20"/>
                </button>

                <button
                    className="button icon-button br-1"
                    onClick={onPauseToggle}
                    style={{color: isPaused ? 'var(--color-warning)' : undefined}}
                >
                    {isPaused
                        ? <span className="icon play-icon icon-size-20"/>
                        : <span className="icon pause-icon icon-size-20"/>}
                </button>

                <button
                    className="button icon-button br-1"
                    onClick={onClear}
                >
                    <span className="icon clear-icon icon-size-20"/>
                </button>
            </div>
        </div>
    );
}, (prev, next) =>
    prev.snapshot.version  === next.snapshot.version &&
    prev.isPaused          === next.isPaused         &&
    prev.copyFeedback      === next.copyFeedback     &&
    prev.showSearch        === next.showSearch       &&
    prev.showLevelFilters  === next.showLevelFilters &&
    prev.selectedLevels    === next.selectedLevels,
);
