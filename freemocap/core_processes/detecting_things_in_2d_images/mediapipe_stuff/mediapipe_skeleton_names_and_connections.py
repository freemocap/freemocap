from typing import Tuple, Dict, List

from mediapipe.python.solutions import holistic as mp_holistic

mediapipe_body_connections = {connection[0]: connection[1] for connection in mp_holistic.POSE_CONNECTIONS}

mediapipe_hand_connections = {connection[0]: connection[1] for connection in mp_holistic.HAND_CONNECTIONS}

mediapipe_face_contour_connections = {connection[0]: connection[1] for connection in mp_holistic.FACEMESH_CONTOURS}

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


def convert_mediapipe_face_mesh_connections_to_triangles():
    """
    add the unique markers in the triangle to the mesh definition here: https://docs.blender.org/api/blender_python_api_2_76_1/bpy.types.Mesh.html#bpy.types.Mesh.from_pydata

    """
    #doesn't work
    pass

    # # this will preserve the order of the connections, with the first element of the tuple as the key and the second element as the value
    # facemesh_tesseleation = mp_holistic.FACEMESH_TESSELATION
    # facemesh_dict = dict(facemesh_tesseleation)
    #
    # mediapipe_face_mesh_triangles = []
    # triangle = []
    #
    # for connection_number, key in enumerate(facemesh_dict.keys()):
    #     triangle.append(key)
    #     triangle.append(facemesh_dict[key])
    #     if connection_number % 3 == 2:
    #         unique_markers = set(triangle)
    #         mediapipe_face_mesh_triangles.append(unique_markers)
    #         triangle = []
    # return mediapipe_face_mesh_triangles


def get_markers_from_connections(connections: Dict[int, int]):
    markers = []
    markers.extend(list(dict(connections).keys()))
    markers.extend(list(dict(connections).values()))

    markers = set(markers) #get unique markers in list
    return list(markers)


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
        "contour_markers": get_markers_from_connections(mediapipe_face_contour_connections),
        "connections": mediapipe_face_contour_connections,
        # "tesselation": convert_mediapipe_face_mesh_connections_to_triangles(),
    },
}

if __name__ == "__main__":
    import pprint

    pprint.pp(mediapipe_tracked_point_names_dict)
    print("\n--\n--\n--\n")
    pprint.pp(mediapipe_names_and_connections_dict)
