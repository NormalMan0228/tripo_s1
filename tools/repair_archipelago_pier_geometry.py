"""Retain Tripo piling and wood maps, supply a clean open pedestrian deck."""
import math
import bmesh
import bpy
from mathutils import Vector
from mathutils.geometry import barycentric_transform
from mathutils.bvhtree import BVHTree

def repair_pier(building,height):
    mesh=building.data
    mesh.calc_loop_triangles()
    coordinates=[v.co.copy() for v in mesh.vertices]
    triangles=[list(t.vertices) for t in mesh.loop_triangles]
    uv=[tuple(Vector((*mesh.uv_layers.active.data[n].uv,0)) for n in t.loops) for t in mesh.loop_triangles]
    material_indices=[t.material_index for t in mesh.loop_triangles]
    materials=list(mesh.materials)
    uv_name=mesh.uv_layers.active.name
    tree=BVHTree.FromPolygons(coordinates,triangles,all_triangles=True)
    def sample(position):
        hit,normal,face,distance=tree.ray_cast(Vector((position.x*.65,position.y*.72,5)),Vector((0,0,-1)),10)
        if hit is None:
            return Vector((.5,.5,0)),0
        indices=triangles[face]
        texture=barycentric_transform(hit,*(coordinates[n] for n in indices),*uv[face])
        return texture,material_indices[face]
    # One planar cut keeps the original sculpted piles and lower support timbers.
    bm=bmesh.new();bm.from_mesh(mesh)
    cut=bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
        dist=.00001,plane_co=(0,0,.60),plane_no=(0,0,1),clear_outer=True,clear_inner=False)
    edges=[e for e in cut['geom_cut'] if isinstance(e,bmesh.types.BMEdge) and e.is_boundary]
    if edges:
        bmesh.ops.holes_fill(bm,edges=edges,sides=0)
    bm.normal_update();bm.to_mesh(mesh);bm.free();mesh.update()
    parts=[building]
    def finish(obj):
        for material in materials:
            obj.data.materials.append(material)
        layer=obj.data.uv_layers.active or obj.data.uv_layers.new(name=uv_name)
        layer.name=uv_name
        for polygon in obj.data.polygons:
            position=obj.matrix_world@polygon.center
            _,index=sample(position)
            polygon.material_index=index
            for loop in polygon.loop_indices:
                position=obj.matrix_world@obj.data.vertices[obj.data.loops[loop].vertex_index].co
                texture,_=sample(position)
                layer.data[loop].uv=texture[:2]
        parts.append(obj)
    def block(name,location,dimensions,bevel=.025):
        bpy.ops.mesh.primitive_cube_add(size=1,location=location)
        obj=bpy.context.object;obj.name=name;obj.scale=dimensions
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        modifier=obj.modifiers.new('Soft_timber_edges','BEVEL');modifier.width=bevel;modifier.segments=3
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        finish(obj)
    for i in range(12):
        block('Pier_Deck_Plank_%02d'%i,(0,-2.75+i*.5,1.10),(3,.49,.20),.024)
    for x in [-1.06,1.06]:
        for y in [-2.15,2.15]:
            bpy.ops.mesh.primitive_cylinder_add(vertices=20,radius=.23,depth=.52,location=(x,y,.82))
            finish(bpy.context.object)
    for x in [-1.32,1.32]:
        block('Pier_Side_Rail',(x,0,1.48),(.13,5.55,.14),.035)
        for y in [-2.76,2.76]:
            block('Pier_Corner_Post',(x,y,1.375),(.25,.25,.45),.034)
            block('Pier_Rounded_Cap',(x,y,height-.055),(.32,.32,.11),.04)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active=building
    bpy.ops.object.join()
    building.data.update();bpy.context.view_layer.update()
    return building
