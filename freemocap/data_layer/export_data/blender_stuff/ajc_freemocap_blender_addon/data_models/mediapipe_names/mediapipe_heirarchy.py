# Dictionary containing the empty children for each of the capture empties.
# This will be used to correct the position of the empties (and its children) that are outside the bone length interval defined by x*stdev


MEDIAPIPE_HIERARCHY = {
    # BODY
    # TORSO
    'hips_center': {
        'children': ['right_hip',
                     'left_hip',
                     'trunk_center']
    },
    'trunk_center': {
        'children': ['neck_center']
    },
    'neck_center': {
        'children': ['right_shoulder',
                     'left_shoulder',
                     'head_center']
    },
    'head_center': {
        'children': ['nose',
                     'mouth_right',
                     'mouth_left',
                     'right_eye',
                     'right_eye_inner',
                     'right_eye_outer',
                     'left_eye',
                     'left_eye_inner',
                     'left_eye_outer',
                     'right_ear',
                     'left_ear']
    },
    # LEGS
    # RIGHT LEG
    'right_hip': {
        'children': ['right_knee']
    },
    'right_knee': {
        'children': ['right_ankle']
    },
    'right_ankle': {
        'children': ['right_foot_index',
                     'right_heel']
    },
    # LEFT LEG
    'left_hip': {
        'children': ['left_knee']
    },

    'left_knee': {
        'children': ['left_ankle']
    },

    'left_ankle': {
        'children': ['left_foot_index',
                     'left_heel']},

    # ARMS
    # RIGHT ARM
    'right_shoulder': {
        'children': ['right_elbow']
    },
    'right_elbow': {
        'children': ['right_wrist']
    },
    'right_wrist': {
        'children': ['right_thumb',
                     'right_index',
                     'right_pinky',
                     'right_hand_middle',
                     'right_hand_wrist']
    },
    'right_hand_wrist': {
        'children': ['right_hand_thumb_cmc',
                     'right_hand_index_finger_mcp',
                     'right_hand_middle_finger_mcp',

                     'right_hand_ring_finger_mcp',
                     'right_hand_pinky_mcp']
    },
    'right_hand_thumb_cmc': {
        'children': ['right_hand_thumb_mcp']
    },
    # LEFT ARM
    'left_shoulder': {
        'children': ['left_elbow']
    },

    'left_elbow': {
        'children': ['left_wrist']
    },
    'left_wrist': {
        'children': ['left_thumb',
                     'left_index',
                     'left_pinky',
                     'left_hand_middle',
                     'left_hand_wrist']
    },

    'left_hand_wrist': {
        'children': ['left_hand_thumb_cmc',
                     'left_hand_index_finger_mcp',
                     'left_hand_middle_finger_mcp',
                     'left_hand_ring_finger_mcp',
                     'left_hand_pinky_mcp']
    },

    # HANDS
    # RIGHT HAND
    'right_hand_thumb_mcp': {
        'children': ['right_hand_thumb_ip']
    },
    'right_hand_thumb_ip': {
        'children': ['right_hand_thumb_tip']
    },
    'right_hand_index_finger_mcp': {
        'children': ['right_hand_index_finger_pip']
    },
    'right_hand_index_finger_pip': {
        'children': ['right_hand_index_finger_dip']
    },
    'right_hand_index_finger_dip': {
        'children': ['right_hand_index_finger_tip']
    },
    'left_hand_thumb_cmc': {
        'children': ['left_hand_thumb_mcp']
    },
    'right_hand_middle_finger_mcp': {
        'children': ['right_hand_middle_finger_pip']
    },
    'right_hand_middle_finger_pip': {
        'children': ['right_hand_middle_finger_dip']
    },
    'right_hand_middle_finger_dip': {
        'children': ['right_hand_middle_finger_tip']
    },
    'right_hand_ring_finger_mcp': {
        'children': ['right_hand_ring_finger_pip']
    },
    'right_hand_ring_finger_pip': {
        'children': ['right_hand_ring_finger_dip']
    },
    'left_hand_thumb_mcp': {
        'children': ['left_hand_thumb_ip']
    },
    'right_hand_ring_finger_dip': {
        'children': ['right_hand_ring_finger_tip']
    },
    'left_hand_thumb_ip': {
        'children': ['left_hand_thumb_tip']
    },
    'right_hand_pinky_mcp': {
        'children': ['right_hand_pinky_pip']
    },
    'left_hand_index_finger_mcp': {
        'children': ['left_hand_index_finger_pip']
    },
    'right_hand_pinky_pip': {
        'children': ['right_hand_pinky_dip']
    },
    'right_hand_pinky_dip': {
        'children': ['right_hand_pinky_tip']
    },
    # LEFT HAND
    'left_hand_index_finger_pip': {
        'children': ['left_hand_index_finger_dip']
    },
    'left_hand_index_finger_dip': {
        'children': ['left_hand_index_finger_tip']
    },

    'left_hand_middle_finger_mcp': {
        'children': ['left_hand_middle_finger_pip']
    },

    'left_hand_middle_finger_pip': {
        'children': ['left_hand_middle_finger_dip']
    },

    'left_hand_middle_finger_dip': {
        'children': ['left_hand_middle_finger_tip']
    },

    'left_hand_ring_finger_mcp': {
        'children': ['left_hand_ring_finger_pip']
    },

    'left_hand_ring_finger_pip': {
        'children': ['left_hand_ring_finger_dip']
    },

    'left_hand_ring_finger_dip': {
        'children': ['left_hand_ring_finger_tip']
    },

    'left_hand_pinky_mcp': {
        'children': ['left_hand_pinky_pip']
    },

    'left_hand_pinky_pip': {
        'children': ['left_hand_pinky_dip']
    },

    'left_hand_pinky_dip': {
        'children': ['left_hand_pinky_tip']
    },
}
