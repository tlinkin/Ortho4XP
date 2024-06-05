@echo off
echo Setting up Ortho4XP...

python -m venv venv

call venv\Scripts\activate.bat

pip install Utils\win\GDAL-3.8.4-cp312-cp312-win_amd64.whl

pip install Utils\win\scikit_fmm-2024.5.29-cp312-cp312-win_amd64.whl

pip install -r requirements_win.txt
 
echo Ortho4XP setup complete!
echo Use start_windows.bat to run Ortho4XP

deactivate
