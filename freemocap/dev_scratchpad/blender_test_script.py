import bpy

bpy.ops.mesh.primitive_monkey_add(enter_editmode=False, align='WORLD', location=(0, 0, 0), scale=(1, 1, 1))

this_monke = bpy.context.active_object

bpy.ops.mesh.primitive_monkey_add(enter_editmode=False, align='WORLD', location=(0, 2, 0), scale=(1, 1, 1))

