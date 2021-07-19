

import maya.cmds as cmds
import math


def write_to_maya(fmcDataObj, slice=False, sample_by = 5):
    """
    takes an Actor dictionary dataset and and creates animated maya objects accordingly

    input:
        actor_dict: actor dictionary extracted from mmcap_datastructure
        slice: if not false should be an int tuple of len=2 defining start and end frame to write to Maya
    """
    for actor_name in fmcDataObj.list_actors():
        ### Creating point_names
        sample_length = fmcDataObj.get_actor_sample_count(actor_name)
        tracking_points = fmcDataObj.get_actor_tracking_points(actor_name)
        point_names = tracking_points.keys()

        # Create point locators
        pnt_locs = {}
        for pnt_name in point_names:
            pnt_locs[pnt_name] = cmds.spaceLocator(n=pnt_name+ "_loc")[0]

        #cmds.scale(0.2, 0.2, 0.2, list(pnt_locs.values()))


        # Make line connector between point locators according to "parents"
        connect_lines = []
        for pnt_name in point_names:
            parents = fmcDataObj.get_point_parents(actor_name, pnt_name)
            for parent_name in parents:
                line = make_line_between(pnt_locs[pnt_name], pnt_locs[parent_name], "connectorLine_" + pnt_name + "_" + parent_name)
                connect_lines.append(line)

        # group everything under the same transform
        grp = cmds.group(list(pnt_locs.values()) + connect_lines, name="mmcap_" + actor_name + "_grp")

        # Adding position data to point locators
        if not slice == False and len(slice)==2:
            print("Slice active: using samples in range: %s:%s" % (slice[0], slice[1]))
            sample_range = range(slice[0], slice[1], sample_by)
        else:
            sample_range = range(0, sample_length, sample_by)

        progress_step = 100./len(sample_range)
        progress = 0
        last_progress = 0
        for sample_i in sample_range:
            for pnt_name in point_names:
                loc_name = pnt_locs[pnt_name]
                pos = tracking_points[pnt_name]["samples"][sample_i]
                if not math.isnan(pos[0]):
                    cmds.setKeyframe(loc_name, v=pos[0], at='translateX', time=sample_i )
                    cmds.setKeyframe(loc_name, v=pos[1], at='translateY', time=sample_i )
                    cmds.setKeyframe(loc_name, v=pos[2], at='translateZ', time=sample_i )
            progress += progress_step
            if int(progress) > int(last_progress):
                print(str(int(progress)).zfill(2) + "%")
                last_progress = progress


        # Reorienting base group to align with grid
        for attr in reorient_transform:
            cmds.setAttr(grp+"." + attr, reorient_transform[attr])

        cmds.playbackOptions(minTime= sample_range[0], maxTime = sample_range[-1])




def make_line_between(obj1, obj2, line_name):
    """
    creates a curve segment and attaches each end to obj1 and obj2 accordingly
    """
    line = cmds.curve(name=line_name, d=1, p=[(0,0,0),(0,0,0)])
    cmds.connectAttr(obj1+".t", line + ".cv[0]")
    cmds.connectAttr(obj2+".t", line + ".cv[1]")
    return line



# Imperically derived orientation to place actor on grid in Maya
reorient_transform = {
    "translateX": 6.976,
    "translateY": -21.502,
    "translateZ": 47.516,
    "rotateX": -114.918,
    "rotateY": 4.391,
    "rotateZ":0,
    "scaleX": 0.031,
    "scaleY": 0.031,
    "scaleZ": 0.031,
    }
