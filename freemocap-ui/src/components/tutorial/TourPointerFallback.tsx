import React, {useEffect, useState} from 'react';
import {useTranslation} from 'react-i18next';
import {useTutorial} from './TutorialContext';
import {TourNav} from './TourNav';

// Mirror of FloatingOnboarding's own visibility test: is the anchor present,
// on-screen, and non-zero?
function isTargetVisible(selector: string): boolean {
    const el = document.querySelector(selector) as HTMLElement | null;
    if (!el || !document.body.contains(el)) return false;
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
}

// Safety net for pointer steps: the Back/Next/Skip controls normally live on the
// anchored bubble, but that bubble can't render when its target is hidden
// (collapsed panel, wrong route, not yet mounted). When that happens this renders
// the SAME controls on a prominent centered card so the tour can never soft-lock.
// It stays hidden while the target is visible — the bubble owns the controls then.
export const TourPointerFallback: React.FC = () => {
    const {t} = useTranslation();
    const {currentStep} = useTutorial();
    const [targetHidden, setTargetHidden] = useState(false);
    const target = currentStep?.target;

    useEffect(() => {
        setTargetHidden(false);
        if (!target) return;
        let interval: ReturnType<typeof setInterval> | undefined;
        // Grace period so normal step transitions don't flash the fallback before
        // the target mounts.
        const timeout = setTimeout(() => {
            const check = () => setTargetHidden(!isTargetVisible(target));
            check();
            interval = setInterval(check, 400);
        }, 900);
        return () => {
            clearTimeout(timeout);
            if (interval) clearInterval(interval);
        };
    }, [target]);

    if (!currentStep || currentStep.kind !== 'pointer' || !targetHidden) return null;

    return (
        <div className="tour-pointer-fallback bg-dark border-1 border-solid border-blue br-3 elevated-sharp p-2 flex flex-col gap-2">
            <h3 className="text-white text lg">{t(currentStep.titleKey)}</h3>
            <p className="text-white text md" style={{whiteSpace: 'pre-line'}}>{t(currentStep.textKey)}</p>
            <p className="tour-control-caption text sm text-gray">{t('tour.controls.targetHidden')}</p>
            <TourNav/>
        </div>
    );
};
