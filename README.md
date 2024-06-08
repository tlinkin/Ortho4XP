# Ortho4XP
![example](https://github.com/shred86/Ortho4XP/assets/32663154/f06ebfe5-ba1d-4f05-9439-8e569bd99ef5)

Ortho4XP is a scenery generation tool for X-Plane. It creates the scenery base mesh and texture layer using external data and orthophoto sources.

This is a forked version of [Ortho4XP](https://github.com/oscarpilote/Ortho4XP) developed by [@oscarpilote](https://github.com/oscarpilote) which includes some minor updates, fixes and documentation. The official version is infrequently updated which is the reason I created this forked version to provide quicker updates and documentation. This forked version will incorporate any of the changes made to the official version.

The specific changes in this forked version:
* Code changes to enable using [PyInstaller](https://pyinstaller.org/en/stable/) to bundle Ortho4XP and its dependencies into a single package.
* Add the ability to set an alternate `custom_overlay_src` directory to resolve an issue for some users. The default X-Plane scenery files are split up between `/X-Plane 12/Global Scenery/X-Plane Global Scenery` and `/X-Plane 12/Global Scenery/X-Plane Demo Areas`. So if you set `custom_overlay_src` to the first directory and try to batch build a bunch of tiles, you might get an error that the .dsf file can't be found if its a location where the .dsf files are located in the second directory.
* Saves custom_dem and fill_nodata to global configuration.
* Display asterik next to zoom level number in the Tiles and configuration window if custom zoom levels have been specified for a tile.
* Includes Windows Python dependency wheel files for gdal and scikit-fmm.
* Update and pin requirements to latest working versions.
* Adds a bash script to automate the setup process for those that prefer not to use the packaged version.

## Installation

For installation instructions, refer to the [Installation page](https://github.com/shred86/Ortho4XP/wiki/Installation) in the [Wiki](https://github.com/shred86/Ortho4XP/wiki).

## Support

Troubleshooting steps for some issues are provided in the [Wiki FAQ](https://github.com/shred86/Ortho4XP/wiki/FAQ). For additional support or questions, refer to the [Ortho4XP forum](https://forums.x-plane.org/index.php?/forums/forum/322-ortho4xp/) at [X-Plane.org](https://forums.x-plane.org).
