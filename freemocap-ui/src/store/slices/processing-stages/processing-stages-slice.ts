import {createAsyncThunk, createSelector, createSlice, type PayloadAction} from '@reduxjs/toolkit';
import type {RootState} from '@/store';
import {serverClient, recordingRequest} from '@/services/server/sdk';
import {getDetailedErrorMessage} from '@/store/slices/thunk-helpers';
import {PROCESSING_STAGES, type ResumeStage, type StageSelection} from '@/services/recording/posthoc-processing';

export interface SavedGroup {sensor_group: string; stages: Record<ResumeStage, boolean>}
export interface SavedStageInventory {selected_run_id: number; runs: {run_id: number; groups: SavedGroup[]}[]}
export interface SavedChoice extends SavedGroup {run_id: number}
export type RunSaveMode = 'overwrite' | 'new_run';
export type StageOutcome = 'Run' | 'Rerun' | 'In original run only' | 'Removed after save'
    | 'Not requested' | 'Saved' | 'Reuse saved' | 'Not saved';

export interface StageRow {
    stage: ResumeStage;
    label: string;
    runs: boolean;
    canSelect: boolean;
    outcome: StageOutcome;
}

/** The processing-stage choices for one recording, shared by the list and graph views. */
export interface ProcessingStagesState {
    recordingPath: string | null;
    inventory: SavedStageInventory | null;
    inventoryRequestId: string | null;
    inventoryError: string;
    choiceKey: string;
    start: number | null;
    stop: number;
    saveMode: RunSaveMode;
}

const LAST_STAGE = PROCESSING_STAGES.length - 1;

const initialState: ProcessingStagesState = {
    recordingPath: null,
    inventory: null,
    inventoryRequestId: null,
    inventoryError: '',
    choiceKey: '',
    start: null,
    stop: LAST_STAGE,
    saveMode: 'overwrite',
};

export const choiceKey = (choice: {run_id: number; sensor_group: string}): string =>
    JSON.stringify([choice.run_id, choice.sensor_group]);

const choicesOf = (inventory: SavedStageInventory | null): SavedChoice[] =>
    inventory?.runs.flatMap(run => run.groups.map(group => ({...group, run_id: run.run_id}))) ?? [];

const choiceOf = (inventory: SavedStageInventory | null, key: string): SavedChoice | undefined =>
    choicesOf(inventory).find(item => choiceKey(item) === key);

/** Resume at the first missing stage; later saved results cannot fill an earlier gap. */
const defaultStart = (choice: SavedChoice | undefined): number | null => {
    const missing = PROCESSING_STAGES.findIndex(([stage]) => !choice?.stages[stage]);
    return missing < 0 ? null : missing;
};

export const savedStagesRequested = createAsyncThunk<SavedStageInventory, string, {rejectValue: string}>(
    'processingStages/savedStagesRequested',
    async (path, {signal, rejectWithValue}) => {
        try {
            const response = await serverClient().responses.saved_stages_freemocap_recordings__recording_id__stages_get(
                {...recordingRequest(path), signal});
            if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
            return await response.json() as SavedStageInventory;
        } catch (reason) {
            return rejectWithValue(reason instanceof Error ? reason.message : String(reason));
        }
    },
);

export const processingStagesSlice = createSlice({
    name: 'processingStages',
    initialState,
    reducers: {
        recordingPathCleared: () => initialState,
        choiceSelected: (state, action: PayloadAction<string>) => {
            state.choiceKey = action.payload;
            // A different saved result has different saved stages, so the start resets to its default.
            state.start = defaultStart(choiceOf(state.inventory, action.payload));
            state.stop = LAST_STAGE;
        },
        saveModeSelected: (state, action: PayloadAction<RunSaveMode>) => {
            state.saveMode = action.payload;
        },
        stageToggled: (state, action: PayloadAction<{index: number; checked: boolean}>) => {
            const {index, checked} = action.payload;
            const choice = choiceOf(state.inventory, state.choiceKey);
            if (checked) {
                state.start = state.start === null ? index : Math.min(state.start, index);
                state.stop = LAST_STAGE;
            } else if (index === state.start) {
                // Removing the first selected stage can reuse its saved result.
                const saved = Boolean(choice?.stages[PROCESSING_STAGES[index][0]]);
                state.start = saved && index < state.stop ? index + 1 : null;
            } else {
                state.stop = index - 1;
            }
        },
    },
    extraReducers: builder => {
        builder
            .addCase(savedStagesRequested.pending, (state, action) => {
                state.recordingPath = action.meta.arg;
                state.inventory = null;
                state.inventoryRequestId = action.meta.requestId;
                state.inventoryError = '';
                state.choiceKey = '';
                state.start = null;
                state.stop = LAST_STAGE;
                state.saveMode = 'overwrite';
            })
            .addCase(savedStagesRequested.fulfilled, (state, action) => {
                if (action.meta.requestId !== state.inventoryRequestId) return;
                const inventory = action.payload;
                const run = inventory.runs.find(item => item.run_id === inventory.selected_run_id) ?? inventory.runs[0];
                state.inventory = inventory;
                state.choiceKey = run?.groups[0] ? choiceKey({run_id: run.run_id, sensor_group: run.groups[0].sensor_group}) : '';
                state.start = defaultStart(choiceOf(inventory, state.choiceKey));
                state.stop = LAST_STAGE;
            })
            .addCase(savedStagesRequested.rejected, (state, action) => {
                if (action.meta.requestId !== state.inventoryRequestId || action.meta.aborted) return;
                state.inventoryError = action.payload ?? action.error.message ?? 'Unknown error';
            });
    },
});

export const {recordingPathCleared, choiceSelected, saveModeSelected, stageToggled} = processingStagesSlice.actions;

const selectProcessingStages = (state: RootState): ProcessingStagesState => state.processingStages;

export const selectStageChoices = createSelector(
    [(state: RootState) => state.processingStages.inventory],
    inventory => choicesOf(inventory),
);

export const selectStageChoice = createSelector(
    [selectStageChoices, (state: RootState) => state.processingStages.choiceKey],
    (choices, key) => choices.find(item => choiceKey(item) === key),
);

export const selectSourceRunId = (state: RootState): number => selectStageChoice(state)?.run_id ?? 0;

/** The request fields chosen under Processing stages, or null while no stage is selected. */
export const selectStageSelection = createSelector(
    [selectProcessingStages, selectStageChoice],
    (stages, choice): StageSelection | null => stages.inventory && stages.start !== null ? {
        startStage: PROCESSING_STAGES[stages.start][0],
        stopStage: PROCESSING_STAGES[stages.stop][0],
        baseRunId: choice?.run_id ?? 0,
        runSaveMode: stages.saveMode,
        sensorGroup: choice?.sensor_group,
    } : null,
);

/** What this attempt does to each stage, in processing order. */
export const selectStageRows = createSelector(
    [selectProcessingStages, selectStageChoice],
    (stages, choice): StageRow[] => PROCESSING_STAGES.map(([stage, label], index) => {
        const {start, stop, saveMode} = stages;
        const saved = Boolean(choice?.stages[stage]);
        const runs = start !== null && index >= start && index <= stop;
        const previousSaved = index > 0 && Boolean(choice?.stages[PROCESSING_STAGES[index - 1][0]]);
        const canSelect = runs || index === 0 || previousSaved || (start !== null && index > start);
        const outcome: StageOutcome = runs ? (saved ? 'Rerun' : 'Run')
            : start !== null && index > stop ? (saved ? (saveMode === 'new_run' ? 'In original run only' : 'Removed after save') : 'Not requested')
            : saved ? (start === null ? 'Saved' : 'Reuse saved') : 'Not saved';
        return {stage, label, runs, canSelect, outcome};
    }),
);
