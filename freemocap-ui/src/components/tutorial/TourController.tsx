import React, {useEffect, useRef} from 'react';
import {useLocation, useNavigate} from 'react-router-dom';
import {useTranslation} from 'react-i18next';
import {useTutorial} from './TutorialContext';
import type {TourAction} from './types';
import {TourOverlay} from './TourOverlay';
import {TourSpotlight} from './TourSpotlight';
import {TourPointerBubble} from './TourPointerBubble';
import {TourPointerFallback} from './TourPointerFallback';
import '@/styles/tutorial.css';

function isSelectorVisible(selector: string): boolean {
    const el = document.querySelector(selector) as HTMLElement | null;
    if (!el || !document.body.contains(el)) return false;
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
}

// Whether an action's visibility guards allow it to fire right now.
function actionShouldFire(a: TourAction): boolean {
    if (a.unlessVisible && isSelectorVisible(a.unlessVisible)) return false;
    if (a.onlyIfVisible && !isSelectorVisible(a.onlyIfVisible)) return false;
    return true;
}

// Mounted once (inside HashRouter). Reads the active step and renders the right
// chrome for its kind. Owns the two cross-cutting concerns a step shouldn't:
// routing to a step's declared route, and global keyboard shortcuts.
export const TourController: React.FC = () => {
    const {t} = useTranslation();
    const navigate = useNavigate();
    const location = useLocation();
    const {isTourActive, currentStep, next, back, skip} = useTutorial();

    // Navigate to the step's route when it differs from where we are. Guarding on
    // the path difference keeps this from looping on every render.
    useEffect(() => {
        if (!isTourActive || !currentStep?.route) return;
        if (location.pathname !== currentStep.route) navigate(currentStep.route);
    }, [isTourActive, currentStep?.route, location.pathname, navigate]);

    // Per-step side effects. On each step change: run the previous step's onExit
    // (e.g. close the panel it opened), then the current step's onEnter (e.g. open a
    // panel — retried because the target may mount just after a route change). Doing
    // the close here (not via the app's click-outside) makes it work for keyboard nav
    // too. When the tour ends, the last step's onExit still runs.
    const prevExitRef = useRef<TourAction | undefined>(undefined);
    useEffect(() => {
        const runOnce = (a: TourAction | undefined) => {
            if (!a || a.type !== 'click' || !actionShouldFire(a)) return;
            (document.querySelector(a.target) as HTMLElement | null)?.click();
        };

        // Close whatever the previous step opened.
        runOnce(prevExitRef.current);

        if (!isTourActive) {
            prevExitRef.current = undefined;
            return;
        }
        prevExitRef.current = currentStep?.onExit;

        const enter = currentStep?.onEnter;
        if (!enter || enter.type !== 'click') return;
        let cancelled = false;
        let tries = 0;
        const attempt = () => {
            if (cancelled || !actionShouldFire(enter)) return;
            const el = document.querySelector(enter.target) as HTMLElement | null;
            if (el) {
                el.click();
                return;
            }
            if (tries++ < 15) setTimeout(attempt, 100);
        };
        const start = setTimeout(attempt, 60);
        return () => {
            cancelled = true;
            clearTimeout(start);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isTourActive, currentStep?.id]);

    // Esc skips; ←/→ step back/forward during pointer steps (overlays use buttons).
    useEffect(() => {
        if (!isTourActive) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                skip();
                return;
            }
            if (currentStep?.kind === 'pointer') {
                if (e.key === 'ArrowRight') next();
                else if (e.key === 'ArrowLeft') back();
            }
        };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [isTourActive, currentStep, next, back, skip]);

    if (!isTourActive || !currentStep) return null;

    if (currentStep.kind === 'pointer') {
        const target = currentStep.target;
        return (
            <>
                {target && <TourSpotlight target={target}/>}
                {target && (
                    <TourPointerBubble
                        target={target}
                        title={t(currentStep.titleKey)}
                        text={t(currentStep.textKey)}
                        position={currentStep.position ?? 'pos-right'}
                        offsetTop={currentStep.offsetTop}
                    />
                )}
                {/* Safety net: shows the same controls if the target can't be highlighted. */}
                <TourPointerFallback/>
            </>
        );
    }

    // 'branch' | 'info'
    return <TourOverlay/>;
};
