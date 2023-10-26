BONES_CONSTRAINTS = {
    "pelvis": [
        {'type': 'COPY_LOCATION',
         'target': 'hips_center'},
        {'type': 'LOCKED_TRACK',
         'target': 'right_hip',
         'track_axis': 'TRACK_NEGATIVE_X',
         'lock_axis': 'LOCK_Z',

         'influence': 1.0}
    ],
    "pelvis.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_hip',
         'track_axis': 'TRACK_Y'}
    ],
    "pelvis.L": [
        {'type': 'DAMPED_TRACK',
         'target': 'left_hip',
         'track_axis': 'TRACK_Y'}
    ],
    "spine": [
        {'type': 'COPY_LOCATION',
         'target': 'hips_center'},
        {'type': 'DAMPED_TRACK',
         'target': 'trunk_center',
         'track_axis': 'TRACK_Y'},
        {'type': 'LIMIT_ROTATION',
         'use_limit_x': True, 'min_x': -45, 'max_x': 68, 'use_limit_y': True, 'min_y': -45,
         'max_y': 45, 'use_limit_z': True, 'min_z': -30, 'max_z': 30, 'owner_space': 'LOCAL'}
    ],
    "spine.001": [
        {'type': 'DAMPED_TRACK',
         'target': 'neck_center',
         'track_axis': 'TRACK_Y'},
        {'type': 'LOCKED_TRACK',
         'target': 'right_shoulder',
         'track_axis': 'TRACK_NEGATIVE_X',
         'lock_axis': 'LOCK_Y',

         'influence': 1.0},
        {'type': 'LIMIT_ROTATION',
         'use_limit_x': True, 'min_x': -45, 'max_x': 22, 'use_limit_y': True, 'min_y': -45,
         'max_y': 45, 'use_limit_z': True, 'min_z': -30, 'max_z': 30, 'owner_space': 'LOCAL'}
    ],
    "neck": [
        {'type': 'DAMPED_TRACK',
         'target': 'head_center',
         'track_axis': 'TRACK_Y'},
        {'type': 'LOCKED_TRACK',
         'target': 'nose',
         'track_axis': 'TRACK_Z',
         'lock_axis': 'LOCK_Y',
         'influence': 1.0},
        {'type': 'LIMIT_ROTATION',
         'use_limit_x': True, 'min_x': -37, 'max_x': 22, 'use_limit_y': True, 'min_y': -45,
         'max_y': 45, 'use_limit_z': True, 'min_z': -30, 'max_z': 30, 'owner_space': 'LOCAL'}
    ],
    "face": [
        {'type': 'DAMPED_TRACK',
         'target': 'nose',
         'track_axis': 'TRACK_Y'}
    ],
    "shoulder.R": [
        {'type': 'COPY_LOCATION',
         'target': 'neck_center'},
        {'type': 'DAMPED_TRACK',
         'target': 'right_shoulder',
         'track_axis': 'TRACK_Y'}
    ],
    "shoulder.L": [
        {'type': 'COPY_LOCATION',
         'target': 'neck_center'},
        {'type': 'DAMPED_TRACK',
         'target': 'left_shoulder',
         'track_axis': 'TRACK_Y'}
    ],
    "upper_arm.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_elbow',
         'track_axis': 'TRACK_Y'},
        {'type': 'LIMIT_ROTATION',
         'use_limit_x': True, 'min_x': -135, 'max_x': 90, 'use_limit_y': True, 'min_y': -98,
         'max_y': 180, 'use_limit_z': True, 'min_z': -97, 'max_z': 91, 'owner_space': 'LOCAL'}
    ],
    "upper_arm.L": [
        {'type': 'DAMPED_TRACK',
         'target': 'left_elbow',
         'track_axis': 'TRACK_Y'},
        {'type': 'LIMIT_ROTATION',
         'use_limit_x': True, 'min_x': -135, 'max_x': 90, 'use_limit_y': True, 'min_y': -180,
         'max_y': 98, 'use_limit_z': True, 'min_z': -91, 'max_z': 97, 'owner_space': 'LOCAL'}
    ],
    "forearm.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_wrist',
         'track_axis': 'TRACK_Y'},
        # {'type':'LOCKED_TRACK',
        # 'target':'right_' + hand_locked_track_target,'track_axis':'TRACK_Z',
        # 'lock_axis':'LOCK_Y',
        # 'influence':1.0},
        {'type': 'LIMIT_ROTATION',
         'use_limit_x': True, 'min_x': -90, 'max_x': 79, 'use_limit_y': True, 'min_y': 0,
         'max_y': 146, 'use_limit_z': True, 'min_z': 0, 'max_z': 0, 'owner_space': 'LOCAL'}
    ],
    "forearm.L": [
        # {'type':'IK',
        # 'target':'left_wrist',
        # 'pole_target':'left_elbow',
        # 'chain_count':2,'pole_angle':-90},
        {'type': 'DAMPED_TRACK',
         'target': 'left_wrist',
         'track_axis': 'TRACK_Y'},
        # {'type':'LOCKED_TRACK',
        # 'target':'left_' + hand_locked_track_target,'track_axis':'TRACK_Z',
        # 'lock_axis':'LOCK_Y',
        # 'influence':1.0},
        {'type': 'LIMIT_ROTATION',
         'use_limit_x': True, 'min_x': -90, 'max_x': 79, 'use_limit_y': True, 'min_y': -146,
         'max_y': 0, 'use_limit_z': True, 'min_z': 0, 'max_z': 0, 'owner_space': 'LOCAL'}
    ],
    # "hand.R": [
    #     {'type': 'DAMPED_TRACK',
    #     'target': 'right_' + hand_damped_track_target, 'track_axis': 'TRACK_Y'},
    #     {'type': 'LOCKED_TRACK',
    #     'target': 'right_' + hand_locked_track_target, 'track_axis': 'TRACK_Z',

    #      'lock_axis': 'LOCK_Y',
    #      'influence': 1.0},
    #     {'type': 'LIMIT_ROTATION',
    #     'use_limit_x': True, 'min_x': -45, 'max_x': 45, 'use_limit_y': True, 'min_y': -36,
    #      'max_y': 25, 'use_limit_z': True, 'min_z': -86, 'max_z': 90, 'owner_space': 'LOCAL'}
    #      ],
    # "hand.L": [
    #     {'type': 'DAMPED_TRACK',
    #     'target': 'left_' + hand_damped_track_target, 'track_axis': 'TRACK_Y'},
    #     {'type': 'LOCKED_TRACK',
    #     'target': 'left_' + hand_locked_track_target, 'track_axis': 'TRACK_Z',

    #      'lock_axis': 'LOCK_Y',
    #      'influence': 1.0},
    #     {'type': 'LIMIT_ROTATION',
    #     'use_limit_x': True, 'min_x': -45, 'max_x': 45, 'use_limit_y': True, 'min_y': -25,
    #      'max_y': 36, 'use_limit_z': True, 'min_z': -90, 'max_z': 86, 'owner_space': 'LOCAL'}
    #      ],
    "hand.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_index',
         'track_axis': 'TRACK_Y'},
        {'type': 'LOCKED_TRACK',
         'target': 'right_index',
         'track_axis': 'TRACK_Z',

         'lock_axis': 'LOCK_Y',
         'influence': 1.0},
        {'type': 'LIMIT_ROTATION',
         'use_limit_x': True, 'min_x': -45, 'max_x': 45, 'use_limit_y': True, 'min_y': -36,
         'max_y': 25, 'use_limit_z': True, 'min_z': -86, 'max_z': 90, 'owner_space': 'LOCAL'}
    ],
    "hand.L": [
        {'type': 'DAMPED_TRACK',
         'target': 'left_index',
         'track_axis': 'TRACK_Y'},
        {'type': 'LOCKED_TRACK',
         'target': 'left_index',
         'track_axis': 'TRACK_Z',

         'lock_axis': 'LOCK_Y',
         'influence': 1.0},
        {'type': 'LIMIT_ROTATION',
         'use_limit_x': True, 'min_x': -45, 'max_x': 45, 'use_limit_y': True, 'min_y': -25,
         'max_y': 36, 'use_limit_z': True, 'min_z': -90, 'max_z': 86, 'owner_space': 'LOCAL'}
    ],

    "thigh.R": [
        {'type': 'COPY_LOCATION',
         'target': 'right_hip'},
        {'type': 'DAMPED_TRACK',
         'target': 'right_knee',
         'track_axis': 'TRACK_Y'},
        {'type': 'LIMIT_ROTATION',
         'use_limit_x': True, 'min_x': -155, 'max_x': 45, 'use_limit_y': True, 'min_y': -105,
         'max_y': 85, 'use_limit_z': True, 'min_z': -88, 'max_z': 17, 'owner_space': 'LOCAL'}
    ],
    "thigh.L": [
        {'type': 'COPY_LOCATION',
         'target': 'left_hip'},
        {'type': 'DAMPED_TRACK',
         'target': 'left_knee',
         'track_axis': 'TRACK_Y'},
        {'type': 'LIMIT_ROTATION',
         'use_limit_x': True, 'min_x': -155, 'max_x': 45, 'use_limit_y': True, 'min_y': -85,
         'max_y': 105, 'use_limit_z': True, 'min_z': -17, 'max_z': 88, 'owner_space': 'LOCAL'}
    ],
    "shin.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_ankle',
         'track_axis': 'TRACK_Y'},
        {'type': 'LIMIT_ROTATION',
         'use_limit_x': True, 'min_x': 0, 'max_x': 150, 'use_limit_y': True, 'min_y': 0,
         'max_y': 0, 'use_limit_z': True, 'min_z': 0, 'max_z': 0, 'owner_space': 'LOCAL'}
    ],
    "shin.L": [
        {'type': 'DAMPED_TRACK',
         'target': 'left_ankle',
         'track_axis': 'TRACK_Y'},
        {'type': 'LIMIT_ROTATION',
         'use_limit_x': True, 'min_x': 0, 'max_x': 150, 'use_limit_y': True, 'min_y': 0,
         'max_y': 0, 'use_limit_z': True, 'min_z': 0, 'max_z': 0, 'owner_space': 'LOCAL'}
    ],
    "foot.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_foot_index',
         'track_axis': 'TRACK_Y'},
        {'type': 'LIMIT_ROTATION',
         'use_limit_x': True, 'min_x': -31, 'max_x': 63, 'use_limit_y': True, 'min_y': -26,
         'max_y': 26, 'use_limit_z': True, 'min_z': -15, 'max_z': 74, 'owner_space': 'LOCAL'}
    ],
    "foot.L": [
        {'type': 'DAMPED_TRACK',
         'target': 'left_foot_index',
         'track_axis': 'TRACK_Y'},
        {'type': 'LIMIT_ROTATION',
         'use_limit_x': True, 'min_x': -31, 'max_x': 63, 'use_limit_y': True, 'min_y': -26,
         'max_y': 26, 'use_limit_z': True, 'min_z': -74, 'max_z': 15, 'owner_space': 'LOCAL'}
    ],
    "heel.02.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_heel',
         'track_axis': 'TRACK_Y'}
    ],
    "heel.02.L": [
        {'type': 'DAMPED_TRACK',
         'target': 'left_heel',
         'track_axis': 'TRACK_Y'}
    ],
    "thumb.carpal.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_hand_thumb_cmc',
         'track_axis': 'TRACK_Y'}
    ],
    "thumb.01.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_hand_thumb_mcp',
         'track_axis': 'TRACK_Y'}
    ],
    "thumb.02.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_hand_thumb_ip',
         'track_axis': 'TRACK_Y'}
    ],
    "thumb.03.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_hand_thumb_tip',
         'track_axis': 'TRACK_Y'}
    ],
    "palm.01.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_hand_index_finger_mcp',
         'track_axis': 'TRACK_Y'}
    ],
    "f_index.01.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_hand_index_finger_pip',
         'track_axis': 'TRACK_Y'}
    ],
    "f_index.02.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_hand_index_finger_dip',
         'track_axis': 'TRACK_Y'}
    ],
    "f_index.03.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_hand_index_finger_tip',
         'track_axis': 'TRACK_Y'}
    ],
    "palm.02.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_hand_middle_finger_mcp',
         'track_axis': 'TRACK_Y'}
    ],
    "f_middle.01.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_hand_middle_finger_pip',
         'track_axis': 'TRACK_Y'}
    ],
    "f_middle.02.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_hand_middle_finger_dip',
         'track_axis': 'TRACK_Y'}
    ],
    "f_middle.03.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_hand_middle_finger_tip',
         'track_axis': 'TRACK_Y'}
    ],
    "palm.03.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_hand_ring_finger_mcp',
         'track_axis': 'TRACK_Y'}
    ],
    "f_ring.01.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_hand_ring_finger_pip',
         'track_axis': 'TRACK_Y'}
    ],
    "f_ring.02.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_hand_ring_finger_dip',
         'track_axis': 'TRACK_Y'}
    ],
    "f_ring.03.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_hand_ring_finger_tip',
         'track_axis': 'TRACK_Y'}
    ],
    "palm.04.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_hand_pinky_mcp',
         'track_axis': 'TRACK_Y'}
    ],
    "f_pinky.01.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_hand_pinky_pip',
         'track_axis': 'TRACK_Y'}
    ],
    "f_pinky.02.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_hand_pinky_dip',
         'track_axis': 'TRACK_Y'}
    ],
    "f_pinky.03.R": [
        {'type': 'DAMPED_TRACK',
         'target': 'right_hand_pinky_tip',
         'track_axis': 'TRACK_Y'}
    ],
    "thumb.carpal.L": [
        {'type': 'DAMPED_TRACK',
         'target': 'left_hand_thumb_cmc',
         'track_axis': 'TRACK_Y'}
    ],
    "thumb.01.L": [
        {'type': 'DAMPED_TRACK',
         'target': 'left_hand_thumb_mcp',
         'track_axis': 'TRACK_Y'}
    ],
    "thumb.02.L": [
        {'type': 'DAMPED_TRACK',
         'target': 'left_hand_thumb_ip',
         'track_axis': 'TRACK_Y'}
    ],
    "thumb.03.L": [
        {'type': 'DAMPED_TRACK',
         'target': 'left_hand_thumb_tip',
         'track_axis': 'TRACK_Y'}
    ],
    "palm.01.L": [
        {'type': 'DAMPED_TRACK',
         'target': 'left_hand_index_finger_mcp',
         'track_axis': 'TRACK_Y'}
    ],
    "f_index.01.L": [
        {'type': 'DAMPED_TRACK',
         'target': 'left_hand_index_finger_pip',
         'track_axis': 'TRACK_Y'}
    ],
    "f_index.02.L": [
        {'type': 'DAMPED_TRACK',
         'target': 'left_hand_index_finger_dip',
         'track_axis': 'TRACK_Y'}
    ],
    "f_index.03.L": [
        {'type': 'DAMPED_TRACK',
         'target': 'left_hand_index_finger_tip',
         'track_axis': 'TRACK_Y'}
    ],
    "palm.02.L": [
        {'type': 'DAMPED_TRACK',
         'target': 'left_hand_middle_finger_mcp',
         'track_axis': 'TRACK_Y'}
    ],
    "f_middle.01.L": [
        {'type': 'DAMPED_TRACK',
         'target': 'left_hand_middle_finger_pip',
         'track_axis': 'TRACK_Y'}
    ],
    "f_middle.02.L": [
        {'type': 'DAMPED_TRACK',
         'target': 'left_hand_middle_finger_dip',
         'track_axis': 'TRACK_Y'}
    ],
    "f_middle.03.L": [
        {'type': 'DAMPED_TRACK',
         'target': 'left_hand_middle_finger_tip',
         'track_axis': 'TRACK_Y'}
    ],
    "palm.03.L": [
        {'type': 'DAMPED_TRACK',
         'target': 'left_hand_ring_finger_mcp',
         'track_axis': 'TRACK_Y'}
    ],
    "f_ring.01.L": [
        {'type': 'DAMPED_TRACK',
         'target': 'left_hand_ring_finger_pip',
         'track_axis': 'TRACK_Y'}
    ],
    "f_ring.02.L": [
        {'type': 'DAMPED_TRACK',
         'target': 'left_hand_ring_finger_dip',
         'track_axis': 'TRACK_Y'}
    ],
    "f_ring.03.L": [
        {'type': 'DAMPED_TRACK',
         'target': 'left_hand_ring_finger_tip',
         'track_axis': 'TRACK_Y'}
    ],
    "palm.04.L": [
        {'type': 'DAMPED_TRACK',
         'target': 'left_hand_pinky_mcp',
         'track_axis': 'TRACK_Y'}
    ],
    "f_pinky.01.L": [
        {'type': 'DAMPED_TRACK',
         'target': 'left_hand_pinky_pip',
         'track_axis': 'TRACK_Y'}
    ],
    "f_pinky.02.L": [
        {'type': 'DAMPED_TRACK',
         'target': 'left_hand_pinky_dip',
         'track_axis': 'TRACK_Y'}
    ],
    "f_pinky.03.L": [
        {'type': 'DAMPED_TRACK',
         'target': 'left_hand_pinky_tip',
         'track_axis': 'TRACK_Y'}
    ],
}
