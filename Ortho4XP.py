#!/usr/bin/env python3
import sys
import os
from pyproj import datadir
Ortho4XP_dir='..' if getattr(sys,'frozen',False) else '.'
sys.path.append(os.path.join(Ortho4XP_dir,'src'))

import O4_File_Names as FNAMES
sys.path.append(FNAMES.Provider_dir)
import O4_Imagery_Utils as IMG
import O4_Vector_Map as VMAP
import O4_Mesh_Utils as MESH
import O4_Mask_Utils as MASK
import O4_Tile_Utils as TILE
import O4_GUI_Utils as GUI
import O4_Config_Utils as CFG  # CFG imported last because it can modify other modules variables

# Check if running as a PyInstaller bundle and set PROJ_DATA environment
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    base_path = sys._MEIPASS
    relative_proj_path = os.path.join("pyproj", "proj_dir", "share", "proj")
    lib_path = os.path.join(sys._MEIPASS, "_internal")
    os.environ["DYLD_LIBRARY_PATH"] = lib_path + ":" + os.environ.get("DYLD_LIBRARY_PATH", "")
    proj_data_path = os.path.join(base_path, relative_proj_path)
    os.environ["PROJ_DATA"] = proj_data_path
    datadir.set_data_dir(proj_data_path)

if __name__ == '__main__':
    if not os.path.isdir(FNAMES.Utils_dir):
        print("Missing ",FNAMES.Utils_dir,"directory, check your install. Exiting.")
        sys.exit()   
    for directory in (FNAMES.Preview_dir, FNAMES.Provider_dir, FNAMES.Extent_dir, FNAMES.Filter_dir, FNAMES.OSM_dir,
                      FNAMES.Mask_dir,FNAMES.Imagery_dir,FNAMES.Elevation_dir,FNAMES.Geotiff_dir,FNAMES.Patch_dir,
                      FNAMES.Tile_dir,FNAMES.Tmp_dir):
        if not os.path.isdir(directory):
            try: 
                os.makedirs(directory)
                print("Creating missing directory",directory)
            except: 
                print("Could not create required directory",directory,". Exit.")
                sys.exit()
    IMG.initialize_extents_dict()
    IMG.initialize_color_filters_dict()
    IMG.initialize_providers_dict()
    IMG.initialize_combined_providers_dict()
    if len(sys.argv)==1: # switch to the graphical interface
        Ortho4XP = GUI.Ortho4XP_GUI()
        Ortho4XP.mainloop()	    
        print("Bon vol!")
    else:
        # CLI mode - dispatch to CLI module
        import O4_CLI as CLI
        sys.exit(CLI.main(sys.argv[1:]))
 
        
