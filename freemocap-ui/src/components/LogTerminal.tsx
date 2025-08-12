import {alpha, Box, Chip, Collapse, ToggleButton, ToggleButtonGroup, useTheme} from "@mui/material";
import {useEffect, useRef, useState} from "react";
import {LogRecord} from "@/store/slices/logRecordsSlice";
import {useAppSelector} from "@/store/AppStateStore";


const LOG_COLORS = {
    "LOOP": "#999",
    "TRACE": "#ccc",
    "DEBUG": "#88ccFF",
    "INFO": "#00E5FF",
    "SUCCESS": "#FF66FF",
    "API": "#66FF66",
    "WARNING": "#FFFF66",
    "ERROR": "#FF6666",
    "CRITICAL": "#FF0000"
} as const;

const LogEntryComponent = ({log}: { log: LogRecord }) => {
    const [expanded, setExpanded] = useState(false);
    const color = LOG_COLORS[log.levelname.toUpperCase() as keyof typeof LOG_COLORS];
    const theme = useTheme();

    const renderWithFormatting = (text: string) => {
        return text.split('\n').map((line, i) => (
            <span key={i}>
                {line.split('\t').map((segment, j) => (
                    <span key={j}>
                        {segment}
                        {j < line.split('\t').length - 1 && <span style={{ marginRight: '2em' }} />}
                    </span>
                ))}
                {i < text.split('\n').length - 1 && <br />}
            </span>
        ));
    };

    return (
        <Box
            sx={{
                mb: 0.5,
                borderLeft: `2px solid ${color}`,
                pl: 1,
                backgroundColor: expanded
                    ? alpha(color, 0.1)
                    : theme.palette.mode === 'dark'
                        ? 'rgba(0,0,0,0.2)'
                        : 'rgba(0,0,0,0.05)',
                cursor: 'pointer',
                transition: 'background-color 0.1s',
                '&:hover': {
                    backgroundColor: alpha(color, theme.palette.mode === 'dark' ? 0.05 : 0.1)
                }
            }}
            onClick={() => setExpanded(!expanded)}
        >
            <Box sx={{display: 'flex', gap: 1, alignItems: 'center', py: 0.5}}>
                <span style={{
                    color: theme.palette.mode === 'dark' ? '#888' : '#555',
                    fontSize: '0.9em'
                }}>
                    {log.asctime}
                </span>
                <Chip size="small" label={log.levelname} sx={{
                    backgroundColor: color,
                    color: '#000',
                    height: 16,
                    fontSize: '0.8em',
                    '.MuiChip-label': {
                        px: 1,
                    }
                }}/>
                <span style={{
                    color: theme.palette.mode === 'dark' ? '#fff' : '#000',
                    flexGrow: 1,
                    fontSize: '0.9em'
                }}>
                    {renderWithFormatting(log.message)}
                </span>
            </Box>

            <Collapse in={expanded}>
                <Box
                    sx={{
                        pl: 2,
                        py: 1,
                        fontSize: '0.8em',
                        color: theme.palette.mode === 'dark' ? '#888' : '#555',
                        borderTop: '1px solid',
                        borderColor: theme.palette.mode === 'dark'
                            ? 'rgba(255,255,255,0.1)'
                            : 'rgba(0,0,0,0.1)'
                    }}
                >
                    <div>Location: {log.module}:{log.funcName}:Line#{log.lineno}</div>
                    <div>File: {log.filename}</div>
                    <div>Time delta: {log.delta_t}</div>
                    <div>Path: {log.pathname}</div>
                    <div>Raw message: {renderWithFormatting(log.formatted_message)}</div>
                    <div>Thread: {log.threadName} (ID: {log.thread})</div>
                    <div>Process: {log.processName} (ID: {log.process})</div>

                    {(log.exc_info || log.exc_text) && (
                        <div>
                            <div>Exception details:</div>
                            {log.exc_info && <div>{renderWithFormatting(log.exc_info)}</div>}
                            {log.exc_text && <div>{renderWithFormatting(log.exc_text)}</div>}
                        </div>
                    )}

                    {log.stack_info && (
                        <div>
                            <div>Stack Trace:</div>
                            <pre style={{
                                whiteSpace: 'pre-wrap',
                                background: theme.palette.mode === 'dark' ? '#111' : '#f5f5f5',
                                padding: 8,
                                borderRadius: 4,
                                margin: '8px 0'
                            }}>
                                {renderWithFormatting(log.stack_info)}
                            </pre>
                        </div>
                    )}
                </Box>
            </Collapse>
        </Box>
    );
};

export const LogTerminal = () => {
    const theme = useTheme();
    const logs = useAppSelector(state => state.logRecords.entries);
    const [selectedLevels, setSelectedLevels] = useState<string[]>([]);
    const logEndRef = useRef<HTMLDivElement>(null);

    const filteredLogs = logs.filter(log =>
        selectedLevels.length === 0 || selectedLevels.includes(log.levelname.toLowerCase())
    );

    useEffect(() => {
        logEndRef.current?.scrollIntoView({behavior: 'instant'});
    }, [filteredLogs]);

    return (
        <Box sx={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            backgroundColor: theme.palette.mode === 'dark'
                ? '#1a1a1a'
                : theme.palette.grey[100]
        }}>
            <Box sx={{
                p: 0.5,
                borderBottom: '1px solid',
                borderColor: theme.palette.divider,
                display: 'flex',
                gap: 1,
                alignItems: 'center'
            }}>
                <span style={{
                    color: theme.palette.text.primary,
                    fontSize: '0.9em'
                }}>
                    Server Logs
                </span>
                <ToggleButtonGroup
                    size="small"
                    value={selectedLevels}
                    onChange={(_, val) => setSelectedLevels(val)}
                    sx={{
                        '.MuiToggleButtonGroup-grouped': {
                            border: `1px solid ${theme.palette.divider} !important`,
                            mx: '1px',
                            '&:not(:first-of-type)': {
                                borderRadius: '2px',
                            },
                            '&:first-of-type': {
                                borderRadius: '2px',
                            },
                        }
                    }}
                >
                    {Object.entries(LOG_COLORS).map(([level, color]) => (
                        <ToggleButton
                            key={level}
                            value={level.toLowerCase()}
                            sx={{
                                py: 0.25,
                                px: 1,
                                minWidth: 0,
                                fontSize: '0.75em',
                                color: alpha(color, 0.7),
                                '&.Mui-selected': {
                                    backgroundColor: alpha(color, 0.15),
                                    color: color,
                                    '&:hover': {
                                        backgroundColor: alpha(color, 0.2),
                                    }
                                },
                                '&:hover': {
                                    backgroundColor: alpha(color, 0.1),
                                }
                            }}
                        >
                            {level}
                        </ToggleButton>
                    ))}
                </ToggleButtonGroup>
            </Box>

            <Box sx={{
                flex: 1,
                overflowY: 'auto',
                p: 1,
                '&::-webkit-scrollbar': {
                    width: '8px',
                    backgroundColor: 'transparent',
                },
                '&::-webkit-scrollbar-thumb': {
                    backgroundColor: theme.palette.mode === 'dark'
                        ? 'rgba(255, 255, 255, 0.2)'
                        : 'rgba(0, 0, 0, 0.2)',
                    borderRadius: '4px',
                    '&:hover': {
                        backgroundColor: theme.palette.mode === 'dark'
                            ? 'rgba(255, 255, 255, 0.3)'
                            : 'rgba(0, 0, 0, 0.3)',
                    },
                },
                '&::-webkit-scrollbar-track': {
                    backgroundColor: 'transparent',
                },
                // For Firefox
                scrollbarWidth: 'thin',
                scrollbarColor: theme.palette.mode === 'dark'
                    ? 'rgba(255, 255, 255, 0.2) transparent'
                    : 'rgba(0, 0, 0, 0.2) transparent',
            }}>
                {filteredLogs.map((log, i) => (
                    <LogEntryComponent key={i} log={log}/>
                ))}
                <div ref={logEndRef}/>
            </Box>
        </Box>
    );
};
