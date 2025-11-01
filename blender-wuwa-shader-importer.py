import bpy
import os

SHADER_FILE = r"" # WW_ShaderV2.blend
MODELS_FOLDER = r"" # Rename folders to match the FBX

SPECIAL_MATS = {"Bangs", "Hair", "Face", "Eye"}

MAIN_MATS_MAP = {
    "Base Color": "D",
    "Normal Map": "N",
    "Mask ID": "ID"
}

def main():
    outlines = bpy.data.node_groups.get("WW - Outlines")
    
    if not outlines:
        with bpy.data.libraries.load(SHADER_FILE, link=False) as (data_from, data_to):
            data_to.materials = list(data_from.materials)
            data_to.node_groups = [n for n in data_from.node_groups if n in {"Light Vectors", "WW - Outlines"}]
            data_to.objects = [o for o in data_from.objects if o in {"Head Origin", "Head Forward", "Head Up"}]
            
        outlines = bpy.data.node_groups.get("WW - Outlines")
            
        # Fix reversed names
        for i in range(5, 8):
            a = outlines.inputs[f"Outline {i} Material"]
            b = outlines.inputs[f"Outline {i} Mask"]
            a.name, b.name = b.name, a.name
            
    outlines_mat = bpy.data.materials.get("WW - Outlines")
    head_origin = bpy.data.objects.get("Head Origin")
    light_vectors = bpy.data.node_groups.get("Light Vectors")
    
    for obj in bpy.context.scene.objects:
        # Need to tell imported models from normal ones, I just use COL0 lol
        if obj.type != "MESH" or "COL0" not in obj.data.attributes: continue
        
        blender_mesh_name = obj.name.split("_", 1)[0]
        mesh_name = blender_mesh_name.split(".", 1)[0]
        
        # Head Origin
        
        new_head_origin = bpy.data.objects.get(f"{blender_mesh_name} - Head Origin")
        
        if not new_head_origin:
            new_head_origin = head_origin.copy()
            new_head_origin.name = f"{blender_mesh_name} - Head Origin"
            bpy.context.collection.objects.link(new_head_origin)
                    
            for child in head_origin.children:
                new_child = child.copy()
                new_child.parent = new_head_origin
                new_child.name = f"{blender_mesh_name} - {child.name}"
                new_child.matrix_parent_inverse = child.matrix_parent_inverse.copy()
                bpy.context.collection.objects.link(new_child)
                
            for con in new_head_origin.constraints:
                new_head_origin.constraints.remove(con)

            con = new_head_origin.constraints.new(type="CHILD_OF")
            con.target = obj
            con.subtarget = "Bip001Head"
        
        # Modifiers
        
        if "Light Vectors" not in obj.modifiers:
            mod = obj.modifiers.new(name="Light Vectors", type="NODES")
            mod.node_group = light_vectors

            inputs = mod.node_group.inputs

            mod[inputs["Head Origin"].identifier] = new_head_origin
            mod[inputs["Head Forward"].identifier] = bpy.data.objects.get(f"{blender_mesh_name} - Head Forward")
            mod[inputs["Head Up"].identifier] = bpy.data.objects.get(f"{blender_mesh_name} - Head Up")
            
        mod = obj.modifiers.get("Outlines")
        
        if not mod:
            mod = obj.modifiers.new(name="Outlines", type="NODES")
            mod.node_group = outlines

            inputs = mod.node_group.inputs

            id = inputs["Vertex Colors"].identifier
            mod[f"{id}_use_attribute"] = True
            mod[f"{id}_attribute_name"] = "COL0"
            
        # Materials
        for i, mat in enumerate(obj.data.materials):
            if not mat: continue
        
            mat_name = mat.name
            if " - " in mat_name: continue
        
            mat_name = mat_name.split(mesh_name)[1].split(".", 1)[0]
            source_mat_name = f"WW - {mat_name}" if mat_name in SPECIAL_MATS else "WW - Main"
            
            new_mat = bpy.data.materials.get(source_mat_name).copy()
            new_mat.name = new_mat.name.replace("WW", blender_mesh_name).replace("Main", mat_name)
            
            tex_prefix = fr"{MODELS_FOLDER}\{mesh_name}\Textures\T_{mesh_name}"
            
            nodes = new_mat.node_tree.nodes
            for node in nodes:
                if node.type != "TEX_IMAGE" or node.name == "Image Texture": continue
            
                suffix = "_"
                if mat_name in SPECIAL_MATS:
                    tex = node.name.rsplit(" ", 1)[1]
                    suffix +=  f"{'D' if tex == 'Diffuse' else tex}.png"
                else:
                    suffix += f"{MAIN_MATS_MAP.get(node.name)}.png"

                path = f"{tex_prefix}{mat_name}{suffix}"

                if os.path.exists(path):
                    node.image = bpy.data.images.load(path)
                    
                    if suffix != "_D.png":
                        node.image.colorspace_settings.name = "Non-Color"
                        
                        if suffix == "_ID.png":
                            nodes.get("Shadow Mask Converter").inputs[2].default_value = 1
            
            obj.data.materials[i] = new_mat
            
            outlines_i = i + 1
            
            if not outlines.inputs.get(f"Outline {outlines_i} Mask"):
                outlines.inputs.new("NodeSocketMaterial", f"Outline {outlines_i} Mask")
                outlines.inputs.new("NodeSocketMaterial", f"Outline {outlines_i} Material")
                
                nodes = outlines.nodes
                links = outlines.links
                
                group_inputs = nodes.new("NodeGroupInput")
                material_selection = nodes.new("GeometryNodeMaterialSelection")
                set_material = nodes.new("GeometryNodeSetMaterial")
                flip_faces = outlines.nodes.get("Flip Faces")
                
                links.new(group_inputs.outputs[f"Outline {outlines_i} Mask"], material_selection.inputs["Material"])
                links.new(material_selection.outputs["Selection"], set_material.inputs["Selection"])
                links.new(group_inputs.outputs[f"Outline {outlines_i} Material"], set_material.inputs["Material"])
                links.new(flip_faces.inputs["Mesh"].links[0].from_node.outputs["Geometry"], set_material.inputs["Geometry"])
                links.new(set_material.outputs["Geometry"], flip_faces.inputs["Mesh"])
                
            mod[inputs[f"Outline {outlines_i} Mask"].identifier] = new_mat
            mod[inputs[f"Outline {outlines_i} Material"].identifier] = outlines_mat
        
main()