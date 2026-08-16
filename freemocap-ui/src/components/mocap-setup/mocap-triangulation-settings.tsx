import React from "react";
import { useAppDispatch, useAppSelector } from "../../store/hooks";
import {
    triangulationConfigUpdated,
    selectMocapTriangulationConfig
} from "../../store/slices/mocap";

import ValueSelector from "../ui-components/ValueSelector";
import ToggleComponent from "../ui-components/ToggleComponent";
import SubactionHeader from "../ui-components/SubactionHeader";
import { useTranslation } from "react-i18next";

const TriangulationSettings: React.FC = () => {
    const { t } = useTranslation();
    const dispatch = useAppDispatch();
    const config = useAppSelector(selectMocapTriangulationConfig);

    return (
        <div className="flex flex-col gap-1">
            <SubactionHeader text={t("triangulation.settings")} />

            <ToggleComponent
                text={t("triangulation.useOutlierRejection")}
                isToggled={config.use_outlier_rejection}
                onToggle={(checked) =>
                    dispatch(
                        triangulationConfigUpdated({
                            use_outlier_rejection: checked,
                        })
                    )
                }
            />

            <div className={`flex flex-row p-1 items-center justify-content-space-between ${config.use_outlier_rejection ? '' : 'disabled'}`}>
                <div className="flex items-center gap-1 flex-wrap">
                    <span className="icon icon-size-20 subcat-icon"></span>
                    <span className="text sm">{t("triangulation.minimumCameras")}</span>
                </div>
                <ValueSelector
                    value={config.minimum_cameras_for_triangulation}
                    min={2}
                    max={100}
                    onChange={(minimum_cameras_for_triangulation) =>
                        dispatch(
                            triangulationConfigUpdated({
                                minimum_cameras_for_triangulation: minimum_cameras_for_triangulation,
                            })
                        )
                    }
                />
            </div>

            <div className={`flex flex-row p-1 items-center justify-content-space-between ${config.use_outlier_rejection ? '' : 'disabled'}`}>
                <div className="flex items-center gap-1 flex-wrap">
                    <span className="icon icon-size-20 subcat-icon"></span>
                    <span className="text sm">{t("triangulation.maximumCamerasToDrop")}</span>
                </div>
                <ValueSelector
                    value={config.maximum_cameras_to_drop}
                    min={0}
                    max={100}
                    onChange={(maximum_cameras_to_drop) =>
                        dispatch(
                            triangulationConfigUpdated({
                                maximum_cameras_to_drop: maximum_cameras_to_drop,
                            })
                        )
                    }
                />
            </div>

            <div className={`flex flex-row p-1 items-center justify-content-space-between ${config.use_outlier_rejection ? '' : 'disabled'}`}>
                <div className="flex items-center gap-1 flex-wrap">
                    <span className="icon icon-size-20 subcat-icon"></span>
                    <span className="text sm">{t("triangulation.targetReprojectionError")}</span>
                </div>
                <ValueSelector
                    value={config.target_reprojection_error}
                    min={0.001}
                    max={1.0}
                    step={0.01}
                    onChange={(target_reprojection_error) =>
                        dispatch(
                            triangulationConfigUpdated({target_reprojection_error})
                        )
                    }
                />
            </div>
        </div>
    );
};

export default TriangulationSettings;
