"""
Blender script to load mediapipe body tracking data from CSV
"""

import bpy
import csv
import colorsys
from pathlib import Path
from dataclasses import dataclass


@dataclass
class TrackingPoint:
    """Single tracking point from mediapipe"""
    frame: int
    keypoint: str
    x: float
    y: float
    z: float
    model: str
    trajectory: str


def clear_scene() -> None:
    """Remove all objects from the scene"""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    for collection in bpy.data.collections:
        bpy.data.collections.remove(collection)


def read_mediapipe_csv(*, filepath: str) -> dict[str, list[TrackingPoint]]:
    """
    Read mediapipe tracking data from CSV file
    
    Args:
        filepath: Path to the CSV file
        
    Returns:
        Dictionary mapping keypoint names to their tracking points
        
    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV format is invalid
    """
    if not Path(filepath).exists():
        raise FileNotFoundError(f"CSV file not found: {filepath}")
    
    points_by_keypoint: dict[str, list[TrackingPoint]] = {}
    
    with open(filepath, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        
        if not reader.fieldnames:
            raise ValueError("CSV file is empty or has no headers")
        
        required_headers = {'frame', 'keypoint', 'x', 'y', 'z', 'model', 'trajectory'}
        if not required_headers.issubset(reader.fieldnames):
            missing = required_headers - set(reader.fieldnames)
            raise ValueError(f"CSV missing required headers: {missing}")
        
        for row_num, row in enumerate(reader, start=2):
            # Check for required fields
            frame_str = row.get('frame', '').strip()
            keypoint = row.get('keypoint', '').strip()
            x_str = row.get('x', '').strip()
            y_str = row.get('y', '').strip()
            z_str = row.get('z', '').strip()
            model = row.get('model', '').strip()
            trajectory = row.get('trajectory', '').strip()
            
            if not frame_str or not keypoint:
                raise ValueError(f"Row {row_num}: Missing frame or keypoint")
            
            # Skip rows with missing coordinates
            if not x_str or not y_str or not z_str:
                continue
            if 'face' in keypoint.lower():
                continue
            
            try:
                point = TrackingPoint(
                    frame=int(frame_str),
                    keypoint=keypoint,
                    x=float(x_str),
                    y=float(y_str),
                    z=float(z_str),
                    model=model,
                    trajectory=trajectory
                )
                
                if keypoint not in points_by_keypoint:
                    points_by_keypoint[keypoint] = []
                points_by_keypoint[keypoint].append(point)
                
            except ValueError as e:
                raise ValueError(f"Row {row_num}: Invalid data - {e}") from e
    
    if not points_by_keypoint:
        raise ValueError("No valid tracking data found in CSV")
    
    return points_by_keypoint


def get_keypoint_color(*, keypoint_name: str) -> tuple[float, float, float, float]:
    """
    Get a consistent color for a keypoint based on its name
    
    Args:
        keypoint_name: Name of the keypoint
        
    Returns:
        RGBA color tuple
    """
    # Use hash to generate consistent color
    hash_val = hash(keypoint_name) % 360
    hue = hash_val / 360.0
    rgb = colorsys.hsv_to_rgb(hue, 0.8, 1.0)
    return (*rgb, 1.0)


def create_keypoint_sphere(*, keypoint_name: str, radius: float = 0.001) -> bpy.types.Object:
    """
    Create a sphere mesh for a keypoint
    
    Args:
        keypoint_name: Name of the keypoint
        radius: Sphere radius in Blender units
        
    Returns:
        Created sphere object
    """
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=8,
        ring_count=6,
        radius=radius,
        location=(0, 0, 0)
    )
    
    obj = bpy.context.active_object
    if obj is None:
        raise RuntimeError(f"Failed to create sphere for keypoint {keypoint_name}")
    
    obj.name = f"keypoint_{keypoint_name}"
    
    # Add material
    mat = bpy.data.materials.new(name=f"mat_{keypoint_name}")
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs[0].default_value = get_keypoint_color(keypoint_name=keypoint_name)
    obj.data.materials.append(mat)
    
    return obj


def animate_keypoints(
    *,
    points_by_keypoint: dict[str, list[TrackingPoint]],
    scale_factor: float = 0.001,
    trajectory_filter: str|None = None
) -> dict[str, bpy.types.Object]:
    """
    Create and animate keypoint objects
    
    Args:
        points_by_keypoint: Dictionary of keypoint names to tracking points
        scale_factor: Scale factor for coordinates (mm to meters)
        trajectory_filter: Only use points with this trajectory type (e.g., "3d_xyz" or "rigid_3d_xyz")
        
    Returns:
        Dictionary mapping keypoint names to created objects
    """
    keypoint_objects: dict[str, bpy.types.Object] = {}
    
    for keypoint_name, points in points_by_keypoint.items():
        # Filter by trajectory type if specified
        if trajectory_filter:
            points = [p for p in points if p.trajectory == trajectory_filter]
            if not points:
                continue
        
        # Create sphere for this keypoint
        obj = create_keypoint_sphere(keypoint_name=keypoint_name)
        keypoint_objects[keypoint_name] = obj
        
        # Sort points by frame
        points = sorted(points, key=lambda p: p.frame)
        
        # Apply keyframes
        for point in points:
            # Convert coordinates
            # Mediapipe: X-right, Y-down, Z-forward
            # Blender: X-right, Y-forward, Z-up
            location = (
                point.x * scale_factor,
                -point.z * scale_factor,  # Forward becomes -Z
                -point.y * scale_factor   # Down becomes -Y (up in Blender)
            )
            
            obj.location = location
            obj.keyframe_insert(data_path="location", frame=point.frame + 1)
    
    return keypoint_objects


def create_skeleton_bones(*, keypoint_objects: dict[str, bpy.types.Object]) -> None:
    """
    Create edge connections between related keypoints to form a skeleton
    
    Args:
        keypoint_objects: Dictionary of keypoint objects
    """
    # Define bone connections for mediapipe body
    connections = [
        # Face
        ("nose", "left_eye_inner"),
        ("left_eye_inner", "left_eye"),
        ("left_eye", "left_eye_outer"),
        ("left_eye_outer", "left_ear"),
        ("nose", "right_eye_inner"),
        ("right_eye_inner", "right_eye"),
        ("right_eye", "right_eye_outer"),
        ("right_eye_outer", "right_ear"),
        ("mouth_left", "mouth_right"),
        
        # Arms
        ("left_shoulder", "left_elbow"),
        ("left_elbow", "left_wrist"),
        ("left_wrist", "left_pinky"),
        ("left_wrist", "left_index"),
        ("left_wrist", "left_thumb"),
        ("right_shoulder", "right_elbow"),
        ("right_elbow", "right_wrist"),
        ("right_wrist", "right_pinky"),
        ("right_wrist", "right_index"),
        ("right_wrist", "right_thumb"),
        
        # Torso
        ("left_shoulder", "right_shoulder"),
        ("left_shoulder", "left_hip"),
        ("right_shoulder", "right_hip"),
        ("left_hip", "right_hip"),
        
        # Legs
        ("left_hip", "left_knee"),
        ("left_knee", "left_ankle"),
        ("left_ankle", "left_heel"),
        ("left_ankle", "left_foot_index"),
        ("left_heel", "left_foot_index"),
        ("right_hip", "right_knee"),
        ("right_knee", "right_ankle"),
        ("right_ankle", "right_heel"),
        ("right_ankle", "right_foot_index"),
        ("right_heel", "right_foot_index"),
    ]
    
    # Create mesh edges for skeleton visualization
    vertices = []
    edges = []
    vertex_map: dict[str, int] = {}
    
    # Build vertex list from unique keypoints in connections
    for start_name, end_name in connections:
        if start_name not in keypoint_objects or end_name not in keypoint_objects:
            continue
            
        if start_name not in vertex_map:
            vertex_map[start_name] = len(vertices)
            vertices.append(keypoint_objects[start_name].location)
            
        if end_name not in vertex_map:
            vertex_map[end_name] = len(vertices)
            vertices.append(keypoint_objects[end_name].location)
            
        edges.append((vertex_map[start_name], vertex_map[end_name]))
    
    if not vertices:
        return
    
    # Create mesh
    mesh = bpy.data.meshes.new(name="skeleton_mesh")
    mesh.from_pydata(vertices, edges, [])
    mesh.update()
    
    # Create object
    skeleton_obj = bpy.data.objects.new("skeleton", mesh)
    bpy.context.collection.objects.link(skeleton_obj)
    
    # Add vertex parent constraints for each vertex to follow its keypoint
    for keypoint_name, vertex_index in vertex_map.items():
        if keypoint_name not in keypoint_objects:
            continue
            
        # Use hooks to connect vertices to keypoint objects
        hook_modifier = skeleton_obj.modifiers.new(
            name=f"hook_{keypoint_name}",
            type='HOOK'
        )
        hook_modifier.object = keypoint_objects[keypoint_name]
        hook_modifier.vertex_indices_set([vertex_index])


def setup_scene(*, num_frames: int) -> None:
    """
    Configure scene settings for the animation
    
    Args:
        num_frames: Total number of frames
    """
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = num_frames
    scene.frame_set(1)
    
    # Set viewport shading
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'SOLID'
                    space.overlay.show_floor = True
                    space.overlay.show_axis_x = True
                    space.overlay.show_axis_y = True


def main(*, csv_filepath: str, trajectory_type: str = "3d_xyz", create_skeleton: bool = True) -> None:
    """
    Main function to load mediapipe trajectory data into Blender
    
    Args:
        csv_filepath: Path to the CSV file
        trajectory_type: Which trajectory to use ("3d_xyz" or "rigid_3d_xyz")
        create_skeleton: Whether to create bone connections
    """
    print("=" * 60)
    print("MEDIAPIPE TRAJECTORY LOADER")
    print("=" * 60)
    
    # Clear existing scene
    print("Clearing scene...")
    clear_scene()
    
    # Read CSV data
    print(f"Reading CSV: {csv_filepath}")
    points_by_keypoint = read_mediapipe_csv(filepath=csv_filepath)
    
    # Get frame range
    all_frames = set()
    for points in points_by_keypoint.values():
        all_frames.update(p.frame for p in points)
    
    if not all_frames:
        raise ValueError("No frames found in data")
    
    min_frame = min(all_frames)
    max_frame = max(all_frames)
    num_frames = max_frame - min_frame + 1
    
    print(f"Found {len(points_by_keypoint)} keypoints")
    print(f"Frames: {min_frame} to {max_frame} ({num_frames} total)")
    print(f"Using trajectory: {trajectory_type}")
    
    # Create and animate keypoints
    print("Creating animated keypoints...")
    keypoint_objects = animate_keypoints(
        points_by_keypoint=points_by_keypoint,
        scale_factor=1, 
        trajectory_filter=trajectory_type
    )
    
    if not keypoint_objects:
        raise RuntimeError(f"No keypoints created for trajectory type: {trajectory_type}")
    
    print(f"Created {len(keypoint_objects)} keypoint objects")
    
    # Create skeleton connections
    if create_skeleton:
        print("Creating skeleton connections...")
        create_skeleton_bones(keypoint_objects=keypoint_objects)
    
    # Setup scene
    setup_scene(num_frames=num_frames)
    
    print("=" * 60)
    print("✓ LOAD COMPLETE")
    print("Press SPACE to play animation")
    print("=" * 60)


# ============================================================================
# USAGE
# ============================================================================

if __name__ == "__main__" or __name__ =='<run_path>':
    # UPDATE THIS PATH
    CSV_FILE = r"C:\Users\jonma\freemocap_data\recording_sessions\freemocap_test_data\output_data\freemocap_data_by_frame.csv"
    try:
        main(
            csv_filepath=CSV_FILE,
            trajectory_type="3d_xyz",  # or "rigid_3d_xyz"
            create_skeleton=True
        )
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise