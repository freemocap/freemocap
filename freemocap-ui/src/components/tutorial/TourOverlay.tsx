import React from 'react';
import {useTranslation} from 'react-i18next';
import ButtonSm from '@/components/ui-components/ButtonSm';
import ButtonCard from '@/components/ui-components/ButtonCard';
import IconButton from '@/components/ui-components/IconButton';
import {useTutorial} from './TutorialContext';

// Centered modal for 'branch' and 'info' steps. Reuses the .splash-overlay
// backdrop for visual consistency with WelcomeModal, but uses its own compact
// modal box (the .splash-modal box is fixed to the two-column welcome layout).
// A single choice renders as one primary button (intro/finish); 2+ choices render
// as ButtonCards, matching the welcome screen's direction picker.
export const TourOverlay: React.FC = () => {
    const {t} = useTranslation();
    const {currentStep, choose, skip} = useTutorial();

    if (!currentStep || (currentStep.kind !== 'branch' && currentStep.kind !== 'info')) return null;

    const choices = currentStep.choices ?? [];
    const isSingle = choices.length === 1;

    return (
        <div
            className="splash-overlay reveal fadeIn tour-overlay"
            style={{position: 'fixed', inset: 0, zIndex: 340}}
            onClick={skip}
        >
            <div
                className="tour-modal bg-dark border-1 border-black br-2 flex flex-col p-1 reveal fade"
                style={{width: 460, maxWidth: '90vw'}}
                onClick={(e) => e.stopPropagation()}
            >
                <div className="bg-middark br-1 flex flex-col gap-3 p-3 pos-rel">
                    <IconButton
                        icon="close-icon"
                        onClick={skip}
                        className="pos-abs top-2 right-2 tertiary"
                    />

                    <h1 className="title flex flex-col gap-1">
                        <span className="text-white">{t(currentStep.titleKey)}</span>
                    </h1>

                    <p className="text md text-gray" style={{whiteSpace: 'pre-line'}}>
                        {t(currentStep.textKey)}
                    </p>

                    {isSingle ? (
                        <ButtonSm
                            text={t(choices[0].labelKey)}
                            textColor="text-white"
                            className="primary accent full-width justify-center"
                            onClick={() => choose(choices[0].id)}
                        />
                    ) : (
                        <div className="flex gap-2 mt-2">
                            {choices.map((c) => (
                                <ButtonCard
                                    key={c.id}
                                    text={t(c.labelKey)}
                                    iconClass={`${c.iconClass ?? ''} icon-size-42`}
                                    onClick={() => choose(c.id)}
                                />
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};
