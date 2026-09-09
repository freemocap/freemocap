import {useEffect, useId, useRef, useState} from 'react';
import {FloatingOnboarding} from '@/hooks/floatingOnboarding';
import IconButton from './IconButton';
import PromptTooltip from './PromptTooltip';

interface AnchoredInfoProps {
    title: string;
    text: string;
    imageSrc?: string;
    link?: {label: string; url: string};
}

export default function AnchoredInfo({title, text, imageSrc, link}: AnchoredInfoProps) {
    const id = useId();
    const [hovered, setHovered] = useState(false);
    const [pinned, setPinned] = useState(false);
    const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
    useEffect(() => () => {if(timer.current) clearTimeout(timer.current);}, []);
    const enter = () => {if(timer.current) clearTimeout(timer.current); setHovered(true);};
    const leave = () => {timer.current = setTimeout(() => setHovered(false), 180);};
    return <span id={id} className="pos-rel flex" style={{flexShrink: 0}} onMouseEnter={enter} onMouseLeave={leave}>
        <IconButton icon="explainer-icon" title={title} className={`icon-size-25 ${pinned ? 'activated' : ''}`} onClick={() => setPinned(!pinned)}/>
        {(hovered || pinned) && <FloatingOnboarding target={`[id="${id}"]`}>
                <PromptTooltip show onMouseEnter={enter} onMouseLeave={leave} title={title} text={text} image={!!imageSrc} imageSrc={imageSrc}
                    position="pos-right" button={!!link} buttonText={link?.label} onButtonClick={() => {if(link) window.open(link.url, '_blank');}}
                    onClose={() => {setPinned(false); setHovered(false);}}/>
        </FloatingOnboarding>}
    </span>;
}
