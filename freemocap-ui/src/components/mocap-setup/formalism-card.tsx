import {useEffect, useRef, useState} from 'react';
import {Matrix4} from 'three';
import FloatInput from '@/components/ui-components/FloatInput';
import AnchoredInfo from '@/components/ui-components/AnchoredInfo';
import SegmentedControl from '@/components/ui-components/SegmentedControl';
import {fieldLabels, transformFields, transformFromFields, TransformRepresentation} from './reference-transform';

enum PositionUnit { Millimetres = 'mm', Metres = 'm' }

interface FormalismCardProps {
    title: string;
    help: string;
    representation: TransformRepresentation;
    indices: number[];
    matrix: Matrix4;
    onChange: (matrix: Matrix4) => void;
}

export default function FormalismCard({title, help, representation, indices, matrix, onChange}: FormalismCardProps) {
    const [unit, setUnit] = useState(PositionUnit.Millimetres);
    const isPosition = indices.length === 3 && indices.every(index => index < 3);
    const unitScale = isPosition && unit === PositionUnit.Metres ? 1000 : 1;
    const label = (index: number) => isPosition ? ['X', 'Y', 'Z'][index] + ' ' + unit : fieldLabels(representation)[index];
    const [error, setError] = useState<string | null>(null);
    const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
    useEffect(() => () => {if (timer.current) clearTimeout(timer.current);}, []);
    const values = transformFields(matrix, representation);
    function edit(index: number, text: string): void {
        try {
            if (!text.trim() || !Number.isFinite(Number(text))) throw new Error('Enter a finite number.');
            const candidate = [...values];
            candidate[index] = Number(text) * unitScale;
            if (representation === TransformRepresentation.Quaternion || representation === TransformRepresentation.AxisAngle) {
                const end = representation === TransformRepresentation.Quaternion ? 7 : 6;
                const norm = Math.hypot(...candidate.slice(3, end));
                if (norm < 1e-12) throw new Error('Direction cannot have zero length.');
                for (let i = 3; i < end; i++) candidate[i] /= norm;
            }
            onChange(transformFromFields(candidate, representation));
            setError(null);
        } catch (failure) {
            setError(failure instanceof Error ? failure.message : String(failure));
            if (timer.current) clearTimeout(timer.current);
            timer.current = setTimeout(() => setError(null), 2000);
        }
    }
    return <section className={`formalism-card bg-secondary br-1${error ? ' formalism-rejected' : ''}`} aria-label={title}>
        <div className="flex items-center justify-content-space-between">
            <h4 className="text md text-white">{title}</h4>
            <>{isPosition && <SegmentedControl className="transform-representation position-units" size="sm" value={unit} options={[{label: "mm", value: PositionUnit.Millimetres}, {label: "m", value: PositionUnit.Metres}]} onChange={value => setUnit(value as PositionUnit)}/>}</>
            <AnchoredInfo title={`About ${title}`} text={help}/>
        </div>

        <div className={representation === TransformRepresentation.Matrix ? 'transform-matrix' : 'formalism-fields'} style={{gridTemplateColumns: `repeat(${representation === TransformRepresentation.Matrix ? 4 : indices.length}, minmax(0, 1fr))`}}>
            {indices.map(index => <div className="transform-field" key={index}>
                {representation !== TransformRepresentation.Matrix && <span className="text sm text-gray">{label(index)}</span>}
                <FloatInput label={`${title}: ${label(index)}`} value={String(Number((values[index] / unitScale).toPrecision(12)))}
                    sensitivity={isPosition ? .1 / unitScale : representation === TransformRepresentation.Matrix ? .001 : index < 3 || representation === TransformRepresentation.Euler ? .1 : .001}
                    onChange={text => edit(index, text)}/>
            </div>)}
        </div>
        {error && <div role="alert" className="text sm text-error">Not applied: {error}</div>}
    </section>;
}



