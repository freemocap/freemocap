import React, {createContext, useCallback, useContext, useEffect, useMemo, useReducer, useState} from 'react';
import {loadFromStorage, saveToStorage} from '@/store/persistence';
import {TOURS} from './tours';
import {emitTourEvent} from './telemetry';
import type {Tour, TourStep} from './types';

// ─── Durable completion flag ──────────────────────────────────────────────────
// One-shot flag persisted through the app's storage SSOT (store/persistence.ts,
// 'freemocap:' prefix). Read once at startup to drive the first-run nudge; written
// when a tour is finished or skipped so the app stops nudging.
const STORAGE_KEY = 'tutorial';

interface TutorialPersisted {
    completed: boolean;
}

// ─── Runtime state (transient, per session) ───────────────────────────────────
interface TutorialState {
    status: 'idle' | 'active';
    activeTourId: string | null;
    currentStepId: string | null;
    history: string[]; // outgoing step ids, pushed on every forward move; popped by back()
}

const initialState: TutorialState = {
    status: 'idle',
    activeTourId: null,
    currentStepId: null,
    history: [],
};

type Action =
    | {type: 'START'; tourId: string; stepId: string}
    | {type: 'GOTO'; stepId: string}   // forward move: remember where we came from
    | {type: 'BACK'}                    // pop history
    | {type: 'END'};

function reducer(state: TutorialState, action: Action): TutorialState {
    switch (action.type) {
        case 'START':
            return {status: 'active', activeTourId: action.tourId, currentStepId: action.stepId, history: []};
        case 'GOTO':
            if (state.currentStepId === null) return state;
            return {...state, currentStepId: action.stepId, history: [...state.history, state.currentStepId]};
        case 'BACK': {
            if (state.history.length === 0) return state;
            const history = state.history.slice(0, -1);
            const prev = state.history[state.history.length - 1];
            return {...state, currentStepId: prev, history};
        }
        case 'END':
            return initialState;
        default:
            return state;
    }
}

// Walk the tour's default path (first choice / linear `next`) from the start so
// the pointer bubble can show a stable "Step N of M". Branches off this path fall
// back to history depth (handled in the value computation below).
function computeDefaultPath(tour: Tour): string[] {
    const path: string[] = [];
    const seen = new Set<string>();
    let id: string | undefined = tour.startStepId;
    while (id && !seen.has(id)) {
        seen.add(id);
        path.push(id);
        const step: TourStep | undefined = tour.steps[id];
        if (!step) break;
        const nextId: string | undefined = step.kind === 'pointer' ? step.next : step.choices?.[0]?.next;
        id = nextId || undefined;
    }
    return path;
}

// The ordered sub-steps of a main step's "deeper" sub-tour: follow `deeper` then
// `next` until the chain rejoins the main path (or ends). Used to number sub-steps
// as parent.N (e.g. 2.1, 2.2).
function subChain(tour: Tour, parentId: string, defaultPath: string[]): string[] {
    const onMain = new Set(defaultPath);
    const chain: string[] = [];
    let id: string | undefined = tour.steps[parentId]?.deeper;
    while (id && !onMain.has(id) && !chain.includes(id)) {
        chain.push(id);
        id = tour.steps[id]?.next;
    }
    return chain;
}

interface TutorialContextValue {
    isTourActive: boolean;
    completed: boolean;
    currentStep: TourStep | null;
    stepIndex: number;    // 1-based position on the main path (parent index for sub-steps)
    stepTotal: number;    // main-path length
    stepLabel: string;    // display label: "2 / 7" on the main path, "2.1" in a sub-tour
    canGoBack: boolean;
    canGoDeeper: boolean; // true when the current step has a "deeper" sub-tour
    startTour: (tourId: string) => void;
    next: () => void;
    back: () => void;
    deeper: () => void;
    choose: (choiceId: string) => void;
    skip: () => void;
}

const TutorialContext = createContext<TutorialContextValue | null>(null);

export const TutorialProvider: React.FC<{children: React.ReactNode}> = ({children}) => {
    const [state, dispatch] = useReducer(reducer, initialState);
    const [completed, setCompleted] = useState<boolean>(
        () => loadFromStorage<TutorialPersisted>(STORAGE_KEY, {completed: false}).completed,
    );

    const activeTour = state.activeTourId ? TOURS[state.activeTourId] : null;
    const currentStep = activeTour && state.currentStepId ? activeTour.steps[state.currentStepId] ?? null : null;

    const markCompleted = useCallback(() => {
        saveToStorage<TutorialPersisted>(STORAGE_KEY, {completed: true});
        setCompleted(true);
    }, []);

    const {stepIndex, stepTotal, stepLabel} = useMemo(() => {
        if (!activeTour || !state.currentStepId) return {stepIndex: 0, stepTotal: 0, stepLabel: ''};
        const path = computeDefaultPath(activeTour);
        const total = path.length;
        const onPath = path.indexOf(state.currentStepId);
        if (onPath >= 0) {
            // Main-path step → "N / total".
            return {stepIndex: onPath + 1, stepTotal: total, stepLabel: `${onPath + 1} / ${total}`};
        }
        // Sub-tour step → number it off its parent: "parent.sub" (e.g. "2.1").
        const parentId = activeTour.steps[state.currentStepId]?.parentStepId;
        const parentIndex = parentId ? path.indexOf(parentId) + 1 : state.history.length + 1;
        const chain = parentId ? subChain(activeTour, parentId, path) : [];
        const subIndex = chain.indexOf(state.currentStepId) + 1;
        const label = parentIndex && subIndex ? `${parentIndex}.${subIndex}` : `${parentIndex}`;
        return {stepIndex: parentIndex, stepTotal: total, stepLabel: label};
    }, [activeTour, state.currentStepId, state.history.length]);

    const startTour = useCallback((tourId: string) => {
        const tour = TOURS[tourId];
        if (!tour) throw new Error(`Unknown tour id: ${tourId}`);
        emitTourEvent('tour_started', {tourId});
        dispatch({type: 'START', tourId, stepId: tour.startStepId});
    }, []);

    // Natural end: the user advanced past the last step (a step whose next is empty).
    const completeTour = useCallback(() => {
        emitTourEvent('tour_completed', {tourId: state.activeTourId, stepId: state.currentStepId});
        markCompleted();
        dispatch({type: 'END'});
    }, [state.activeTourId, state.currentStepId, markCompleted]);

    // Move to a step id; an empty/absent id means "past the end" → complete the tour.
    const goto = useCallback((stepId: string | undefined) => {
        if (!stepId) {
            completeTour();
            return;
        }
        dispatch({type: 'GOTO', stepId});
    }, [completeTour]);

    const next = useCallback(() => {
        if (!currentStep) return;
        const nextId = currentStep.kind === 'pointer'
            ? currentStep.next
            : currentStep.choices?.[0]?.next; // default = first choice
        goto(nextId);
    }, [currentStep, goto]);

    const choose = useCallback((choiceId: string) => {
        if (!currentStep) return;
        const choice = currentStep.choices?.find((c) => c.id === choiceId);
        if (!choice) throw new Error(`Unknown choice "${choiceId}" on step "${currentStep.id}"`);
        goto(choice.next);
    }, [currentStep, goto]);

    const back = useCallback(() => dispatch({type: 'BACK'}), []);

    // Detour into the current step's "deeper" sub-tour (its first sub-step).
    const deeper = useCallback(() => {
        if (!currentStep?.deeper) return;
        emitTourEvent('tour_deeper', {tourId: state.activeTourId, stepId: state.currentStepId});
        goto(currentStep.deeper);
    }, [currentStep, goto, state.activeTourId, state.currentStepId]);

    // Early exit: skip button, Esc, or clicking the overlay backdrop. The step id
    // records exactly where the user bailed — the key drop-off signal.
    const skip = useCallback(() => {
        emitTourEvent('tour_skipped', {tourId: state.activeTourId, stepId: state.currentStepId, stepIndex, stepTotal});
        markCompleted();
        dispatch({type: 'END'});
    }, [state.activeTourId, state.currentStepId, stepIndex, stepTotal, markCompleted]);

    // Funnel middle: one event per step entry (forward or back), so drop-off
    // between any two steps is visible. Keyed on step id so it fires once per view.
    useEffect(() => {
        if (!state.activeTourId || !state.currentStepId) return;
        emitTourEvent('tour_step_viewed', {
            tourId: state.activeTourId,
            stepId: state.currentStepId,
            stepIndex,
            stepTotal,
            kind: currentStep?.kind,
        });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [state.activeTourId, state.currentStepId]);

    const value = useMemo<TutorialContextValue>(() => ({
        isTourActive: state.status === 'active',
        completed,
        currentStep,
        stepIndex,
        stepTotal,
        stepLabel,
        canGoBack: state.history.length > 0,
        canGoDeeper: !!currentStep?.deeper,
        startTour,
        next,
        back,
        deeper,
        choose,
        skip,
    }), [state.status, state.history.length, completed, currentStep, stepIndex, stepTotal, stepLabel, startTour, next, back, deeper, choose, skip]);

    return <TutorialContext.Provider value={value}>{children}</TutorialContext.Provider>;
};

export function useTutorial(): TutorialContextValue {
    const ctx = useContext(TutorialContext);
    if (!ctx) throw new Error('useTutorial must be used within a TutorialProvider');
    return ctx;
}
