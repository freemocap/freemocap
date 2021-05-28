def reconstruct3D(session, data_nCams_nFrames_nImgPts_XY,data_params):
    n_cams, n_frames, n_trackedPoints = data_params

    #assert numDims == 2, 'Problem with your data! Not enough dimensions'

    dataFlat_nCams_nTotalPoints_XY = data_nCams_nFrames_nImgPts_XY.reshape(n_cams, -1, 2) #reshape data to collapse across 'frames' so it becomes [numCams, numFrames*numPoints, XY]

    data3d_flat = session.cgroup.triangulate(dataFlat_nCams_nTotalPoints_XY, progress=True)
    dataReprojerr_flat = session.cgroup.reprojection_error(data3d_flat, dataFlat_nCams_nTotalPoints_XY, mean=True)

    ##return:
    data_fr_mar_dim = data3d_flat.reshape(n_frames, n_trackedPoints, 3)
    dataReprojErr_fr_mar_err = dataReprojerr_flat.reshape(n_frames, n_trackedPoints)

    return data_fr_mar_dim   
