import React from "react";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
    triangulationConfigUpdated,
    selectMocapTriangulationConfig
} from "@/store/slices/mocap";

import ValueSelector from "@/components/ui-components/ValueSelector"
import SubactionHeader from "../ui-components/SubactionHeader";
import Checkbox from "../ui-components/Checkbox";

const TriangulationSettings:React.FC = () => {
    const dispatch = useAppDispatch();
    const config = useAppSelector(selectMocapTriangulationConfig)

    return (
        <div className = "flex flex-col gap-1">
            <SubactionHeader text = "Triangulation Settings" />

        
        <Checkbox
        label="Use outlier rejection"
        checked={config.use_outlier_rejection}
        onChange={(event) =>
            dispatch(
            triangulationConfigUpdated({
                use_outlier_rejection: event.target.checked,
            })
            )}
    
        />

        <div className = "flex flex-row p-1 items-center justify-content-space-between">
            <span className = "text sm"> Minimum Cameras for Triangulation </span>
            <ValueSelector
                value = {config.minimum_cameras_for_triangulation}
                min = {2}
                max = {100}
                onChange = {(cutoff) =>
                    dispatch(
                        triangulationConfigUpdated({
                            minimum_cameras_for_triangulation: cutoff,
                        })
                    )
                }
            />
        </div>

        <div className = "flex flex-row p-1 items-center justify-content-space-between">
            <span className = "text sm"> Maximum Cameras to Drop </span>
            <ValueSelector
                value = {config.maximum_cameras_to_drop}
                min = {0}
                max = {100}
                onChange = {(cutoff) =>
                    dispatch(
                        triangulationConfigUpdated({
                            maximum_cameras_to_drop: cutoff,
                        })
                    )
                }
            />
        </div>

        <div className = "flex flex-row p-1 items-center justify-content-space-between">
            <span className = "text sm"> Target Reprojection Error </span>
            <ValueSelector
                value = {config.target_reprojection_error}
                min = {0.001}
                max = {1.0}
                step = {0.001}
                onChange = {(target_reprojection_error) =>
                    dispatch(
                        triangulationConfigUpdated({target_reprojection_error})
                    )
                }
            />
        </div>
    </div>  

            
    );

}

export default TriangulationSettings;
