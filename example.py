import bpy

# Clear existing objects
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# Add a cube
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
