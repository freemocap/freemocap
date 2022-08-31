def determine_shared_charuco_board_views(self):
    pass
    # # determine paired board views
    # for this_cam_num in range(multi_cam.num_cams):
    #     if full_charuco_detected_on_this_frame[this_cam_num]:
    #         for this_other_camera_num in range(multi_cam.num_cams):
    #             if this_other_camera_num != this_cam_num:
    #                 if full_charuco_detected_on_this_frame[this_other_camera_num]:
    #                     each_cameras_shared_board_view_count_array[this_cam_num,
    #                     this_other_camera_num] += 1
    # each_cameras_shared_board_view_count_total = np.sum(
    # each_cameras_shared_board_view_count_array, axis=1)
    # # print(each_cameras_shared_board_view_count)
    #
    # for this_pair_num, this_cam_pair in enumerate(camera_pair_list):
    #     camera_one_id = this_cam_pair[0]
    #     camera_two_id = this_cam_pair[1]
    #
    #     if full_charuco_detected_on_this_frame[camera_one_id] and
    #     full_charuco_detected_on_this_frame[
    #         camera_two_id]:
    #         camera_pair_joint_view_count[this_pair_num] += 1
