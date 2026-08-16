// Tutorial step-graph model.
//
// A tour is a directed graph of steps keyed by id. Navigation is data-driven:
// a step declares where it goes next (linear `next`, or a set of `choices` that
// branch). Adding content never touches the engine — a new step is one object in
// a tour's `steps` map, a new branch is one entry in `choices`, a new tour is one
// file plus one line in the registry (tours/index.ts).

// Position of the pointer bubble relative to its anchor. Matches the `pos-*`
// arrow classes in styles/tooltips.css.
export type TourPosition =
    | 'pos-top' | 'pos-top-left' | 'pos-top-right'
    | 'pos-bottom' | 'pos-bottom-left' | 'pos-bottom-right'
    | 'pos-left' | 'pos-right';

// - 'branch': centered overlay with 2+ labelled choices, each routing to a
//   different next step. The first choice is the implicit default.
// - 'pointer': anchors a bubble to a real element (via a data-onboarding
//   selector) and advances linearly through `next`.
// - 'info': centered overlay with exactly one implicit choice. Same renderer as
//   'branch' — used for intro / "you're all set" screens that branches converge on.
export type TourStepKind = 'branch' | 'pointer' | 'info';

// Side effect run when a step is entered, so a step can expand the part of the UI
// it's about (open a panel, expand a row). v1 supports a single action: click a DOM
// element. `unlessVisible` makes it idempotent — skip the click if that selector is
// already on-screen, so re-entering the step doesn't toggle an open panel shut.
export interface TourAction {
    type: 'click';
    target: string;         // CSS selector of the control to click
    unlessVisible?: string; // skip the click if this selector is already visible (for "open")
    onlyIfVisible?: string;  // skip the click unless this selector is visible (for "close")
}

export interface TourChoice {
    id: string;
    labelKey: string;      // i18n key, resolved with t()
    iconClass?: string;    // optional icon class for ButtonCard
    next: string;          // id of the step this choice leads to
}

export interface TourStep {
    id: string;
    kind: TourStepKind;
    titleKey: string;      // i18n key
    textKey: string;       // i18n key
    // Route the controller navigates to before showing this step (HashRouter
    // path). Omitted = stay on the current route.
    route?: string;
    // 'pointer' only: CSS selector of the anchor element, e.g.
    // '[data-onboarding="camera:connect-camera"]'.
    target?: string;
    position?: TourPosition;
    // Nudge the bubble down (+) / up (−) from its anchored position, in px. Handy
    // when a step points at a tall element (e.g. an opened panel) and centering
    // would push the bubble off-screen.
    offsetTop?: number;
    // Optional side effects: onEnter runs when the step is shown (e.g. open the panel
    // it explains); onExit runs when leaving it (e.g. close that panel again). onExit
    // makes cleanup work for every input method, not just mouse click-outside.
    onEnter?: TourAction;
    onExit?: TourAction;
    // Optional "Read the docs →" link shown on the step, for steps that hand off to
    // deeper documentation (e.g. calibration).
    docsUrl?: string;
    // 'branch'/'info' only. For 'info', a single choice acts as the sole button.
    choices?: TourChoice[];
    // 'pointer' only: the next step id. Omitted = this is the last step.
    next?: string;
    // Main-path step only: id of the first step of this step's "deeper" sub-tour.
    // When set, the step shows a Back / Deeper / Next control. The sub-tour is a
    // chain of steps (via `next`) whose last `next` rejoins the main path, so
    // "Deeper" is a detour that returns to the flow.
    deeper?: string;
    // Sub-tour step only: id of the main-path step this belongs to. Used to number
    // sub-steps off the parent (e.g. parent step 2 → sub-steps 2.1, 2.2).
    parentStepId?: string;
}

export interface Tour {
    id: string;
    startStepId: string;
    steps: Record<string, TourStep>;
}
