"""
Blender script to load and visualize ChArUco board trajectory data from CSV
Run this script in Blender's Text Editor or as an add-on
"""

import bpy
import csv
from pathlib import Path
from typing import NamedTuple
from collections import defaultdict


class TrajectoryPoint(NamedTuple):
    """Single trajectory point with frame, keypoint ID, and 3D position"""
    frame: int
    keypoint: int
    x: float
    y: float
    z: float


def clear_scene() -> None:
    """Remove all objects from the scene"""
    # Deselect all objects
    bpy.ops.object.select_all(action='SELECT')
    # Delete selected objects
    bpy.ops.object.delete(use_global=False)
    
    # Remove all collections except Scene Collection
    for collection in bpy.data.collections:
        bpy.data.collections.remove(collection)


def read_trajectory_csv(filepath: str) -> list[TrajectoryPoint]:
    """
    Read trajectory data from CSV file
    
    Args:
        filepath: Path to the CSV file
        
    Returns:
        List of TrajectoryPoint objects
        
    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV format is invalid or no valid data found
    """
    trajectory_data: list[TrajectoryPoint] = []
    skipped_rows = 0
    
    if not Path(filepath).exists():
        raise FileNotFoundError(f"CSV file not found: {filepath}")
    
    with open(filepath, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        
        # Validate CSV headers
        if not reader.fieldnames:
            raise ValueError("CSV file appears to be empty or has no headers")
            
        expected_headers = {'frame', 'keypoint', 'x', 'y', 'z'}
        if not expected_headers.issubset(reader.fieldnames):
            raise ValueError(f"CSV missing required headers. Expected: {expected_headers}, Got: {reader.fieldnames}")
        
        for row_num, row in enumerate(reader, start=2):  # Start at 2 since header is line 1
            try:
                # Check for None or missing keys first
                if 'frame' not in row or 'keypoint' not in row:
                    raise ValueError(f"Row {row_num}: Missing critical fields (frame or keypoint)")
                
                # Handle None values and empty strings
                frame_val = row.get('frame', '').strip()
                keypoint_val = row.get('keypoint', '').strip()
                x_val = row.get('x', '').strip()
                y_val = row.get('y', '').strip()
                z_val = row.get('z', '').strip()
                
                # Check if critical fields are empty
                if not frame_val or not keypoint_val:
                    raise ValueError(f"Row {row_num}: Empty frame or keypoint values")
                
                # Check if any coordinate is empty or None
                if not x_val or not y_val or not z_val:
                    skipped_rows += 1
                    print(f"Skipping row {row_num}: missing coordinate data (frame={frame_val}, keypoint={keypoint_val})")
                    continue
                
                # Try to parse values
                point = TrajectoryPoint(
                    frame=int(frame_val),
                    keypoint=int(keypoint_val),
                    x=float(x_val),
                    y=float(y_val),
                    z=float(z_val)
                )
                trajectory_data.append(point)
                
            except ValueError as e:
                if "Missing critical fields" in str(e) or "Empty frame or keypoint" in str(e):
                    # Critical error - re-raise
                    raise
                # Non-critical error - skip the row
                skipped_rows += 1
                print(f"Skipping row {row_num}: {e}")
                continue
            except Exception as e:
                # Unexpected error - fail loudly
                raise RuntimeError(f"Unexpected error at row {row_num}: {e}") from e
    
    if skipped_rows > 0:
        print(f"Warning: Skipped {skipped_rows} rows with missing or invalid data")
    
    if not trajectory_data:
        raise ValueError(f"No valid trajectory data found in CSV file: {filepath}")
    
    return trajectory_data


def create_keypoint_object(*, keypoint_id: int, object_type: str = 'EMPTY') -> bpy.types.Object:
    """
    Create a Blender object to represent a keypoint
    
    Args:
        keypoint_id: Unique identifier for the keypoint
        object_type: Type of object to create ('EMPTY' or 'SPHERE')
        
    Returns:
        Created Blender object
        
    Raises:
        RuntimeError: If object creation fails
    """
    name = f"Keypoint_{keypoint_id:02d}"
    
    try:
        if object_type == 'SPHERE':
            # Create UV sphere mesh
            bpy.ops.mesh.primitive_uv_sphere_add(
                segments=16,
                ring_count=8,
                radius=0.005,
                location=(0, 0, 0)
            )
            obj = bpy.context.active_object
            if obj is None:
                raise RuntimeError(f"Failed to create sphere object for keypoint {keypoint_id}")
            
            obj.name = name
            
            # Add material for visibility
            mat = bpy.data.materials.new(name=f"Mat_{name}")
            mat.use_nodes = True
            # Set color based on keypoint ID
            hue = (keypoint_id * 0.15) % 1.0
            mat.node_tree.nodes["Principled BSDF"].inputs[0].default_value = (hue, 0.8, 1.0, 1.0)
            obj.data.materials.append(mat)
        else:
            # Create empty object
            bpy.ops.object.empty_add(
                type='SPHERE',
                radius=0.05,
                location=(0, 0, 0)
            )
            obj = bpy.context.active_object
            if obj is None:
                raise RuntimeError(f"Failed to create empty object for keypoint {keypoint_id}")
                
            obj.name = name
            obj.empty_display_size = 0.05
        
        return obj
        
    except Exception as e:
        raise RuntimeError(f"Failed to create keypoint object {keypoint_id}: {e}") from e


def apply_trajectory_to_objects(
    *,
    trajectory_data: list[TrajectoryPoint],
    scale_factor: float = 0.01,
    use_spheres: bool = False
) -> dict[int, bpy.types.Object]:
    """
    Create objects for each keypoint and apply trajectory animation
    
    Args:
        trajectory_data: List of trajectory points
        scale_factor: Scale factor to convert units (default 0.01 for cm to meters)
        use_spheres: If True, use sphere meshes instead of empties
        
    Returns:
        Dictionary mapping keypoint IDs to created objects
        
    Raises:
        ValueError: If trajectory_data is empty
        RuntimeError: If object creation or animation fails
    """
    if not trajectory_data:
        raise ValueError("Cannot apply trajectories: trajectory_data is empty")
    
    # Group trajectory data by keypoint
    trajectories_by_keypoint: dict[int, list[TrajectoryPoint]] = defaultdict(list)
    for point in trajectory_data:
        trajectories_by_keypoint[point.keypoint].append(point)
    
    if not trajectories_by_keypoint:
        raise ValueError("No keypoints found in trajectory data")
    
    # Create objects for each keypoint
    keypoint_objects: dict[int, bpy.types.Object] = {}
    
    for keypoint_id in sorted(trajectories_by_keypoint.keys()):
        trajectory = trajectories_by_keypoint[keypoint_id]
        
        # Skip keypoints with no trajectory data
        if not trajectory:
            print(f"Warning: Keypoint {keypoint_id} has no trajectory data, skipping")
            continue
        
        # Create object
        obj_type = 'SPHERE' if use_spheres else 'EMPTY'
        try:
            obj = create_keypoint_object(keypoint_id=keypoint_id, object_type=obj_type)
        except Exception as e:
            raise RuntimeError(f"Failed to create object for keypoint {keypoint_id}: {e}") from e
            
        keypoint_objects[keypoint_id] = obj
        
        # Sort trajectory points by frame
        trajectory = sorted(trajectory, key=lambda p: p.frame)
        
        # Apply keyframes
        for point in trajectory:
            # Convert coordinates (apply scale and coordinate system conversion)
            # Blender uses: X-right, Y-forward, Z-up
            # Input might be different, adjust as needed
            location = (
                point.x * scale_factor,
                -point.z * scale_factor,  # Swap Y and Z, negate for coordinate system
                point.y * scale_factor
            )
            
            obj.location = location
            obj.keyframe_insert(data_path="location", frame=point.frame + 1)  # Blender frames start at 1
    
    if not keypoint_objects:
        raise ValueError("No keypoint objects were created - all keypoints had empty trajectories")
    
    return keypoint_objects


def create_trajectory_trails(*, keypoint_objects: dict[int, bpy.types.Object], num_frames: int) -> None:
    """
    Create visual trails showing the path of each keypoint
    
    Args:
        keypoint_objects: Dictionary of keypoint objects
        num_frames: Total number of frames in animation
        
    Raises:
        ValueError: If inputs are invalid
        RuntimeError: If trail creation fails
    """
    if not keypoint_objects:
        print("Warning: No keypoint objects to create trails for")
        return
    
    if num_frames < 1:
        raise ValueError(f"Invalid num_frames: {num_frames}, must be >= 1")
    
    for keypoint_id, obj in keypoint_objects.items():
        try:
            # Sample positions from animation
            positions = []
            for frame in range(1, num_frames + 1):
                bpy.context.scene.frame_set(frame)
                positions.append(obj.matrix_world.translation.copy())
            
            # Skip if we don't have enough positions for a trail
            if len(positions) < 2:
                print(f"Warning: Keypoint {keypoint_id} has fewer than 2 positions, skipping trail creation")
                continue
            
            # Create curve object for trail
            curve_data = bpy.data.curves.new(name=f"Trail_{keypoint_id:02d}", type='CURVE')
            curve_data.dimensions = '3D'
            
            # Create spline
            spline = curve_data.splines.new('BEZIER')
            
            # Add points to spline (we need to add len-1 because one point already exists)
            num_points_to_add = len(positions) - 1
            if num_points_to_add > 0:
                spline.bezier_points.add(num_points_to_add)
            
            # Set positions
            for i, pos in enumerate(positions):
                point = spline.bezier_points[i]
                point.co = pos
                point.handle_left_type = 'AUTO'
                point.handle_right_type = 'AUTO'
            
            # Create curve object
            curve_obj = bpy.data.objects.new(f"Trail_{keypoint_id:02d}", curve_data)
            bpy.context.collection.objects.link(curve_obj)
            
            # Set curve properties for visibility
            curve_data.bevel_depth = 0.002
            curve_data.bevel_resolution = 2
            
            # Add material
            mat = bpy.data.materials.new(name=f"TrailMat_{keypoint_id:02d}")
            mat.use_nodes = True
            hue = (keypoint_id * 0.15) % 1.0
            mat.node_tree.nodes["Principled BSDF"].inputs[0].default_value = (hue, 0.8, 0.5, 1.0)
            curve_obj.data.materials.append(mat)
            
        except Exception as e:
            print(f"Error creating trail for keypoint {keypoint_id}: {e}")
            # Continue with other trails instead of failing completely
            continue


def setup_scene(*, num_frames: int) -> None:
    """
    Configure scene settings for the animation
    
    Args:
        num_frames: Total number of frames
        
    Raises:
        ValueError: If num_frames is invalid
    """
    if num_frames < 1:
        raise ValueError(f"Invalid num_frames: {num_frames}, must be >= 1")
    
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = num_frames
    scene.frame_set(1)
    
    # Set up viewport shading for better visibility
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'SOLID'
                    space.shading.light = 'MATCAP'
                    space.shading.studio_light = 'basic_1.exr'


def main(
    *,
    csv_filepath: str,
    clear_existing: bool = True,
    scale_factor: float = 0.01,
    use_spheres: bool = True,
    create_trails: bool = True
) -> None:
    """
    Main function to load trajectory data into Blender
    
    Args:
        csv_filepath: Path to the CSV file
        clear_existing: Whether to clear existing objects
        scale_factor: Scale factor for coordinates
        use_spheres: Use sphere meshes instead of empties
        create_trails: Create trajectory trail curves
        
    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If data is invalid or empty
        RuntimeError: If processing fails
    """
    print("=" * 50)
    print("Loading ChArUco Trajectory Data")
    print("=" * 50)
    
    # Validate inputs
    if not csv_filepath:
        raise ValueError("csv_filepath cannot be empty")
    
    if scale_factor <= 0:
        raise ValueError(f"scale_factor must be positive, got {scale_factor}")
    
    # Clear scene if requested
    if clear_existing:
        print("Clearing existing objects...")
        clear_scene()
    
    # Read CSV data
    print(f"Reading CSV file: {csv_filepath}")
    trajectory_data = read_trajectory_csv(csv_filepath)
    
    if not trajectory_data:
        raise ValueError("No trajectory data loaded from CSV")
    
    print(f"Loaded {len(trajectory_data)} trajectory points")
    
    # Get frame range
    frames = {point.frame for point in trajectory_data}
    if not frames:
        raise ValueError("No frames found in trajectory data")
    
    min_frame = min(frames)
    max_frame = max(frames)
    num_frames = max_frame - min_frame + 1
    
    print(f"Animation frames: {min_frame} to {max_frame} ({num_frames} frames)")
    
    # Create and animate objects
    print("Creating keypoint objects and applying animation...")
    keypoint_objects = apply_trajectory_to_objects(
        trajectory_data=trajectory_data,
        scale_factor=scale_factor,
        use_spheres=use_spheres
    )
    
    if not keypoint_objects:
        raise RuntimeError("Failed to create any keypoint objects")
    
    print(f"Created {len(keypoint_objects)} keypoint objects")
    
    # Create trajectory trails
    if create_trails:
        print("Creating trajectory trails...")
        create_trajectory_trails(keypoint_objects=keypoint_objects, num_frames=num_frames)
    
    # Setup scene
    print("Configuring scene settings...")
    setup_scene(num_frames=num_frames)
    
    print("=" * 50)  
    print("✓ Trajectory data loaded successfully!")
    print("Press SPACE to play the animation")
    print("=" * 50)


# ============================================================================
# USAGE
# ============================================================================

if __name__ == "__main__" or __name__ == '<run_path>':
    # IMPORTANT: Update this path to your CSV file location
    CSV_FILE = r"C:\Users\jonma\freemocap_data\recordings\2025-11-12_15-16-53_GMT-5_calibration\output_data\charuco_board_5_3_body_3d_xyz.csv"
    
    # Configuration options
    CLEAR_EXISTING = True  # Clear all existing objects before loading
    SCALE_FACTOR = 0.01    # Scale from millimeters to meters (adjust based on your data)
    USE_SPHERES = True     # Use sphere meshes (True) or empty objects (False)
    CREATE_TRAILS = True   # Create visual trails showing paths
    
    print(f"Loading trajectory from: {CSV_FILE}")
    try:
        main( 
            csv_filepath=CSV_FILE,
            clear_existing=CLEAR_EXISTING,
            scale_factor=SCALE_FACTOR,
            use_spheres=USE_SPHERES,
            create_trails=CREATE_TRAILS 
        )
    except Exception as e:
        print(f"ERROR: Failed to load trajectory data!")
        print(f"Error details: {e}")
        import traceback
        traceback.print_exc()
        raise