import logging

import bpy
from bpy.props import StringProperty, BoolProperty

logger = logging.getLogger(__name__)


class FMC_ADAPTER_PROPERTIES(bpy.types.PropertyGroup):
    logger.info("Initializing FMC_ADAPTER_PROPERTIES class...")

    data_parent_empty: bpy.props.PointerProperty(
        name="FreeMoCap data parent empty",
        description="Empty that serves as parent for all the freemocap empties",
        type=bpy.types.Object,
        poll=lambda self, object: object.type == 'EMPTY',
    )

    recording_path: StringProperty(
        name="FreeMoCap recording path",
        description="Path to a freemocap recording",
        default="",
        subtype='FILE_PATH',
    )

    # Show Options Booleans
    show_reorient_empties_options: BoolProperty(
        name="Show options",
        description="Show/hide the options for the Re-orient Empties operator",
        default=False,
    )
    show_bone_length_options: BoolProperty(
        name="Show options",
        description="Show/hide the options for the Reduce Bone Length Dispersion operator",
        default=False,
    )
    show_add_rig_options: BoolProperty(
        name="Show options",
        description="Show/hide the options for the Add Rig operator",
        default=False,
    )

    vertical_align_reference: bpy.props.EnumProperty(
        name='',
        description='Empty that serves as reference to align the z axis',
        items=[('left_knee', 'left_knee', ''),
               ('trunk_center', 'trunk_center', ''),
               ('right_knee', 'right_knee', '')]
    )
    vertical_align_angle_offset: bpy.props.FloatProperty(
        name='',
        default=0,
        description='Angle offset to adjust the vertical alignement of the z axis (in degrees)'
    )
    ground_align_reference: bpy.props.EnumProperty(
        name='',
        description='Empty that serves as ground reference to the axes origin',
        items=[('left_foot_index', 'left_foot_index', ''),
               ('right_foot_index', 'right_foot_index', ''),
               ('left_heel', 'left_heel', ''),
               ('right_heel', 'right_heel', '')]
    )
    vertical_align_position_offset: bpy.props.FloatProperty(
        name='',
        default=0,
        precision=3,
        description='Additional z offset to the axes origin relative to the imaginary ground level'
    )
    correct_fingers_empties: bpy.props.BoolProperty(
        name='',
        default=True,
        description='Correct the fingers empties. Match hand_wrist (axis empty) position to wrist (sphere empty)'
    )
    add_hand_middle_empty: bpy.props.BoolProperty(
        name='',
        default=True,
        description='Add an empty in the middle of the hand between index and pinky empties. This empty is used for a better orientation of the hand (experimental)'
    )

    # Reduce Bone Length Dispersion Options
    interval_variable: bpy.props.EnumProperty(
        name='',
        description='Variable used to define the new length dispersion interval',
        items=[('median', 'Median',
                'Defines the new dispersion interval as [median*(1-interval_factor),median*(1+interval_factor)]'),
               ('stdev', 'Standard Deviation',
                'Defines the new dispersion interval as [median-interval_factor*stdev,median+interval_factor*stdev]')]
    )
    interval_factor: bpy.props.FloatProperty(
        name='',
        default=0,
        min=0,
        precision=3,
        description='Factor to multiply the variable and form the limits of the dispersion interval like [median-factor*variable,median+factor*variable]. ' +
                    'If variable is median, the factor will be limited to values inside [0, 1].' +
                    'If variable is stdev, the factor will be limited to values inside [0, median/stdev]'
    )

    # Reduce Shakiness Options
    recording_fps: bpy.props.FloatProperty(
        name='',
        default=30,
        min=0,
        precision=3,
        description='Frames per second (fps) of the capture recording'
    )

    # Add Rig Options
    bone_length_method: bpy.props.EnumProperty(
        name='',
        description='Method use to calculate length of major bones',
        items=[('median_length', 'Median Length', ''),
               # ('current_frame', 'Current Frame', '')]
               ]
    )
    keep_symmetry: bpy.props.BoolProperty(
        name='',
        default=False,
        description='Keep right/left side symmetry (use average right/left side bone length)'
    )
    add_fingers_constraints: bpy.props.BoolProperty(
        name='',
        default=True,
        description='Add bone constraints for fingers'
    )
    use_limit_rotation: bpy.props.BoolProperty(
        name='',
        default=False,
        description='Add rotation limits (human skeleton) to the bones constraints (experimental)'
    )

    # Add Body Mesh Options
    body_mesh_mode: bpy.props.EnumProperty(
        name='',
        description='Mode (source) for adding the mesh to the rig',
        items=[('custom', 'custom', ''),
               ('file', 'file', '')]
    )
