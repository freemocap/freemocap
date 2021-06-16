from freemocap import fmc_anipose
import numpy as np 
# from numba import jit

# @jit(nopython=True)
def reconstruct3D(session, data_nCams_nFrames_nImgPts_XYC, confidenceThreshold = .3):
    
    if session.cgroup is None: #load the calibration settings into the session class if it hasn't been already
        calibrationFile = '{}_calibration.yaml'.format(session.sessionID)
        session.cameraConfigFilePath = session.sessionPath/calibrationFile
        session.cgroup = fmc_anipose.CameraGroup.load(session.cameraConfigFilePath)
    
    
    nCams, nFrames, nImgPts, nDims = data_nCams_nFrames_nImgPts_XYC.shape

    if nDims == 3:
        
        data_nCams_nFrames_nImgPts_X = np.squeeze(data_nCams_nFrames_nImgPts_XYC[:,:,:,0].copy())
        data_nCams_nFrames_nImgPts_Y = np.squeeze(data_nCams_nFrames_nImgPts_XYC[:,:,:,1].copy())
        confidence = np.squeeze(data_nCams_nFrames_nImgPts_XYC[:,:,:,2].copy())

        data_nCams_nFrames_nImgPts_X[confidence < confidenceThreshold] = np.nan #replace low confidence points with 'nan'
        data_nCams_nFrames_nImgPts_Y[confidence < confidenceThreshold] = np.nan
        data_nCams_nFrames_nImgPts_XY =np.stack((data_nCams_nFrames_nImgPts_X, data_nCams_nFrames_nImgPts_Y), axis=3)
        
    if nDims == 2:
        data_nCams_nFrames_nImgPts_XY = data_nCams_nFrames_nImgPts_XYC

    dataFlat_nCams_nTotalPoints_XY = data_nCams_nFrames_nImgPts_XY.reshape(nCams, -1, 2) #reshape data to collapse across 'frames' so it becomes [numCams, numFrames*numPoints, XY]

    data3d_flat = session.cgroup.triangulate(dataFlat_nCams_nTotalPoints_XY, progress=True)
    dataReprojerr_flat = session.cgroup.reprojection_error(data3d_flat, dataFlat_nCams_nTotalPoints_XY, mean=True)

    ##return:
    data_fr_mar_dim = data3d_flat.reshape(nFrames, nImgPts, 3)
    dataReprojErr_fr_mar_err = dataReprojerr_flat.reshape(nFrames, nImgPts)

    return data_fr_mar_dim   
