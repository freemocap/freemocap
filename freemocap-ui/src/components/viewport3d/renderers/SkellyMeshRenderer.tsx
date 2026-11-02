import {useEffect, useRef, useState} from 'react';
import {useFrame, useThree} from '@react-three/fiber';
import {Group, type SkinnedMesh} from 'three';
import {useKeypointsSource, useModelDefinitionsById} from '../KeypointsSourceContext';
import type {ResolvedModelFrame} from '@/services/server/transport/frame-types';
import {prepareModels, preparedModelsMatch, type PreparedModel} from './prepared-models';
import {createSkellyMesh, disposeSkellyMesh, prepareSkellyRows, skellyCompatible, updateSkellyPose,
    type SkellyAsset, type SkellyRows} from './skelly/skelly-binding';

interface BoundMesh {mesh: SkinnedMesh; rows: SkellyRows; frameIndex: number}

/** Optional artwork on the same resolved frames as the generic rigid-body renderer. */
export function SkellyMeshRenderer() {
    const {subscribeToModelFrames, getLatestModelFrames, subscribeToModels} = useKeypointsSource();
    const definitions = useModelDefinitionsById();
    const invalidate = useThree(state => state.invalidate);
    const [asset, setAsset] = useState<SkellyAsset | null>(null);
    const group = useRef<Group>(null);
    const frames = useRef<ResolvedModelFrame[]>([]);
    const layout = useRef<PreparedModel[] | null>(null);
    const bindings = useRef<BoundMesh[]>([]);
    const dirty = useRef(true);
    useEffect(() => {
        let active = true;
        import('./skelly/skelly.json').then(module => {
            if (active) {setAsset(module.default); invalidate();}
        }).catch(error => console.error('Could not load Skelly artwork', error));
        return () => {active = false;};
    }, [invalidate]);
    useEffect(() => {
        frames.current = getLatestModelFrames() ?? [];
        dirty.current = true;
        return subscribeToModelFrames(value => {frames.current = value; dirty.current = true;});
    }, [subscribeToModelFrames, getLatestModelFrames]);
    useEffect(() => subscribeToModels(() => invalidate()), [subscribeToModels, invalidate]);
    useEffect(() => () => {
        for (const {mesh} of bindings.current) {mesh.removeFromParent(); disposeSkellyMesh(mesh);}
        bindings.current = []; layout.current = null;
    }, []);
    useFrame(() => {
        if (!group.current || !asset) return;
        if (!layout.current || !preparedModelsMatch(layout.current, frames.current, definitions.current)) {
            for (const {mesh} of bindings.current) {mesh.removeFromParent(); disposeSkellyMesh(mesh);}
            bindings.current = [];
            layout.current = prepareModels(frames.current, definitions.current);
            for (const model of layout.current) {
                // Other authored models continue to use the generic model layers.
                if (!skellyCompatible(asset, model.definition)) continue;
                const mesh = createSkellyMesh(asset);
                group.current.add(mesh);
                bindings.current.push({mesh, frameIndex: model.frameIndex,
                    rows: prepareSkellyRows(asset, frames.current[model.frameIndex])});
            }
            dirty.current = true;
        }
        if (!dirty.current) return;
        for (const bound of bindings.current) updateSkellyPose(bound.mesh, asset, bound.rows, frames.current[bound.frameIndex]);
        dirty.current = false;
    });
    return <group ref={group}/>;
}
