@echo off
echo Setting up Ortho4XP...
echo:

echo Setting up a Python virtual environment
python -m venv venv
echo:

echo Activating the Python virtual environment
call venv\Scripts\activate.bat
echo:

echo Installing Python dependency: gdal
pip install Utils\win\GDAL-3.8.4-cp312-cp312-win_amd64.whl
echo:

echo Installing Python dependency: scikit-fmm
pip install Utils\win\scikit_fmm-2024.5.29-cp312-cp312-win_amd64.whl
echo:

echo Installing remaining Python dependencies
pip install -r requirements.txt
echo:

echo Ortho4XP setup complete!
echo:

echo Use start_windows.bat to start Ortho4XP
echo:

call deactivate
pause