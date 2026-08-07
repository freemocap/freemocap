import React from "react";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
    posthocFilterConfigUpdated,
    selectPosthocFilterConfig
} from "@/store/slices/mocap";

import ValueSelector from "@/components/ui-components/ValueSelector"
import SubactionHeader from "../ui-components/SubactionHeader";

const PosthocFilterSettings:React.FC = () => {
    const dispatch = useAppDispatch();
    const config = useAppSelector(selectPosthocFilterConfig)
    const maximumCutoff = Math.max(
        0.1,
        config.sampling_rate/2 - 0.1
    );

    return (
        <div className = "flex flex-col gap-1">
            <SubactionHeader text = "Butterworth Low-Pass Filter" />

            <p className = "text sm text-gray p-1">
                Method: Butterworth low-pass
            </p>

            <div className = "flex flex-row p-1 items-center justify-content-space-between">
                <span className = "text sm"> Sampling Rate </span>
                <ValueSelector
                    value = {config.sampling_rate}
                    min = {1.0}
                    max = {1200.0}
                    step = {1}
                    unit = "Hz"
                    onChange = {(sampling_rate) => {
                        const newMaximumCutoff = Math.max(
                            0.1,
                            sampling_rate/2 - 0.1,
                        );

                        dispatch(
                            posthocFilterConfigUpdated({
                                sampling_rate,
                                cutoff: Math.min(
                                    config.cutoff,
                                    newMaximumCutoff
                                ),
                            }),
                        );
                    }}
                />
            </div>

            <div className = "flex flex-row p-1 items-center justify-content-space-between">
                <span className = "text sm"> Cutoff (Hz)</span>

                <ValueSelector 
                    value = {config.cutoff}
                    min = {0}
                    max = {maximumCutoff}
                    step = {1}
                    unit = "Hz"
                    onChange = {(cutoff) => 
                        dispatch(
                            posthocFilterConfigUpdated({cutoff})
                        )
                    }
                    />
            </div>

            <div className="flex flex-row p-1 items-center justify-content-space-between">
                <span className="text sm">Order</span>

                <ValueSelector
                    value={config.order}
                    min={1}
                    max={100}
                    step={1}
                    unit=""
                    onChange={(order) =>
                        dispatch(
                            posthocFilterConfigUpdated({order}),
                        )
                    }
                />
            </div>
        </div>
    );
};

export default PosthocFilterSettings;