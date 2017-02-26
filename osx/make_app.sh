#!/usr/bin/env bash

function make_app {
  osx_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

  python3_location=$(greadlink -f $(which python3))
  pip3=$(greadlink -f $(which pip3))
  pyvenv3=$(greadlink -f $(which pyvenv))
  python3_bin_dir=$(dirname $python3_location)
  python3_dir=$(dirname $python3_bin_dir)

  py_version=$(basename $python3_dir)

  plover_dir=$(dirname $osx_dir)
  app_dir=$plover_dir/build/Plover.app

  target_python=python${py_version}
  target_pip=pip${py_version}
  target_pyvenv=pyvenv-${py_version}

  target_dir=$app_dir/Contents/Frameworks

  rm -rf $app_dir
  mkdir -p $target_dir
  mkdir $app_dir/Contents/MacOS
  mkdir $app_dir/Contents/Resources

  cd $plover_dir
  python3 setup.py write_requirements
  pip3 install -r requirements.txt -c requirements_constraints.txt
  python3 setup.py bdist_wheel
  pip3 install virtualenv

  virtualenv -p python3 --always-copy $target_dir/plover-env
  source $target_dir/plover-env/bin/activate

# -----------------

  # #sed -i '' "1s/.*/#!.\/$target_python/" $target_dir/$target_pip

  # Make site-packages Local Again
  # Replace symlink with real folder
  rm $target_dir/lib/$target_python/site-packages
  mkdir $target_dir/lib/$target_python/site-packages
  # Add sitecustomize.py that will add the folder to site
  cp $plover_dir/osx/sitecustomize.py $target_dir/lib/$target_python/sitecustomize.py
  # Disable user site-packages by changing a constant in site.py
  sed -ie 's/ENABLE_USER_SITE = None/ENABLE_USER_SITE = False/g' $target_dir/lib/$target_python/site.py

# -----------------

  plover_wheel=$(find $plover_dir/dist -name '*.whl')
  pip install $plover_wheel -c $plover_dir/requirements_constraints.txt

  # # Make distribution source-less
  # python3 -m utils.source_less $app_dir/Contents/MacOS */pip/_vendor/distlib/*
  # # Trim big PyQt5 pieces
  # python3 -m utils.pyqt $app_dir/Contents/MacOS/lib/$target_python/

  # Make scripts relocatable
  virtualenv -p python3 --relocatable $target_dir/plover-env

  cd $target_dir

  target_dylib=$target_dir/plover-env/lib${target_python}.dylib
  cp $python3_dir/Python $target_dylib

  # Change binary to point at our own dylib
  echo 'Fixing Python dylib reference...'
  chmod 777 $target_dir/plover-env/.Python
  install_name_tool -id @executable_path/lib${target_python}.dylib $target_dir/plover-env/.Python

  # Change libpython similarly
  echo 'Fixing dylib self-reference...'
  chmod 777 $target_dylib
  install_name_tool -id @executable_path/lib${target_python}.dylib $target_dylib

  # Copy icon
  echo 'Copying icon...'
  cp $osx_dir/plover.icns $app_dir/Contents/Resources/plover.icns

  echo 'Creating PLists'
  # This allows notifications to identify as from Plover.
  /usr/libexec/PlistBuddy -c 'Add :CFBundleIdentifier string "org.openstenoproject.plover"' $target_dir/plover-enc/bin/Info.plist

  # Setup PList for our .app
  /usr/libexec/PlistBuddy -c 'Add :CFBundleDevelopmentRegion string "en"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :CFBundleIconFile string "plover.icns"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :CFBundleIdentifier string "org.openstenoproject.plover"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :CFBundleName string "Plover"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :CFBundleDisplayName string "Plover"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :CFBundleExecutable string "Frameworks/plover-env/bin/plover"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :CFBundlePackageType string "APPL"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :CFBundleShortVersionString string "1.2.3"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :CFBundleVersion string "1.2.3"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :CFBundleInfoDictionaryVersion string "6.0"' $app_dir/Contents/Info.plist
  year=$(date '+%Y')
  copyright="© $year, Open Steno Project"
  /usr/libexec/PlistBuddy -c "Add :NSHumanReadableCopyright string \"$copyright\"" $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :NSPrincipalClass string "NSApplication"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :NSAppSleepDisabled bool true' $app_dir/Contents/Info.plist
}

make_app
