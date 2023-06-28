
from pyqtgraph.parametertree import ParameterTree
from freemocap_utils.constants import TASK_INTERPOLATION, TASK_FILTERING, TASK_SKELETON_ROTATION, PARAM_ORDER
from freemocap_utils.postprocessing_widgets.parameter_widgets import interpolation_params, filter_params, rotation_params

#name mapping is used if the name of the key in the GUI parameter doesn't match what it needs to be in the settings dict
interpolation_name_mapping = {
    "Order (only used in spline interpolation)": PARAM_ORDER
}

def parameter_tree_to_dict(parameter_object, name_mapping=None):
    if name_mapping is None:
        name_mapping = {}
        
    for child in parameter_object.children():
        if child.hasChildren():
            child_dict = {}
            for grandchild in child.children():
                mapped_name = name_mapping.get(grandchild.name(), grandchild.name())
                child_dict[mapped_name] = grandchild.value()
            return child_dict
        else:
            return {child.name(): child.value()}

def create_main_page_parameter_tree():
    main_tree = ParameterTree()
    main_tree.addParameters(interpolation_params, showTop=False)
    main_tree.addParameters(filter_params, showTop=False)
    main_tree.addParameters(rotation_params,showTop = False)
    return main_tree

def create_main_page_settings_dict():
    interpolation_dict = parameter_tree_to_dict(interpolation_params, interpolation_name_mapping)
    filter_dict = parameter_tree_to_dict(filter_params)
    rotation_dict = parameter_tree_to_dict(rotation_params)

    settings_dict = {
        TASK_INTERPOLATION: interpolation_dict,
        TASK_FILTERING: filter_dict,
        TASK_SKELETON_ROTATION: rotation_dict
    }
    return settings_dict

def create_interpolation_parameter_tree():
    interpolation_tree = ParameterTree()
    interpolation_tree.addParameters(interpolation_params)

    return interpolation_tree

def create_interpolation_page_settings_dict():
    interpolation_dict = parameter_tree_to_dict(interpolation_params, interpolation_name_mapping)

    settings_dict = {
        TASK_INTERPOLATION: interpolation_dict,
    }
    return settings_dict

def create_filter_parameter_tree():
    filter_tree = ParameterTree()
    filter_tree.addParameters(filter_params)

    return filter_tree

def create_filter_page_settings_dict():
    interpolation_dict = parameter_tree_to_dict(interpolation_params, interpolation_name_mapping)
    filter_dict = parameter_tree_to_dict(filter_params)

    settings_dict = {
        TASK_INTERPOLATION: interpolation_dict,
        TASK_FILTERING: filter_dict,
    }
    return settings_dict

f = 2