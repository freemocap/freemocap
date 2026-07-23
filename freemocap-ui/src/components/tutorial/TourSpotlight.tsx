import React from 'react';
import {FloatingOnboarding} from '@/hooks/floatingOnboarding';

// The ring/dim visual. It's a component (not a bare <div>) so it can absorb the
// `__floatingOnboardingUnmount` prop FloatingOnboarding injects via cloneElement,
// keeping it off the DOM node.
const SpotlightRing: React.FC<{__floatingOnboardingUnmount?: () => void}> = () => (
    <div className="tour-spotlight"/>
);

interface TourSpotlightProps {
    target: string;
}

// Dims the app and highlights the current pointer target. Reuses
// FloatingOnboarding purely for positioning — it sizes a fixed box to the target,
// and the box-shadow in .tour-spotlight does the dimming. Purely visual
// (pointer-events: none); it does not trap clicks.
export const TourSpotlight: React.FC<TourSpotlightProps> = ({target}) => (
    <FloatingOnboarding target={target} className="tour-spotlight-layer">
        <SpotlightRing/>
    </FloatingOnboarding>
);
