from freemocap import fmc_anipose
import numpy as np

# from numba import jit

# @jit(nopython=True)
def reconstruct3D(session, data_nCams_nFrames_nImgPts_XYC, confidenceThreshold=0.3):
    """
    Take a specifically formatted data array, and based on the camera calibration yaml, reconstruct a 3D image
    """

    if (
        session.cgroup is None
    ):  # load the calibration settings into the session class if it hasn't been already
        calibrationFile = "{}_calibration.yaml".format(session.sessionID)
        session.cameraConfigFilePath = session.sessionPath / calibrationFile
        session.cgroup = fmc_anipose.CameraGroup.load(session.cameraConfigFilePath)

    nCams, nFrames, nImgPts, nDims = data_nCams_nFrames_nImgPts_XYC.shape

    if nDims == 3:
        dataOG = data_nCams_nFrames_nImgPts_XYC.copy()

        for camNum in range(nCams):
                          
            thisCamX = data_nCams_nFrames_nImgPts_XYC[camNum, :, :,0 ]
            thisCamY = data_nCams_nFrames_nImgPts_XYC[camNum, :, :,1 ]
            thisCamConf = data_nCams_nFrames_nImgPts_XYC[camNum, :, :, 2]

            thisCamX[thisCamConf < confidenceThreshold] = np.nan
            thisCamY[thisCamConf < confidenceThreshold] = np.nan

            if session.debug:
                import matplotlib.pyplot as plt
                fig = plt.figure(8000+camNum)
                fig.suptitle("3d reconstruction Confidence thresholding - cam{}".format(camNum))               
                axOG = fig.add_subplot(1,2,1)
                axOG.imshow(dataOG[0,:,:,0])
                axOG.set_title("Original Data")
                axTh = fig.add_subplot(1,2,2)
                axTh.imshow(thisCamX)
                axTh.set_title("Thresholded Data (there should be NEW and EXCITING gaps :O")
                

                


    if nDims == 2:
        data_nCams_nFrames_nImgPts_XY = data_nCams_nFrames_nImgPts_XYC
    elif nDims == 3:
        data_nCams_nFrames_nImgPts_XY = np.squeeze(data_nCams_nFrames_nImgPts_XYC[:, :, :, 0:2])

    dataFlat_nCams_nTotalPoints_XY = data_nCams_nFrames_nImgPts_XY.reshape(nCams, -1, 2)  # reshape data to collapse across 'frames' so it becomes [numCams, numFrames*numPoints, XY]

    data3d_flat = session.cgroup.triangulate(dataFlat_nCams_nTotalPoints_XY, progress=True)

    dataReprojerr_flat = session.cgroup.reprojection_error( data3d_flat, dataFlat_nCams_nTotalPoints_XY, mean=True)

    ##return:
    data_fr_mar_xyz = data3d_flat.reshape(nFrames, nImgPts, 3)
    dataReprojErr = dataReprojerr_flat.reshape(nFrames, nImgPts)

    return data_fr_mar_xyz, dataReprojErr
