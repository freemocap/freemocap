import React from 'react';
import {useTranslation} from 'react-i18next';
import ButtonSm from '@/components/ui-components/ButtonSm';
import {useTutorial} from './TutorialContext';

// The tour's navigation row: step label + Back / Deeper / Next, plus a quiet Skip.
// Rendered directly inside the pointer bubble (and the fallback card), so the
// controls sit right where the user is reading. "Deeper" only appears on steps
// that declare a sub-tour; it's a detour that rejoins the main path.
export const TourNav: React.FC = () => {
    const {t} = useTranslation();
    const {currentStep, stepLabel, canGoBack, canGoDeeper, next, back, deeper, skip} = useTutorial();
    const docsUrl = currentStep?.docsUrl;

    return (
        <div className="tour-nav flex flex-col gap-1">
            {docsUrl && (
                <ButtonSm
                    iconClass="learn-icon"
                    text={t('tour.controls.docs')}
                    rightSideIcon="externallink"
                    textColor="text-gray"
                    className="tour-docs-link"
                    onClick={() => window.open(docsUrl, '_blank')}
                />
            )}
            <span className="tour-step-counter text sm text-gray">{stepLabel}</span>
            <div className="tour-nav-buttons flex flex-row items-center gap-1">
                <ButtonSm
                    text={t('tour.controls.back')}
                    buttonType="quaternary"
                    className="flex-1 justify-center"
                    onClick={back}
                    disabled={!canGoBack}
                />
                {canGoDeeper && (
                    <ButtonSm
                        text={t('tour.controls.deeper')}
                        buttonType="secondary"
                        textColor="text-white"
                        className="flex-1 justify-center"
                        onClick={deeper}
                    />
                )}
                <ButtonSm
                    text={t('tour.controls.next')}
                    textColor="text-white"
                    className="primary accent flex-1 justify-center"
                    onClick={next}
                />
            </div>
            <ButtonSm
                text={t('tour.controls.skip')}
                buttonType="tertiary"
                textColor="text-gray"
                className="tour-skip-link"
                onClick={skip}
            />
        </div>
    );
};
