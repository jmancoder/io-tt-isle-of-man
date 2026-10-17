# Import-Export TT Isle Of Man
A Blender add-on for importing P3D and PTX files from TT Isle Of Man: Ride on the Edge 3. Support for exporting files will be added in a future release.

## Usage
Download the latest version of this add-on from the [releases](https://github.com/jmancoder/io-tt-isle-of-man/releases) page and install it. Blender 4.2 and newer is supported.

To import a scene/model file:
1. Click *File->Import->TT Isle of Man Scene (.p3d)*.
2. Select one or more P3D files.
3. Click *Import P3D*.

To import a texture file:
1. Click *File->Import->TT Isle of Man Texture (.ptx)*.
2. Select one or more PTX files.
3. Click *Import PTX*.

## Notes
- Materials for the imported textures must be created and assigned manually.
- Some meshes have two UV maps, which can be swapped with the camera icons in *Data (green triangle icon)->UV Maps*.
- Vertex colors can be visualized by adding a material with a color attribute node multiplied by or directly linked to the base color.

## Credits
- texture2ddecoder is used for converting DirectX texture formats. It is bundled with each release of this add-on.
    - License: MIT
    - Source code: https://github.com/K0lb3/texture2ddecoder
    - Package: https://pypi.org/project/texture2ddecoder/
