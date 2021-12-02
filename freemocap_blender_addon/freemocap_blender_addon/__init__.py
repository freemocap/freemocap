# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name" : "FreeMoCap",
    "author" : "Jonathan Samir Matthis",
    "description" : "",
    "blender" : (2, 80, 0),
    "version" : (0, 0, 1),
    "location" : "",
    "warning" : "",
    "category" : "fmc"
}

import bpy
from . import auto_load

auto_load.init()

def register():
    
    #define 'custom properties' - https://youtu.be/9fuFDHR-UkE 

    bpy.types.Scene.fmc_session_path = bpy.props.StringProperty(
        name = 'FMC Session Path',
        subtype= 'FILE_PATH'
    )

    auto_load.register()
    print('registering FreeMoCap Addon')

def unregister():
    auto_load.unregister()
