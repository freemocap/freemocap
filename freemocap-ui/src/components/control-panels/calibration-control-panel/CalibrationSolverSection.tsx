import React from "react";
import {useCalibration} from "@/hooks/useCalibration";
import {CalibrationSolverMethod} from "@/store/slices/calibration";

export const CalibrationSolverSection: React.FC = () => {
    const {config, updateCalibrationConfig, isLoading} = useCalibration();

    return (
        <div className="flex flex-col gap-2">
            <p className="text sm text-gray" style={{fontWeight: 600}}>Solver Settings</p>

            <select
                className="input-field text md"
                value={config.solverMethod}
                onChange={(e) =>
                    updateCalibrationConfig({
                        solverMethod: e.target.value as CalibrationSolverMethod,
                    })
                }
                disabled={isLoading}
                style={{width: '100%'}}
            >
                <option value="anipose">Anipose (legacy)</option>
                <option value="pyceres">Pyceres (bundle adjustment)</option>
            </select>
        </div>
    );
};
