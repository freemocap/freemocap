from mediapipe.python.solutions import holistic as mp_holistic


mediapipe_body_connections = [connection for connection in mp_holistic.POSE_CONNECTIONS]

mediapipe_hand_connections = [connection for connection in mp_holistic.HAND_CONNECTIONS]


mediapipe_face_connections = [connection for connection in mp_holistic.FACEMESH_CONTOURS]

mediapipe_body_landmark_names = [landmark.name.lower() for landmark in mp_holistic.PoseLandmark]
NUMBER_OF_MEDIAPIPE_BODY_MARKERS = len(mediapipe_body_landmark_names)

mediapipe_hand_landmark_names = [landmark.name.lower() for landmark in mp_holistic.HandLandmark]


mediapipe_face_landmark_names = [
    "right_eye",
    "left_eye",
    "nose_tip",
    "mouth_center",
    "right_ear_tragion",
    "left_ear_tragion",
]

mediapipe_tracked_point_names_dict = {
    "body": mediapipe_body_landmark_names,
    "right_hand": [f"right_hand_{name}" for name in mediapipe_hand_landmark_names],
    "left_hand": [f"left_hand_{name}" for name in mediapipe_hand_landmark_names],
    "face": mediapipe_face_landmark_names,
}

mediapipe_names_and_connections_dict = {
    "body": {
        "names": mediapipe_body_landmark_names,
        "connections": mediapipe_body_connections,
    },
    "right_hand": {
        "names": [f"right_hand_{name}" for name in mediapipe_hand_landmark_names],
        "connections": mediapipe_hand_connections,
    },
    "left_hand": {
        "names": [f"left_hand_{name}" for name in mediapipe_hand_landmark_names],
        "connections": mediapipe_hand_connections,
    },
    "face": {
        "names": mediapipe_face_landmark_names,
        "connections": mediapipe_face_connections,
    },
}
mediapipe_virtual_marker_definitions_dict = {
    "head_center": {
        "marker_names": ["left_ear", "right_ear"],
        "marker_weights": [0.5, 0.5],
    },
    "neck_center": {
        "marker_names": ["left_shoulder", "right_shoulder"],
        "marker_weights": [0.5, 0.5],
    },
    "trunk_center": {
        "marker_names": ["left_shoulder", "right_shoulder", "left_hip", "right_hip"],
        "marker_weights": [0.25, 0.25, 0.25, 0.25],
    },
    "hips_center": {
        "marker_names": ["left_hip", "right_hip"],
        "marker_weights": [0.5, 0.5],
    },
}
mediapipe_skeleton_schema = {
    "body": {
        "point_names": mediapipe_body_landmark_names,
        "connections": mediapipe_body_connections,
        "virtual_marker_definitions": mediapipe_virtual_marker_definitions_dict,
        "parent": "hips_center",
    },
    "hands": {
        "right": {
            "point_names": [name for name in mediapipe_hand_landmark_names],
            "connections": mediapipe_hand_connections,
            "parent": "right_wrist",
        },
        "left": {
            "point_names": [name for name in mediapipe_hand_landmark_names],
            "connections": mediapipe_hand_connections,
            "parent": "left_wrist",
        },
    },
    "face": {
        "point_names": mediapipe_face_landmark_names,
        "connections": mediapipe_face_connections,
        "parent": "nose",
    },
}

if __name__ == "__main__":
    import pprint

    #
    # print("mediapipe_body_connections:")
    # pprint.pp(mediapipe_tracked_point_names_dict)

    print("=====================================================")
    print("mediapipe_skeleton_schema:")
    pprint.pp(mediapipe_skeleton_schema)
