from mediapipe.python.solutions import holistic as mp_holistic

mediapipe_body_connections = [connection for connection in mp_holistic.POSE_CONNECTIONS]

mediapipe_hand_connections = [connection for connection in mp_holistic.HAND_CONNECTIONS]

mediapipe_face_connections = [
    connection for connection in mp_holistic.FACEMESH_TESSELATION
]

mediapipe_body_landmark_names = [
    landmark.name.lower() for landmark in mp_holistic.PoseLandmark
]

mediapipe_hand_landmark_names = [
    landmark.name.lower() for landmark in mp_holistic.HandLandmark
]
