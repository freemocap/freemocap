from typing import Union, Tuple, List

import bpy
import numpy as np


def create_crystal_material(name: str = "crystal_gem",
                            color: Union[str, Tuple, List] = "#00FFFF",
                            emission_strength: float = 1.0,
                            roughness: float = 0.01,
                            ior: float = 1.45,
                            ):

    # Create a new material
    material = bpy.data.materials.new(name=name)

    # Enable 'Use Nodes'
    material.use_nodes = True

    # Remove default
    material.node_tree.nodes.remove(material.node_tree.nodes['Principled BSDF'])


    # Add Glass Shader
    glass_shader = material.node_tree.nodes.new('ShaderNodeBsdfGlass')
    glass_shader.inputs['IOR'].default_value = ior
    glass_shader.inputs['Roughness'].default_value = roughness

    # Add Glossy Shader
    glossy_shader = material.node_tree.nodes.new('ShaderNodeBsdfGlossy')
    glossy_shader.inputs['Roughness'].default_value = roughness

    color_to_rgba(color)

    # Add Mix Shader
    mix_shader = material.node_tree.nodes.new('ShaderNodeMixShader')

    # Connect the shaders to the Material Output
    material.node_tree.links.new(glass_shader.outputs['BSDF'], mix_shader.inputs[1])
    material.node_tree.links.new(glossy_shader.outputs['BSDF'], mix_shader.inputs[2])
    material.node_tree.links.new(mix_shader.outputs['Shader'],
                                 material.node_tree.nodes['Material Output'].inputs['Surface'])

    # Set the factor of Mix Shader to 0.05
    mix_shader.inputs['Fac'].default_value = 0.05


def color_to_rgba(color):
    # Convert hex color to rgb
    if isinstance(color, str) and color.startswith("#"):
        rgb_color = [int(color[i:i + 2], 16) / 255. for i in (1, 3, 5)]
    elif isinstance(color, list) or isinstance(color, tuple):
        if len(color) == 3:
            rgb_color = color
            rgb_color.append(1.0)
        elif len(color) == 4:
            rgb_color = color
        else:
            raise ValueError(f"Color must be a list of length 3 or 4, not {len(color)}")
    return rgb_color


def create_material(
    name: str = "Generic",
    color: Union[str, Tuple, List, np.ndarray] = "#00FFFF",
    emission_strength: float = 1.0,
):
    """
    Create a material with the given name and color, with a strong emission.

    :param name: The name of the material.
    :param color: The color of the material, in hex format.
    :return: The created material.
    """
    material = bpy.data.materials.new(name=name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    # Clear all nodes to start clean
    nodes.clear()

    # Create necessary nodes
    output = nodes.new(type="ShaderNodeOutputMaterial")
    emission = nodes.new(type="ShaderNodeEmission")
    bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    mix = nodes.new(type="ShaderNodeMixShader")

    # Set the locations
    output.location = (300, 0)
    mix.location = (100, 0)
    bsdf.location = (-100, 50)
    emission.location = (-100, -50)

    # Set node links
    links.new(output.inputs[0], mix.outputs[0])
    links.new(mix.inputs[1], bsdf.outputs[0])
    links.new(mix.inputs[2], emission.outputs[0])

    # Convert color from hex to RGB
    if isinstance(color, str) and color.startswith("#"):
        color_rgb = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]  # skips the "#" and separates R, G, and B
    elif isinstance(color, list) or isinstance(color, tuple):
        color_rgb = color
    else:
        raise ValueError(f"Color must be a hex string or a list/tuple/array of length 3 or 4, not {color}")

    # Set the colors
    bsdf.inputs[0].default_value = (*color_rgb, 1)
    emission.inputs[0].default_value = (*color_rgb, 1)  # RGB + Alpha

    # Set the strength of the emission
    emission.inputs[1].default_value = emission_strength  # The higher this value, the more the material will glow

    return material



class MaterialMaker:
    def __init__(self,
                 material_name: str = "crystal_gem",
                 color: Union[str, Tuple, List] = "#00FFFF",
                 ior: float = 1.45,
                 roughness: float = 0.01):
        self.material = bpy.data.materials.new(name=material_name)
        self.material.use_nodes = True
        self.rgb_color = self._color_to_rgba(color)
        self._remove_default_shader()
        self._add_shaders(ior, roughness)

    def _color_to_rgba(self, color):
        if isinstance(color, str) and color.startswith("#"):
            return [int(color[i:i+2], 16) / 255. for i in (1, 3, 5)] + [1]
        elif isinstance(color, (list, tuple)) and len(color) in (3, 4):
            return list(color) + [1]*(4 - len(color))
        else:
            raise ValueError(f"Color must be a list or tuple of length 3 or 4, or a hex string, not {color}")

    def _remove_default_shader(self):
        self.material.node_tree.nodes.remove(self.material.node_tree.nodes['Principled BSDF'])

    def _add_shaders(self, ior, roughness):
        glass_shader = self._add_shader('ShaderNodeBsdfGlass', ior=ior, roughness=roughness)
        glossy_shader = self._add_shader('ShaderNodeBsdfGlossy', roughness=roughness)
        mix_shader = self.material.node_tree.nodes.new('ShaderNodeMixShader')
        mix_shader.inputs['Fac'].default_value = 0.05
        self._link_shaders(glass_shader, glossy_shader, mix_shader)

    def _add_shader(self, type: str, **kwargs):
        shader = self.material.node_tree.nodes.new(type)
        for attr, value in kwargs.items():
            shader.inputs[attr].default_value = value
        shader.inputs['Color'].default_value = self.rgb_color
        return shader

    def _link_shaders(self, glass_shader, glossy_shader, mix_shader):
        links = self.material.node_tree.links
        links.new(glass_shader.outputs['BSDF'], mix_shader.inputs[1])
        links.new(glossy_shader.outputs['BSDF'], mix_shader.inputs[2])
        links.new(mix_shader.outputs['Shader'],
                  self.material.node_tree.nodes['Material Output'].inputs['Surface'])
