#!/usr/bin/env bash

# Usage: ./setup.py bdist_app
# $1: wheel name (assumed to be in dist)
# $2: package name
# Script assumes brewed python3
set -e

osx_dir=$(dirname "$0")
plover_dir=$(dirname $osx_dir)
plover_wheel=$plover_dir/dist/$1.whl
PACKAGE=$2

echo "Making Plover.app with Plover wheel $plover_wheel"

# Find system Python
python3_bin_dir=$(dirname $(greadlink -f $(which python3)))
python3_dir=$(dirname $python3_bin_dir)
py_version=$(basename $python3_dir) # e.g. 3.6
echo "System python3 is found at: $python3_dir"

# App to build
app_dir=$plover_dir/build/$PACKAGE.app
app_dist_dir=$plover_dir/dist/Plover.app
# E.g. python3.6 (name of python executable)
target_python=python${py_version}
# Main library folder in App
target_dir=$app_dir/Contents/Frameworks

# Cleanup previous App and make skeleton
rm -rf $app_dir
mkdir -p $target_dir
mkdir $app_dir/Contents/MacOS
mkdir $app_dir/Contents/Resources

# Copy Python launcher
cp $python3_dir/Resources/Python.app/Contents/MacOS/Python $target_dir/${target_python}

# Copy over system dependencies for Python
python3 -m macholib standalone $app_dir

# Make site-packages local
python_home=$target_dir/Python.framework/Versions/$py_version/
# We want pip to install packages to $target_libs
target_libs=$python_home/lib/$target_python
# Replace symlink site-packages with real folder
rm $target_libs/site-packages
mkdir $target_libs/site-packages
# Add sitecustomize.py -- adds the above site-packages to our Python's sys.path
cp $plover_dir/osx/sitecustomize.py $target_libs/sitecustomize.py
# Disable user site-packages by changing a constant in site.py
sed -ie 's/ENABLE_USER_SITE = None/ENABLE_USER_SITE = False/g' $target_libs/site.py

# Absolute path to our python executable
full_target_python=$target_dir/$target_python
# The correct prefix for this Python (necessary because pip seems to get it wrong)
local_sys_prefix=$($full_target_python -c 'import sys; print(sys.prefix)')
# Install pip for this local python
curl https://bootstrap.pypa.io/get-pip.py | $full_target_python - --prefix=$local_sys_prefix

# Install Plover
$(cd $plover_dir && python3 setup.py write_requirements) 
$full_target_python -m pip install --prefix=$local_sys_prefix $plover_wheel -c $plover_dir/requirements_constraints.txt --upgrade

# Make launcher
plover_executable=MacOS/Plover
launcher_file=$app_dir/Contents/$plover_executable
cp $osx_dir/plover_app_launcher.sh $launcher_file
sed -i '' "s/pythonexecutable/$target_python/g" $launcher_file
chmod +x $launcher_file

# Copy icon
cp $osx_dir/plover.icns $app_dir/Contents/Resources/plover.icns

# Get Plover's version
plover_version=$($full_target_python -c "from plover import __version__; print(__version__)")

# This allows notifications from our Python binary to identify as from Plover...
/usr/libexec/PlistBuddy -c 'Add :CFBundleIdentifier string "org.openstenoproject.plover"' $app_dir/Contents/Frameworks/Info.plist

# Setup PList for Plover
/usr/libexec/PlistBuddy -c 'Add :CFBundleDevelopmentRegion string "en"' $app_dir/Contents/Info.plist
/usr/libexec/PlistBuddy -c 'Add :CFBundleIconFile string "plover.icns"' $app_dir/Contents/Info.plist
/usr/libexec/PlistBuddy -c 'Add :CFBundleIdentifier string "org.openstenoproject.plover"' $app_dir/Contents/Info.plist
/usr/libexec/PlistBuddy -c 'Add :CFBundleName string "Plover"' $app_dir/Contents/Info.plist
/usr/libexec/PlistBuddy -c 'Add :CFBundleDisplayName string "Plover"' $app_dir/Contents/Info.plist
/usr/libexec/PlistBuddy -c "Add :CFBundleExecutable string \"$plover_executable\"" $app_dir/Contents/Info.plist
/usr/libexec/PlistBuddy -c 'Add :CFBundlePackageType string "APPL"' $app_dir/Contents/Info.plist
/usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string \"$plover_version\"" $app_dir/Contents/Info.plist
/usr/libexec/PlistBuddy -c "Add :CFBundleVersion string \"$plover_version\"" $app_dir/Contents/Info.plist
/usr/libexec/PlistBuddy -c 'Add :CFBundleInfoDictionaryVersion string "6.0"' $app_dir/Contents/Info.plist
year=$(date '+%Y')
copyright="© $year, Open Steno Project"
/usr/libexec/PlistBuddy -c "Add :NSHumanReadableCopyright string \"$copyright\"" $app_dir/Contents/Info.plist
/usr/libexec/PlistBuddy -c 'Add :NSPrincipalClass string "NSApplication"' $app_dir/Contents/Info.plist
/usr/libexec/PlistBuddy -c 'Add :NSAppSleepDisabled bool true' $app_dir/Contents/Info.plist

# Start stripping extra content
rm -rf $python_home/Resources
rm -rf $python_home/share
rm -rf $python_home/bin
rm -rf $python_home/headers
rm -rf $python_home/include
rm -rf $python_home/lib/pkgconfig

# Extra standard library stuff
rm -rf $target_libs/tkinter
rm -rf $target_libs/idlelib
rm -rf $target_libs/ensure_pip

# Get rid of tests
find $target_libs -path '*/test*' -type d -print0 | xargs -0 rm -rf
# Get rid of .exe's
find $target_libs -path '*.exe' -type f -print0 | xargs -0 rm -rf
# Make distribution source-less
python3 -m utils.source_less $target_libs */pip/_vendor/distlib/*
# Trim big PyQt5 pieces
python3 -m utils.pyqt $target_libs

rm -rf $app_dist_dir
mv $app_dir $app_dist_dir
