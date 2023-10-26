from ajc_freemocap_blender_addon.blender_interface.main_view3d_panel import VIEW3D_PT_freemocap_adapter
from ajc_freemocap_blender_addon.blender_interface.operators import BLENDER_OPERATORS
from ajc_freemocap_blender_addon.blender_interface.properties import FMC_ADAPTER_PROPERTIES

BLENDER_USER_INTERFACE_CLASSES = [FMC_ADAPTER_PROPERTIES,
                                  VIEW3D_PT_freemocap_adapter,
                                  *BLENDER_OPERATORS,
                                  ]
