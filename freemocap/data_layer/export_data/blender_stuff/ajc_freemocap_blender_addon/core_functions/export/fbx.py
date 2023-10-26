import logging
from pathlib import Path

import bpy
import mathutils

logger = logging.getLogger(__name__)


def export_fbx(recording_path: str, ):
    logger.info("Exporting recording to FBX...")
    try:
        # Deselect all
        bpy.ops.object.select_all(action='DESELECT')

        # Select only the rig and the body_mesh
        bpy.data.objects['root'].select_set(True)
        bpy.data.objects['fmc_mesh'].select_set(True)

        recording_path = Path(recording_path)
        recording_name = recording_path.stem
        fbx_filename = recording_name + '.fbx'
        fbx_filepath = recording_path / fbx_filename

        # Define the export parameters dictionary
        export_parameters = {
            'filepath': str(fbx_filepath),
            'use_selection': True,
            'use_visible': False,
            'use_active_collection': False,
            'global_scale': 1.0,
            'apply_unit_scale': True,
            'apply_scale_options': 'FBX_SCALE_NONE',
            'use_space_transform': True,
            'bake_space_transform': False,
            'object_types': {'ARMATURE', 'MESH', 'EMPTY'},
            'use_mesh_modifiers': True,
            'use_mesh_modifiers_render': True,
            'mesh_smooth_type': 'FACE',
            'colors_type': 'SRGB',
            'prioritize_active_color': False,
            'use_subsurf': False,
            'use_mesh_edges': False,
            'use_tspace': False,
            'use_triangles': False,
            'use_custom_props': False,
            'add_leaf_bones': False,
            'primary_bone_axis': 'Y',
            'secondary_bone_axis': 'X',
            'use_armature_deform_only': False,
            'armature_nodetype': 'NULL',
            'bake_anim': True,
            'bake_anim_use_all_bones': True,
            'bake_anim_use_nla_strips': False,
            'bake_anim_use_all_actions': False,
            'bake_anim_force_startend_keying': True,
            'bake_anim_step': 1.0,
            'bake_anim_simplify_factor': 0.0,
            'path_mode': 'AUTO',
            'embed_textures': False,
            'batch_mode': 'OFF',
            'use_batch_own_dir': True,
            'use_metadata': True,
            'axis_forward': 'Y',
            'axis_up': 'Z'
        }

        ################# Use of Blender io_scene_fbx addon + send2UE modifications #############################

        # Import the export_fbx_bin module and necessary utilities
        import io_scene_fbx.export_fbx_bin as export_fbx_bin

        from io_scene_fbx.export_fbx_bin import (
            fbx_data_bindpose_element,
            AnimationCurveNodeWrapper
        )
        from bpy_extras.io_utils import axis_conversion
        from io_scene_fbx.fbx_utils import (
            FBX_MODELS_VERSION,
            FBX_POSE_BIND_VERSION,
            FBX_DEFORMER_SKIN_VERSION,
            FBX_DEFORMER_CLUSTER_VERSION,
            BLENDER_OBJECT_TYPES_MESHLIKE,
            units_convertor_iter,
            matrix4_to_array,
            get_fbx_uuid_from_key,
            get_blenderID_name,
            get_blender_bindpose_key,
            get_blender_anim_stack_key,
            get_blender_anim_layer_key,
            elem_empty,
            elem_data_single_bool,
            elem_data_single_int32,
            elem_data_single_int64,
            elem_data_single_float64,
            elem_data_single_string,
            elem_data_single_int32_array,
            elem_data_single_float64_array,
            elem_properties,
            elem_props_template_init,
            elem_props_template_set,
            elem_props_template_finalize,
            fbx_name_class
        )

        convert_rad_to_deg_iter = units_convertor_iter("radian", "degree")

        from io_scene_fbx.export_fbx_bin import fbx_data_element_custom_properties

        # Backup the method original_fbx_data_armature_elements of export_fbx_bin before it is modified
        backup_fbx_animations_do = export_fbx_bin.fbx_animations_do
        backup_fbx_data_armature_elements = export_fbx_bin.fbx_data_armature_elements
        backup_fbx_data_object_elements = export_fbx_bin.fbx_data_object_elements
        backup_fbx_data_bindpose_element = export_fbx_bin.fbx_data_bindpose_element

        # Modified the functions to adapt the fbx output to UE

        SCALE_FACTOR = 100
    except Exception as e:
        logger.error(e)
        return {'CANCELLED'}

    def fbx_animations_do(scene_data, ref_id, f_start, f_end, start_zero, objects=None, force_keep=False):
        """
        Generate animation data (a single AnimStack) from objects, for a given frame range.
        """
        bake_step = scene_data.settings.bake_anim_step
        simplify_fac = scene_data.settings.bake_anim_simplify_factor
        scene = scene_data.scene
        depsgraph = scene_data.depsgraph
        force_keying = scene_data.settings.bake_anim_use_all_bones
        force_sek = scene_data.settings.bake_anim_force_startend_keying

        if objects is not None:
            # Add bones and duplis!
            for ob_obj in tuple(objects):
                if not ob_obj.is_object:
                    continue
                if ob_obj.type == 'ARMATURE':
                    objects |= {bo_obj for bo_obj in ob_obj.bones if bo_obj in scene_data.objects}
                for dp_obj in ob_obj.dupli_list_gen(depsgraph):
                    if dp_obj in scene_data.objects:
                        objects.add(dp_obj)
        else:
            objects = scene_data.objects

        back_currframe = scene.frame_current
        animdata_ob = {}
        p_rots = {}

        for ob_obj in objects:
            if ob_obj.parented_to_armature:
                continue
            ACNW = AnimationCurveNodeWrapper
            loc, rot, scale, _m, _mr = ob_obj.fbx_object_tx(scene_data)
            rot_deg = tuple(convert_rad_to_deg_iter(rot))
            force_key = (simplify_fac == 0.0) or (ob_obj.is_bone and force_keying)

            animdata_ob[ob_obj] = (ACNW(ob_obj.key, 'LCL_TRANSLATION', force_key, force_sek, loc),
                                   ACNW(ob_obj.key, 'LCL_ROTATION', force_key, force_sek, rot_deg),
                                   ACNW(ob_obj.key, 'LCL_SCALING', force_key, force_sek, scale))
            p_rots[ob_obj] = rot

        force_key = (simplify_fac == 0.0)
        animdata_shapes = {}

        for me, (me_key, _shapes_key, shapes) in scene_data.data_deformers_shape.items():
            # Ignore absolute shape keys for now!
            if not me.shape_keys.use_relative:
                continue
            for shape, (channel_key, geom_key, _shape_verts_co, _shape_verts_idx) in shapes.items():
                acnode = AnimationCurveNodeWrapper(channel_key, 'SHAPE_KEY', force_key, force_sek, (0.0,))
                # Sooooo happy to have to twist again like a mad snake... Yes, we need to write those curves twice. :/
                acnode.add_group(me_key, shape.name, shape.name, (shape.name,))
                animdata_shapes[channel_key] = (acnode, me, shape)

        animdata_cameras = {}
        for cam_obj, cam_key in scene_data.data_cameras.items():
            cam = cam_obj.bdata.data
            acnode = AnimationCurveNodeWrapper(cam_key, 'CAMERA_FOCAL', force_key, force_sek, (cam.lens,))
            animdata_cameras[cam_key] = (acnode, cam)

        currframe = f_start
        while currframe <= f_end:
            real_currframe = currframe - f_start if start_zero else currframe
            scene.frame_set(int(currframe), subframe=currframe - int(currframe))

            for dp_obj in ob_obj.dupli_list_gen(depsgraph):
                pass  # Merely updating dupli matrix of ObjectWrapper...

            for ob_obj, (anim_loc, anim_rot, anim_scale) in animdata_ob.items():
                location_multiple = 100
                scale_factor = 1

                # if this curve is the object root then keep its scale at 1
                if len(str(ob_obj).split('|')) == 1:
                    location_multiple = 1
                    # Todo add to FBX addon
                    scale_factor = SCALE_FACTOR

                # We compute baked loc/rot/scale for all objects (rot being euler-compat with previous value!).
                p_rot = p_rots.get(ob_obj, None)
                loc, rot, scale, _m, _mr = ob_obj.fbx_object_tx(scene_data, rot_euler_compat=p_rot)

                # Todo add to FBX addon
                # the armature object's position is the reference we use to offset all location keyframes
                if ob_obj.type == 'ARMATURE':
                    location_offset = loc
                    # # subtract the location offset from each location keyframe if the use_object_origin is on
                    # if bpy.context.scene.send2ue.use_object_origin:
                    #     loc = mathutils.Vector(
                    #         (loc[0] - location_offset[0], loc[1] - location_offset[1], loc[2] - location_offset[2]))

                p_rots[ob_obj] = rot
                anim_loc.add_keyframe(real_currframe, loc * location_multiple)
                anim_rot.add_keyframe(real_currframe, tuple(convert_rad_to_deg_iter(rot)))
                anim_scale.add_keyframe(real_currframe, scale / scale_factor)
            for anim_shape, me, shape in animdata_shapes.values():
                anim_shape.add_keyframe(real_currframe, (shape.value * scale_factor,))
            for anim_camera, camera in animdata_cameras.values():
                anim_camera.add_keyframe(real_currframe, (camera.lens,))
            currframe += bake_step

        scene.frame_set(back_currframe, subframe=0.0)

        animations = {}

        # And now, produce final data (usable by FBX export code)
        # Objects-like loc/rot/scale...
        for ob_obj, anims in animdata_ob.items():
            for anim in anims:
                anim.simplify(simplify_fac, bake_step, force_keep)
                if not anim:
                    continue
                for obj_key, group_key, group, fbx_group, fbx_gname in anim.get_final_data(scene, ref_id, force_keep):
                    anim_data = animations.setdefault(obj_key, ("dummy_unused_key", {}))
                    anim_data[1][fbx_group] = (group_key, group, fbx_gname)

        # And meshes' shape keys.
        for channel_key, (anim_shape, me, shape) in animdata_shapes.items():
            final_keys = {}
            anim_shape.simplify(simplify_fac, bake_step, force_keep)
            if not anim_shape:
                continue
            for elem_key, group_key, group, fbx_group, fbx_gname in anim_shape.get_final_data(scene, ref_id,
                                                                                              force_keep):
                anim_data = animations.setdefault(elem_key, ("dummy_unused_key", {}))
                anim_data[1][fbx_group] = (group_key, group, fbx_gname)

        # And cameras' lens keys.
        for cam_key, (anim_camera, camera) in animdata_cameras.items():
            final_keys = {}
            anim_camera.simplify(simplify_fac, bake_step, force_keep)
            if not anim_camera:
                continue
            for elem_key, group_key, group, fbx_group, fbx_gname in anim_camera.get_final_data(scene, ref_id,
                                                                                               force_keep):
                anim_data = animations.setdefault(elem_key, ("dummy_unused_key", {}))
                anim_data[1][fbx_group] = (group_key, group, fbx_gname)

        astack_key = get_blender_anim_stack_key(scene, ref_id)
        alayer_key = get_blender_anim_layer_key(scene, ref_id)
        name = (get_blenderID_name(ref_id) if ref_id else scene.name).encode()

        if start_zero:
            f_end -= f_start
            f_start = 0.0

        return (astack_key, animations, alayer_key, name, f_start, f_end) if animations else None

    def fbx_data_armature_elements(root, arm_obj, scene_data):
        """
        Write:
            * Bones "data" (NodeAttribute::LimbNode, contains pretty much nothing!).
            * Deformers (i.e. Skin), bind between an armature and a mesh.
            ** SubDeformers (i.e. Cluster), one per bone/vgroup pair.
            * BindPose.
        Note armature itself has no data, it is a mere "Null" Model...
        """
        mat_world_arm = arm_obj.fbx_object_matrix(scene_data, global_space=True)
        bones = tuple(bo_obj for bo_obj in arm_obj.bones if bo_obj in scene_data.objects)

        bone_radius_scale = 33.0

        # Bones "data".
        for bo_obj in bones:
            bo = bo_obj.bdata
            bo_data_key = scene_data.data_bones[bo_obj]
            fbx_bo = elem_data_single_int64(root, b"NodeAttribute", get_fbx_uuid_from_key(bo_data_key))
            fbx_bo.add_string(fbx_name_class(bo.name.encode(), b"NodeAttribute"))
            fbx_bo.add_string(b"LimbNode")
            elem_data_single_string(fbx_bo, b"TypeFlags", b"Skeleton")

            tmpl = elem_props_template_init(scene_data.templates, b"Bone")
            props = elem_properties(fbx_bo)
            elem_props_template_set(tmpl, props, "p_double", b"Size", bo.head_radius * bone_radius_scale * SCALE_FACTOR)
            elem_props_template_finalize(tmpl, props)

            # Custom properties.
            if scene_data.settings.use_custom_props:
                fbx_data_element_custom_properties(props, bo)

            # Store Blender bone length - XXX Not much useful actually :/
            # (LimbLength can't be used because it is a scale factor 0-1 for the parent-child distance:
            # http://docs.autodesk.com/FBX/2014/ENU/FBX-SDK-Documentation/cpp_ref/class_fbx_skeleton.html#a9bbe2a70f4ed82cd162620259e649f0f )
            # elem_props_set(props, "p_double", "BlenderBoneLength".encode(), (bo.tail_local - bo.head_local).length, custom=True)

        # Skin deformers and BindPoses.
        # Note: we might also use Deformers for our "parent to vertex" stuff???
        deformer = scene_data.data_deformers_skin.get(arm_obj, None)
        if deformer is not None:
            for me, (skin_key, ob_obj, clusters) in deformer.items():
                # BindPose.
                mat_world_obj, mat_world_bones = fbx_data_bindpose_element(root, ob_obj, me, scene_data,
                                                                           arm_obj, mat_world_arm, bones)

                # Deformer.
                fbx_skin = elem_data_single_int64(root, b"Deformer", get_fbx_uuid_from_key(skin_key))
                fbx_skin.add_string(fbx_name_class(arm_obj.name.encode(), b"Deformer"))
                fbx_skin.add_string(b"Skin")

                elem_data_single_int32(fbx_skin, b"Version", FBX_DEFORMER_SKIN_VERSION)
                elem_data_single_float64(fbx_skin, b"Link_DeformAcuracy", 50.0)  # Only vague idea what it is...

                # Pre-process vertex weights (also to check vertices assigned ot more than four bones).
                ob = ob_obj.bdata
                bo_vg_idx = {bo_obj.bdata.name: ob.vertex_groups[bo_obj.bdata.name].index
                             for bo_obj in clusters.keys() if bo_obj.bdata.name in ob.vertex_groups}
                valid_idxs = set(bo_vg_idx.values())
                vgroups = {vg.index: {} for vg in ob.vertex_groups}
                verts_vgroups = (
                    sorted(((vg.group, vg.weight) for vg in v.groups if vg.weight and vg.group in valid_idxs),
                           key=lambda e: e[1], reverse=True)
                    for v in me.vertices)
                for idx, vgs in enumerate(verts_vgroups):
                    for vg_idx, w in vgs:
                        vgroups[vg_idx][idx] = w

                for bo_obj, clstr_key in clusters.items():
                    bo = bo_obj.bdata
                    # Find which vertices are affected by this bone/vgroup pair, and matching weights.
                    # Note we still write a cluster for bones not affecting the mesh, to get 'rest pose' data
                    # (the TransformBlah matrices).
                    vg_idx = bo_vg_idx.get(bo.name, None)
                    indices, weights = ((), ()) if vg_idx is None or not vgroups[vg_idx] else zip(
                        *vgroups[vg_idx].items())

                    # Create the cluster.
                    fbx_clstr = elem_data_single_int64(root, b"Deformer", get_fbx_uuid_from_key(clstr_key))
                    fbx_clstr.add_string(fbx_name_class(bo.name.encode(), b"SubDeformer"))
                    fbx_clstr.add_string(b"Cluster")

                    elem_data_single_int32(fbx_clstr, b"Version", FBX_DEFORMER_CLUSTER_VERSION)
                    # No idea what that user data might be...
                    fbx_userdata = elem_data_single_string(fbx_clstr, b"UserData", b"")
                    fbx_userdata.add_string(b"")
                    if indices:
                        elem_data_single_int32_array(fbx_clstr, b"Indexes", indices)
                        elem_data_single_float64_array(fbx_clstr, b"Weights", weights)
                    # Transform, TransformLink and TransformAssociateModel matrices...
                    # They seem to be doublons of BindPose ones??? Have armature (associatemodel) in addition, though.
                    # WARNING! Even though official FBX API presents Transform in global space,
                    #          **it is stored in bone space in FBX data!** See:
                    #          http://area.autodesk.com/forum/autodesk-fbx/fbx-sdk/why-the-values-return-
                    #                 by-fbxcluster-gettransformmatrix-x-not-same-with-the-value-in-ascii-fbx-file/
                    # test_data[bo_obj.name] = matrix4_to_array(mat_world_bones[bo_obj].inverted_safe() @ mat_world_obj)

                    # Todo add to FBX addon
                    transform_matrix = mat_world_bones[bo_obj].inverted_safe() @ mat_world_obj
                    transform_link_matrix = mat_world_bones[bo_obj]
                    transform_associate_model_matrix = mat_world_arm

                    transform_matrix = transform_matrix.LocRotScale(
                        [i * SCALE_FACTOR for i in transform_matrix.to_translation()],
                        transform_matrix.to_quaternion(),
                        [i * SCALE_FACTOR for i in transform_matrix.to_scale()],
                    )

                    elem_data_single_float64_array(fbx_clstr, b"Transform", matrix4_to_array(transform_matrix))
                    elem_data_single_float64_array(fbx_clstr, b"TransformLink", matrix4_to_array(transform_link_matrix))
                    elem_data_single_float64_array(fbx_clstr, b"TransformAssociateModel",
                                                   matrix4_to_array(transform_associate_model_matrix))

    def fbx_data_object_elements(root, ob_obj, scene_data):
        """
        Write the Object (Model) data blocks.
        Note this "Model" can also be bone or dupli!
        """
        obj_type = b"Null"  # default, sort of empty...
        if ob_obj.is_bone:
            obj_type = b"LimbNode"
        elif (ob_obj.type == 'ARMATURE'):
            if scene_data.settings.armature_nodetype == 'ROOT':
                obj_type = b"Root"
            elif scene_data.settings.armature_nodetype == 'LIMBNODE':
                obj_type = b"LimbNode"
            else:  # Default, preferred option...
                obj_type = b"Null"
        elif (ob_obj.type in BLENDER_OBJECT_TYPES_MESHLIKE):
            obj_type = b"Mesh"
        elif (ob_obj.type == 'LIGHT'):
            obj_type = b"Light"
        elif (ob_obj.type == 'CAMERA'):
            obj_type = b"Camera"

        if ob_obj.type == 'ARMATURE':
            # if bpy.context.scene.send2ue.export_object_name_as_root:
            #     # if the object is already named armature this forces the object name to root
            #     if 'armature' == ob_obj.name.lower():
            #         ob_obj.name = 'root'

            # # otherwise don't use the armature objects name as the root in unreal
            # else:
            #     # Rename the armature object to 'Armature'. This is important, because this is a special
            #     # reserved keyword for the Unreal FBX importer that will be ignored when the bone hierarchy
            #     # is imported from the FBX file. That way there is not an additional root bone in the Unreal
            #     # skeleton hierarchy.
            ob_obj.name = 'Armature'

        model = elem_data_single_int64(root, b"Model", ob_obj.fbx_uuid)
        model.add_string(fbx_name_class(ob_obj.name.encode(), b"Model"))
        model.add_string(obj_type)

        elem_data_single_int32(model, b"Version", FBX_MODELS_VERSION)

        # Object transform info.
        loc, rot, scale, matrix, matrix_rot = ob_obj.fbx_object_tx(scene_data)
        rot = tuple(convert_rad_to_deg_iter(rot))

        # Todo add to FBX addon
        if ob_obj.type == 'ARMATURE':
            scale = mathutils.Vector((scale[0] / SCALE_FACTOR, scale[1] / SCALE_FACTOR, scale[2] / SCALE_FACTOR))
            # if bpy.context.scene.send2ue.use_object_origin:
            #     loc = mathutils.Vector((0, 0, 0))

        elif ob_obj.type == 'Ellipsis':
            loc = mathutils.Vector((loc[0] * SCALE_FACTOR, loc[1] * SCALE_FACTOR, loc[2] * SCALE_FACTOR))
        elif ob_obj.type == 'MESH':
            pass
            # # centers mesh object by their object origin
            # if bpy.context.scene.send2ue.use_object_origin:
            #     asset_id = bpy.context.window_manager.send2ue.asset_id
            #     asset_data = bpy.context.window_manager.send2ue.asset_data.get(asset_id)
            #     # if this is a static mesh then check that all other mesh objects in this export are
            #     # centered relative the asset object
            #     if asset_data['_asset_type'] == 'StaticMesh':
            #         asset_object = bpy.data.objects.get(asset_data['_mesh_object_name'])
            #         current_object = bpy.data.objects.get(ob_obj.name)
            #         asset_world_location = asset_object.matrix_world.to_translation()
            #         object_world_location = current_object.matrix_world.to_translation()
            #         loc = mathutils.Vector((
            #             (object_world_location[0] - asset_world_location[0]) * SCALE_FACTOR,
            #             (object_world_location[1] - asset_world_location[1]) * SCALE_FACTOR,
            #             (object_world_location[2] - asset_world_location[2]) * SCALE_FACTOR
            #         ))

            #         if bpy.context.scene.send2ue.extensions.instance_assets.place_in_active_level:
            #             # clear rotation and scale only if spawning actor
            #             # https://github.com/EpicGames/BlenderTools/issues/610
            #             rot = (0, 0, 0)
            #             scale = (1.0 * SCALE_FACTOR, 1.0 * SCALE_FACTOR, 1.0 * SCALE_FACTOR)
            #     else:
            #         loc = mathutils.Vector((0, 0, 0))

        tmpl = elem_props_template_init(scene_data.templates, b"Model")
        # For now add only loc/rot/scale...
        props = elem_properties(model)
        elem_props_template_set(tmpl, props, "p_lcl_translation", b"Lcl Translation", loc,
                                animatable=True, animated=((ob_obj.key, "Lcl Translation") in scene_data.animated))
        elem_props_template_set(tmpl, props, "p_lcl_rotation", b"Lcl Rotation", rot,
                                animatable=True, animated=((ob_obj.key, "Lcl Rotation") in scene_data.animated))
        elem_props_template_set(tmpl, props, "p_lcl_scaling", b"Lcl Scaling", scale,
                                animatable=True, animated=((ob_obj.key, "Lcl Scaling") in scene_data.animated))
        elem_props_template_set(tmpl, props, "p_visibility", b"Visibility", float(not ob_obj.hide))

        # Absolutely no idea what this is, but seems mandatory for validity of the file, and defaults to
        # invalid -1 value...
        elem_props_template_set(tmpl, props, "p_integer", b"DefaultAttributeIndex", 0)

        elem_props_template_set(tmpl, props, "p_enum", b"InheritType", 1)  # RSrs

        # Custom properties.
        if scene_data.settings.use_custom_props:
            # Here we want customprops from the 'pose' bone, not the 'edit' bone...
            bdata = ob_obj.bdata_pose_bone if ob_obj.is_bone else ob_obj.bdata
            fbx_data_element_custom_properties(props, bdata)

        # Those settings would obviously need to be edited in a complete version of the exporter, may depends on
        # object type, etc.
        elem_data_single_int32(model, b"MultiLayer", 0)
        elem_data_single_int32(model, b"MultiTake", 0)
        elem_data_single_bool(model, b"Shading", True)
        elem_data_single_string(model, b"Culling", b"CullingOff")

        if obj_type == b"Camera":
            # Why, oh why are FBX cameras such a mess???
            # And WHY add camera data HERE??? Not even sure this is needed...
            render = scene_data.scene.render
            width = render.resolution_x * 1.0
            height = render.resolution_y * 1.0
            elem_props_template_set(tmpl, props, "p_enum", b"ResolutionMode", 0)  # Don't know what it means
            elem_props_template_set(tmpl, props, "p_double", b"AspectW", width)
            elem_props_template_set(tmpl, props, "p_double", b"AspectH", height)
            elem_props_template_set(tmpl, props, "p_bool", b"ViewFrustum", True)
            elem_props_template_set(tmpl, props, "p_enum", b"BackgroundMode", 0)  # Don't know what it means
            elem_props_template_set(tmpl, props, "p_bool", b"ForegroundTransparent", True)

        elem_props_template_finalize(tmpl, props)

    def fbx_data_bindpose_element(root, me_obj, me, scene_data, arm_obj=None, mat_world_arm=None, bones=[]):
        """
        Helper, since bindpose are used by both meshes shape keys and armature bones...
        """
        if arm_obj is None:
            arm_obj = me_obj
        # We assume bind pose for our bones are their "Editmode" pose...
        # All matrices are expected in global (world) space.
        bindpose_key = get_blender_bindpose_key(arm_obj.bdata, me)
        fbx_pose = elem_data_single_int64(root, b"Pose", get_fbx_uuid_from_key(bindpose_key))
        fbx_pose.add_string(fbx_name_class(me.name.encode(), b"Pose"))
        fbx_pose.add_string(b"BindPose")

        elem_data_single_string(fbx_pose, b"Type", b"BindPose")
        elem_data_single_int32(fbx_pose, b"Version", FBX_POSE_BIND_VERSION)
        elem_data_single_int32(fbx_pose, b"NbPoseNodes", 1 + (1 if (arm_obj != me_obj) else 0) + len(bones))

        # First node is mesh/object.
        mat_world_obj = me_obj.fbx_object_matrix(scene_data, global_space=True)
        fbx_posenode = elem_empty(fbx_pose, b"PoseNode")
        elem_data_single_int64(fbx_posenode, b"Node", me_obj.fbx_uuid)
        elem_data_single_float64_array(fbx_posenode, b"Matrix", matrix4_to_array(mat_world_obj))

        # Second node is armature object itself.
        if arm_obj != me_obj:
            fbx_posenode = elem_empty(fbx_pose, b"PoseNode")
            elem_data_single_int64(fbx_posenode, b"Node", arm_obj.fbx_uuid)

            # Todo merge into blenders FBX addon
            mat_world_arm = mat_world_arm.LocRotScale(
                mat_world_arm.to_translation(),
                mat_world_arm.to_quaternion(),
                [i / SCALE_FACTOR for i in mat_world_arm.to_scale()],
            )

            elem_data_single_float64_array(fbx_posenode, b"Matrix", matrix4_to_array(mat_world_arm))

        # And all bones of armature!
        mat_world_bones = {}
        for bo_obj in bones:
            bomat = bo_obj.fbx_object_matrix(scene_data, rest=True, global_space=True)
            mat_world_bones[bo_obj] = bomat
            fbx_posenode = elem_empty(fbx_pose, b"PoseNode")
            elem_data_single_int64(fbx_posenode, b"Node", bo_obj.fbx_uuid)

            # Todo merge into blenders FBX addon
            bomat = bomat.LocRotScale(
                bomat.to_translation(),
                bomat.to_quaternion(),
                [i / SCALE_FACTOR for i in bomat.to_scale()]
            )

            elem_data_single_float64_array(fbx_posenode, b"Matrix", matrix4_to_array(bomat))

        return mat_world_obj, mat_world_bones

    export_parameters["global_matrix"] = (
        axis_conversion(
            to_forward=export_parameters['axis_forward'],
            to_up=export_parameters['axis_up'],
        ).to_4x4()
    )

    # Replace the modified functions temporarily
    export_fbx_bin.fbx_animations_do = fbx_animations_do
    export_fbx_bin.fbx_data_armature_elements = fbx_data_armature_elements
    export_fbx_bin.fbx_data_object_elements = fbx_data_object_elements
    export_fbx_bin.fbx_data_bindpose_element = fbx_data_bindpose_element

    # Simulate the FBX Export Operator Class
    self = type(
        'FMCExportFBX',
        (object,),
        {'report': print("error")}
    )

    # Export the FBX file
    export_fbx_bin.save(self, bpy.context, **export_parameters)

    # Restore the modified functions with the saved backups
    export_fbx_bin.fbx_animations_do = backup_fbx_animations_do
    export_fbx_bin.fbx_data_armature_elements = backup_fbx_data_armature_elements
    export_fbx_bin.fbx_data_object_elements = backup_fbx_data_object_elements
    export_fbx_bin.fbx_data_bindpose_element = backup_fbx_data_bindpose_element
