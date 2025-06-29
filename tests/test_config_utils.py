import sys
import os
import unittest
from unittest.mock import MagicMock, patch
sys.path.append('/Users/jamiemun/Projects/Ortho4XP/src')
import O4_Config_Utils as CFG
from O4_Cfg_Vars import *
from tkinter import PhotoImage, ttk
import tempfile
import pdb
from unittest.mock import MagicMock

# class TestConfigUtils(unittest.TestCase):
#     def setUp(self):
#         self.cfg_vars = cfg_vars
#         self.cfg_app_vars = []
#         self.global_prefix = "global_"

#     # test_dict = {
#     #     "apt_smoothing_pix": {
#     #         "type": int,
#     #         "default": 8,
#     #         "hint": "How much gaussian blur is applied to the elevation raster for the look up of altitude over airports. Unit is the evelation raster pixel size.",
#     #     },
#     # }

#     @patch('builtins.exec')
#     def test_set_global_variables(self, mock_exec):

#         # Test setting a variable that does not start with the global prefix
#         for key, value in self.cfg_vars.items():

#             value = str(value["default"])

#             CFG.set_global_variables(key, value)

#             if "module" in cfg_vars[key]:
#                 continue
    
#             if key in cfg_app_vars:
#                 continue

#             if cfg_vars[key]["type"] in (bool, list):
#                 mock_exec.assert_called_with("globals()['" + key + "']=" + value)
#             else:
#                 mock_exec.assert_called_with(f"globals()['{key}']=cfg_vars['{key}']['type'](value)")

#         # Test setting a variable that starts with the global prefix but is not in cfg_app_vars
#         # CFG.set_global_variables("global_test_var", "test_value")
#         # mock_exec.assert_called_with("globals()['global_test_var'] = 'test_value'")


# class TestOrtho4XPConfig(unittest.TestCase):
#     def setUp(self):
#         """Setup test for Ortho4XP_Config module."""
#         with patch('tkinter.PhotoImage', return_value=MagicMock(spec=PhotoImage)), \
#              patch('tkinter.ttk.Button', return_value=MagicMock(spec=ttk.Button)):
#             mock_parent = MagicMock()
#             self.config = CFG.Ortho4XP_Config(mock_parent)

#             for key, dict in cfg_vars.items():
#                 self.config.v_[key].set = MagicMock() 
            
#             # self.config.cfg_vars = cfg_vars
#             # import pdb; pdb.set_trace()

#     def test_load_interface_from_variables(self):
#         """Test load_interface_from_variable method."""
#         for var, value in cfg_vars.items():
#             self.config.load_interface_from_variables()
#             value = str(value["default"])   
#             self.config.v_[var].set.assert_called_with(value)

#     # @patch('os.path.exists')
#     # def test_write_app_cfg(self, mock_exists) -> None:
#     #     """Test write_app_cfg method."""
#     #     with tempfile.NamedTemporaryFile(delete=False) as temp:
#     #         global_cfg_file = temp.name

#     #         for var in list_app_vars:
#     #             self.config.v_[var].set(cfg_app_vars[var]["default"])

#     #         self.config.dict_to_cfg = MagicMock()
#     #         self.config.cfg_to_dict = MagicMock()
#     #         self.config.write_app_cfg()

#     #         for var in list_app_vars:
#     #             self.config.dict_to_cfg.assert_called_once()

#     #         mock_exists.return_value = True

#     #         for var in list_app_vars:
#     #             self.config.cfg_to_dict.assert_called_once()

#     #     # Delete the temporary file
#     #     os.remove(global_cfg_file)
        
#     #     # self.config.global_cfg_file = True

#     #     # self.config.write_app_cfg()
    
#     def test_reset_app_cfg(self) -> None:
#         """Test reset_app_cfg method."""
#         self.config.reset_app_cfg()
#         for var in cfg_app_vars:
#             self.config.v_[var].set.assert_called_with(str(cfg_app_vars[var]["default"]))

class TestO4ConfigUtils(unittest.TestCase):
    @patch.object(CFG.Ortho4XP_Config, 'dict_to_cfg')
    @patch.object(CFG.Ortho4XP_Config, 'cfg_to_dict', return_value={})
    @patch('os.path.exists')
    def test_write_app_cfg(self, mock_exists, mock_cfg_to_dict, mock_dict_to_cfg):

        # Set up dummy data for self.v_
        v_ = {var: MagicMock() for var in list_app_vars}
        for var in v_:
            v_[var].get.return_value = 'dummy_data'

        # Set up O4_Config_Utils instance
        mock_parent = MagicMock()
        o4_config_utils = CFG.Ortho4XP_Config(mock_parent)
        o4_config_utils.v_ = v_

        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            global_cfg_file = temp.name

            # Set the global_cfg_file attribute
            o4_config_utils.global_cfg_file = global_cfg_file

            # Set up os.path.exists to return True
            mock_exists.return_value = True

            # Call the method to test
            o4_config_utils.write_app_cfg()

        # Check that dict_to_cfg and cfg_to_dict were called
        mock_dict_to_cfg.assert_called()
        mock_cfg_to_dict.assert_called_with(global_cfg_file)

        # Delete the temporary file
        os.remove(global_cfg_file)





if __name__ == '__main__':
    unittest.main()
