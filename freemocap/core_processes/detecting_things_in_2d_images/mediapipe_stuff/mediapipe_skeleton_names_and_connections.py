from mediapipe.python.solutions import holistic as mp_holistic

mediapipe_body_connections = [connection for connection in mp_holistic.POSE_CONNECTIONS]

mediapipe_hand_connections = [connection for connection in mp_holistic.HAND_CONNECTIONS]

mediapipe_face_connections = [connection for connection in mp_holistic.FACEMESH_CONTOURS]

mediapipe_body_landmark_names = [landmark.name.lower() for landmark in mp_holistic.PoseLandmark]

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


if __name__ == "__main__":
    import pprint

    pprint.pp(mediapipe_tracked_point_names_dict)
