# Modal and anchored-help contract

Window controls are opt-in. Add `ModalWindowControls` directly inside a working dialog when its contents benefit from moving, resizing and maximizing. Mocap processing and the custom-reference editor use these controls.

Do not apply window behavior to welcome screens, small settings dialogs, tutorial flags or informational popovers by default. Preserve their owning components' layout and dismissal behavior.

Use `AnchoredInfo` for contextual help: it reuses `FloatingOnboarding` and `PromptTooltip`, appears beside its trigger on hover and remains open when pinned by clicking. It must not insert space into the containing layout, take focus, dim the application or maximize.

Use `PanelResizeHandles` for window resizing and `react-resizable-panels` for internal adjustable divisions. Mark only a genuinely expanding modal body with `modal-window-body`; footers must not grow to fill spare space.

Browser coverage: `e2e/modal-window.spec.ts` checks opt-in window gestures. `e2e/formalism-cards.spec.ts` checks linked input, units and anchored help with the tooltip stylesheet loaded.
