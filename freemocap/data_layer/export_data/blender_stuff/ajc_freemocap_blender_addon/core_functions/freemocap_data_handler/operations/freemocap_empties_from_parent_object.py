from typing import Dict

import bpy


def freemocap_empties_from_parent_object(parent_empty: bpy.types.Object) -> Dict[str, bpy.types.Object]:
    return {child.name: child for child in parent_empty.children}
