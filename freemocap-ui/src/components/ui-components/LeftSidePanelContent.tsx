import React, { useCallback, useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import { IconButton, List, ListItem, Tooltip, useTheme } from '@mui/material';
import {
    closestCenter,
    DndContext,
    DragEndEvent,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
} from '@dnd-kit/core';
import {
    arrayMove,
    SortableContext,
    sortableKeyboardCoordinates,
    verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { restrictToVerticalAxis, restrictToParentElement } from '@dnd-kit/modifiers';
import ThemeToggle from '@/components/ui-components/ThemeToggle';
import HomeIcon from '@mui/icons-material/Home';
import { useLocation, useNavigate } from 'react-router-dom';
import VideocamIcon from '@mui/icons-material/Videocam';
import DirectionsRunIcon from '@mui/icons-material/DirectionsRun';
import TuneIcon from '@mui/icons-material/Tune';
import { VideoFolderPanel } from '@/components/video-folder-panel/VideoFolderPanel';
import { SortableSectionWrapper } from '@/components/common/SortableSectionWrapper';
import { ServerConnectionStatus } from '@/components/ServerConnectionStatus';
import { ProcessingPipelinePanel } from '@/components/processing-pipeline-panel/ProcessingPipelinePanel';
import { CameraConfigTreeView } from '@/components/camera-config-tree-view/CameraConfigTreeView';
import { CalibrationControlPanel } from '@/components/calibration-control-panel/CalibrationControlPanel';
import { MocapTaskTreeItem } from '@/components/mocap-control-panel/MocapTaskTreeItem';

const STORAGE_KEY = 'freemocap-sidebar-section-order';

const DEFAULT_SECTION_ORDER = [
    'connection',
    'pipeline',
    'cameras',
    'calibration',
    'mocap',
] as const;

type SectionId = (typeof DEFAULT_SECTION_ORDER)[number];

const SECTION_COMPONENTS: Record<SectionId, React.FC> = {
    connection: ServerConnectionStatus,
    pipeline: ProcessingPipelinePanel,
    cameras: CameraConfigTreeView,
    calibration: CalibrationControlPanel,
    mocap: MocapTaskTreeItem,
};

function loadSectionOrder(): SectionId[] {
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (!stored) return [...DEFAULT_SECTION_ORDER];
        const parsed = JSON.parse(stored) as string[];
        const defaultSet = new Set<string>(DEFAULT_SECTION_ORDER);
        const parsedSet = new Set(parsed);
        if (
            parsed.length !== DEFAULT_SECTION_ORDER.length ||
            !parsed.every((id) => defaultSet.has(id)) ||
            !DEFAULT_SECTION_ORDER.every((id) => parsedSet.has(id))
        ) {
            return [...DEFAULT_SECTION_ORDER];
        }
        return parsed as SectionId[];
    } catch {
        return [...DEFAULT_SECTION_ORDER];
    }
}

function saveSectionOrder(order: SectionId[]): void {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(order));
    } catch {
        // Storage full or unavailable — silently ignore
    }
}

const scrollbarStyles = {
    '&::-webkit-scrollbar': {
        width: '6px',
        backgroundColor: 'transparent',
    },
    '&::-webkit-scrollbar-thumb': {
        backgroundColor: (theme: { palette: { mode: string } }) =>
            theme.palette.mode === 'dark'
                ? 'rgba(255, 255, 255, 0.2)'
                : 'rgba(0, 0, 0, 0.2)',
        borderRadius: '3px',
        '&:hover': {
            backgroundColor: (theme: { palette: { mode: string } }) =>
                theme.palette.mode === 'dark'
                    ? 'rgba(255, 255, 255, 0.3)'
                    : 'rgba(0, 0, 0, 0.3)',
        },
    },
    '&::-webkit-scrollbar-track': {
        backgroundColor: 'transparent',
    },
    scrollbarWidth: 'thin',
    scrollbarColor: (theme: { palette: { mode: string } }) =>
        theme.palette.mode === 'dark'
            ? 'rgba(255, 255, 255, 0.2) transparent'
            : 'rgba(0, 0, 0, 0.2) transparent',
};

export const LeftSidePanelContent = () => {
    const theme = useTheme();
    const navigate = useNavigate();
    const location = useLocation();
    const [sectionOrder, setSectionOrder] = useState<SectionId[]>(loadSectionOrder);

    const sensors = useSensors(
        useSensor(PointerSensor, {
            activationConstraint: {
                distance: 5,
            },
        }),
        useSensor(KeyboardSensor, {
            coordinateGetter: sortableKeyboardCoordinates,
        }),
    );

    const handleDragEnd = useCallback((event: DragEndEvent) => {
        const { active, over } = event;
        if (!over || active.id === over.id) return;

        setSectionOrder((prev) => {
            const oldIndex = prev.indexOf(active.id as SectionId);
            const newIndex = prev.indexOf(over.id as SectionId);
            const newOrder = arrayMove(prev, oldIndex, newIndex);
            saveSectionOrder(newOrder);
            return newOrder;
        });
    }, []);

    const modifiers = useMemo(
        () => [restrictToVerticalAxis, restrictToParentElement],
        [],
    );

    return (
        <Box
            sx={{
                width: '100%',
                height: '100%',
                backgroundColor:
                    theme.palette.mode === 'dark'
                        ? theme.palette.background.paper
                        : theme.palette.grey[50],
                color: theme.palette.text.primary,
                display: 'flex',
                flexDirection: 'column',
                overflowY: 'auto',
                overflowX: 'hidden',
                ...scrollbarStyles,
            }}
        >
            {/* Header */}
            <List disablePadding>
                <ListItem
                    sx={{
                        borderBottom:
                            theme.palette.mode === 'dark'
                                ? '1px solid rgba(255,255,255,0.08)'
                                : '1px solid rgba(0,0,0,0.08)',
                        py: 0.75,
                        px: 1.5,
                        minHeight: 40,
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                    }}
                >
                    <Box
                        component="span"
                        sx={{
                            fontSize: 16,
                            fontWeight: 600,
                            color: theme.palette.text.primary,
                        }}
                    >
                        FreeMoCap 💀📸
                    </Box>

                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
                        <IconButton
                            size="small"
                            onClick={() => navigate('/')}
                            sx={{
                                padding: '4px',
                                color:
                                    location.pathname === '/'
                                        ? theme.palette.success.main
                                        : theme.palette.text.secondary,
                            }}
                        >
                            <HomeIcon sx={{ fontSize: 18 }} />
                        </IconButton>
                        <IconButton
                            color="inherit"
                            onClick={() => navigate('/viewport3d')}
                        >
                            <DirectionsRunIcon />
                        </IconButton>

                        <IconButton
                            size="small"
                            onClick={() => navigate('/cameras')}
                            sx={{
                                padding: '4px',
                                color:
                                    location.pathname === '/cameras'
                                        ? theme.palette.success.main
                                        : theme.palette.text.secondary,
                            }}
                        >
                            <VideocamIcon sx={{ fontSize: 18 }} />
                        </IconButton>

                        <Tooltip title="Setup & System Info">
                            <IconButton
                                size="small"
                                onClick={() => navigate('/setup')}
                                sx={{
                                    padding: '4px',
                                    color:
                                        location.pathname === '/setup'
                                            ? theme.palette.success.main
                                            : theme.palette.text.secondary,
                                }}
                            >
                                <TuneIcon sx={{ fontSize: 18 }} />
                            </IconButton>
                        </Tooltip>

                        <ThemeToggle />
                    </Box>
                </ListItem>
            </List>

            {/* Video Panel for Videos Page */}
            {location.pathname === '/videos' && (
                <Box
                    sx={{
                        borderTop: '1px solid',
                        borderColor: theme.palette.divider,
                    }}
                >
                    <VideoFolderPanel />
                </Box>
            )}

            {/* Sidebar Sections — drag-reorderable */}
            <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                modifiers={modifiers}
                onDragEnd={handleDragEnd}
            >
                <SortableContext
                    items={sectionOrder}
                    strategy={verticalListSortingStrategy}
                >
                    <Box
                        sx={{
                            display: 'flex',
                            flexDirection: 'column',
                            gap: 0.75,
                            p: 0.75,
                            pb: 2,
                        }}
                    >
                        {sectionOrder.map((sectionId) => {
                            const Component = SECTION_COMPONENTS[sectionId];
                            return (
                                <SortableSectionWrapper key={sectionId} id={sectionId}>
                                    <Component />
                                </SortableSectionWrapper>
                            );
                        })}
                    </Box>
                </SortableContext>
            </DndContext>
        </Box>
    );
};