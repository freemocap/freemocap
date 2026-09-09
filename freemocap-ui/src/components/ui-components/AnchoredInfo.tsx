import {type ReactNode, useEffect, useId, useRef, useState} from 'react';
import {FloatingOnboarding} from '@/hooks/floatingOnboarding';
import IconButton from './IconButton';
import PromptTooltip from './PromptTooltip';
import useDraggableTooltips from '@/hooks/useDraggableTooltips';

interface AnchoredInfoProps {
    title: string;
    text: ReactNode;
    imageSrc?: string;
    link?: {label: string; url: string};
}

export default function AnchoredInfo({title, text, imageSrc, link}: AnchoredInfoProps) {
    const id = useId();
    const trigger = useRef<HTMLSpanElement>(null);
    const popupClass = 'anchored-info-' + id.replace(/[^a-zA-Z0-9]/g, '');
    const [hovered, setHovered] = useState(false);
    const [pinned, setPinned] = useState(false);
    useDraggableTooltips(pinned ? '.' + popupClass : null);
    const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
    useEffect(() => () => {if(timer.current) clearTimeout(timer.current);}, []);
    useEffect(() => {
        if (!hovered && !pinned) return;
        const inside = (target: EventTarget | null) => target instanceof Element && (trigger.current?.contains(target) || target.closest('.' + popupClass));
        const move = (event: PointerEvent) => {
            if (inside(event.target)) {if (timer.current) clearTimeout(timer.current); timer.current = null;}
            else if (!timer.current) timer.current = setTimeout(() => {setHovered(false); timer.current = null;}, 180);
        };
        const outside = (event: PointerEvent) => {if (!inside(event.target)) setHovered(false);};
        document.addEventListener('pointermove', move); document.addEventListener('pointerdown', outside);
        return () => {document.removeEventListener('pointermove', move); document.removeEventListener('pointerdown', outside);};
    }, [hovered, pinned, popupClass]);
    const enter = () => {if(timer.current) clearTimeout(timer.current); timer.current = null; setHovered(true);};

    return <span ref={trigger} id={id} className="pos-rel flex" style={{flexShrink: 0}} onMouseEnter={enter}>
        <IconButton icon="explainer-icon" ariaLabel={title} className={`icon-size-25 ${pinned ? 'activated' : ''}`} onClick={() => setPinned(true)}/>
        {(hovered || pinned) && <FloatingOnboarding zIndex={10000} target={`[id="${id}"]`}>
                <PromptTooltip show onClick={() => setPinned(true)} onMouseEnter={enter} title={title} text={text} image={!!imageSrc} imageSrc={imageSrc}
                    position="pos-right" className={popupClass} button={!!link} buttonText={link?.label} onButtonClick={() => {if(link) window.open(link.url, '_blank');}}
                    onClose={() => {setPinned(false); setHovered(false);}}/>
        </FloatingOnboarding>}
    </span>;
}



