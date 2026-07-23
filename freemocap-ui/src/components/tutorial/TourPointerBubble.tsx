import React from 'react';
import clsx from 'clsx';
import {FloatingOnboarding} from '@/hooks/floatingOnboarding';
import {TourNav} from './TourNav';
import type {TourPosition} from './types';

// The contextual callout for a pointer step. It reuses the exact class recipe
// from PromptTooltip so it inherits the tooltip chrome from styles/tooltips.css:
//   - .prompt-tooltip-container → pointer-events:auto + fixed width
//   - .tooltip-container + .pos-* → the arrow triangle and offset toward the target
// The Back/Next/Skip controls live right here on the bubble (via TourNav) so they
// sit in the user's eyeline next to the target — not pinned to the screen edge.
interface BubbleProps {
    title: string;
    text: string;
    position: TourPosition;
    __floatingOnboardingUnmount?: () => void;
}

const Bubble: React.FC<BubbleProps> = ({title, text, position}) => (
    <div
        className={clsx(
            'prompt-tooltip-container text-wrap border-1 border-solid border-mid-black tooltip-container elevated-sharp',
            position,
            'p-01 br-3 bg-dark',
        )}
    >
        <div className="floating-tooltip-inner gap-2 flex flex-col pos-rel br-2 border-1 border-solid border-blue p-2">
            {title && (
                <div className="tooltip-title-holder flex flex-row pos-rel">
                    <h3 className="text-white text lg mb-2">{title}</h3>
                </div>
            )}
            <div className="tooltip-description-holder flex flex-row pos-rel">
                <p className="text-white text md" style={{whiteSpace: 'pre-line'}}>{text}</p>
            </div>
            <TourNav/>
        </div>
    </div>
);

interface TourPointerBubbleProps {
    target: string;
    title: string;
    text: string;
    position: TourPosition;
    offsetTop?: number;
}

export const TourPointerBubble: React.FC<TourPointerBubbleProps> = ({target, title, text, position, offsetTop}) => (
    <FloatingOnboarding target={target} className="tour-bubble-layer" offsetTop={offsetTop}>
        <Bubble title={title} text={text} position={position}/>
    </FloatingOnboarding>
);
