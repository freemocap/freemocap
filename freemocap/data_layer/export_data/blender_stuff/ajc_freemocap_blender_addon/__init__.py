import logging

from ajc_freemocap_blender_addon.system.configure_logging.configure_logging import configure_logging, LogLevel

DEBUG_UI = False

configure_logging(LogLevel.TRACE)
# configure_logging(LogLevel.DEBUG)
# configure_logging(LogLevel.INFO)
# configure_logging(LogLevel.WARNING)

logger = logging.getLogger(__name__)


bl_info = {
    'name': 'Freemocap',
    'author': 'ajc27',
    'version': (1, 1, 7),
    'blender': (3, 0, 0),
    'location': '3D Viewport > Sidebar > Freemocap',
    'description': 'Add-on to adapt the Freemocap Blender output',
    'category': 'Development',
}


def unregister():
    import bpy

    logger.info(f"Unregistering {__file__} as add-on")
    from ajc_freemocap_blender_addon.blender_interface import BLENDER_USER_INTERFACE_CLASSES
    for cls in BLENDER_USER_INTERFACE_CLASSES:
        logger.trace(f"Unregistering class {cls.__name__}")
        bpy.utils.unregister_class(cls)

    logger.info(f"Unregistering property group FMC_ADAPTER_PROPERTIES")
    del bpy.types.Scene.fmc_adapter_properties


def register():
    import bpy

    logger.info(f"Registering {__file__} as add-on")
    from ajc_freemocap_blender_addon.blender_interface import BLENDER_USER_INTERFACE_CLASSES
    logger.debug(f"Registering classes {BLENDER_USER_INTERFACE_CLASSES}")
    for cls in BLENDER_USER_INTERFACE_CLASSES:
        logger.trace(f"Registering class {cls.__name__}")
        bpy.utils.register_class(cls)

    logger.info(f"Registering property group FMC_ADAPTER_PROPERTIES")

    from ajc_freemocap_blender_addon.blender_interface import FMC_ADAPTER_PROPERTIES
    bpy.types.Scene.fmc_adapter_properties = bpy.props.PointerProperty(type=FMC_ADAPTER_PROPERTIES)

    try:
        from ajc_freemocap_blender_addon.core_functions.export.get_io_scene_fbx_addon import get_io_scene_fbx_addon
        get_io_scene_fbx_addon()
    except Exception as e:
        logger.error(f"Error loading io_scene_fbx addon: {str(e)}")
        raise

    logger.success(f"Finished registering {__file__} as add-on!")


if __name__ == "__main__":
    logger.info(f"Running {__file__} as main file ")
    register()
    logger.success(f"Finished running {__file__} as main file!")
