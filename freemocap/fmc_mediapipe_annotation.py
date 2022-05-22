import cv2
import mediapipe as mp
from pathlib import Path


### mediapipe stuff
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles
mp_holistic = mp.solutions.holistic


def annotate_session_videos_with_mediapipe(session):

    annotated_video_save_path = session.sessionPath/'Annotated_Videos'
    annotated_video_save_path.mkdir(exist_ok=True)

    vid_count = 0
    for this_video_path in session.syncedVidPath.iterdir():  # Run MediaPipe 'Holistic' (body, hands, face) tracker on each video in the raw video folder
        if (this_video_path.suffix.lower() == ".mp4"):  # NOTE - at some point we should build some list of 'synced video names' and check against that
                vid_count += 1
                name_for_saved_video = session.sessionID + '_annotated_video_{}'.format(str(vid_count)) + '.mp4'

                print('Annotating video {} from synced videos folder'.format(str(vid_count)))
                generate_video_with_annotation(this_video_path,annotated_video_save_path, name_for_saved_video)


def generate_video_with_annotation(synced_video_path,path_to_save_video,name_for_saved_video):

    body_drawing_spec = mp_drawing.DrawingSpec(thickness=1, circle_radius=.2)
    hand_drawing_spec = mp_drawing.DrawingSpec(thickness=1, circle_radius=.2)
    face_drawing_spec = mp_drawing.DrawingSpec(thickness=1, circle_radius=.2)

    def annotate_image_with_mediapipe_data(image, mediapipe_results):
        mp_drawing.draw_landmarks(image=image,
                                landmark_list=mediapipe_results.face_landmarks,
                                connections=mp_holistic.FACEMESH_CONTOURS,
                                landmark_drawing_spec=None,
                                connection_drawing_spec=mp_drawing_styles
                                .get_default_face_mesh_contours_style())
        mp_drawing.draw_landmarks(image=image,
                                landmark_list=mediapipe_results.face_landmarks,
                                #   connections=mp_holistic.FACEMESH_TESSELATION,
                                connections=mp_holistic.FACEMESH_CONTOURS,
                                landmark_drawing_spec=None,
                                connection_drawing_spec=mp_drawing_styles
                                .get_default_face_mesh_tesselation_style())
        mp_drawing.draw_landmarks(image=image,
                                landmark_list=mediapipe_results.pose_landmarks,
                                connections=mp_holistic.POSE_CONNECTIONS,
                                landmark_drawing_spec=mp_drawing_styles
                                .get_default_pose_landmarks_style())
        mp_drawing.draw_landmarks(
                            image=image,
                            landmark_list=mediapipe_results.left_hand_landmarks,
                            connections=mp_holistic.HAND_CONNECTIONS,
                            landmark_drawing_spec=None,
                            connection_drawing_spec=mp_drawing_styles
                            .get_default_hand_connections_style())
        mp_drawing.draw_landmarks(
                            image=image,
                            landmark_list=mediapipe_results.right_hand_landmarks,
                            connections=mp_holistic.HAND_CONNECTIONS,
                            landmark_drawing_spec = None,
                            connection_drawing_spec=mp_drawing_styles
                            .get_default_hand_connections_style())
        return image

    drawing_spec = mp_drawing.DrawingSpec(thickness=1, circle_radius=1)

    cap = cv2.VideoCapture(str(synced_video_path))
    
    video_frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    video_frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    framerate = cap.get(cv2.CAP_PROP_FPS)

    writer = cv2.VideoWriter(str(path_to_save_video/name_for_saved_video),
                            cv2.VideoWriter_fourcc(*'mp4v'),
                            framerate,
                            (video_frame_width, video_frame_height))

    with mp_holistic.Holistic(
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        model_complexity=2) as holistic:
        success = True
        while success:
            success, raw_image = cap.read()
            if not success:
                break

            mediapipe_results = holistic.process(raw_image)
            annotated_image = annotate_image_with_mediapipe_data(raw_image, mediapipe_results)

            writer.write(annotated_image)

    writer.release()
    cap.release()

            
