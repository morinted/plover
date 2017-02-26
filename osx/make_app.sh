#!/usr/bin/env bash

function make_app {
  osx_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

  python3_location=$(greadlink -f $(which python3))
  echo "Python 3 location: $python3_location"

  python3_bin_dir=$(dirname $python3_location)
  python3_dir=$(dirname $python3_bin_dir)

  py_version=$(basename $python3_dir)
  echo "Python version: $py_version"

  plover_dir=$(dirname $osx_dir)
  app_dir=$plover_dir/build/Plover.app

  target_python=python${py_version}
  python3_lib=$python3_dir/lib/$target_python
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
  cp -RPn $python3_lib $target_dir/plover-env/lib
  source $target_dir/plover-env/bin/activate

  plover_wheel=$(find $plover_dir/dist -name '*.whl')
  pip install $plover_wheel -c $plover_dir/requirements_constraints.txt

  # # Make distribution source-less
  # python3 -m utils.source_less $app_dir/Contents/MacOS */pip/_vendor/distlib/*
  # # Trim big PyQt5 pieces
  # python3 -m utils.pyqt $app_dir/Contents/MacOS/lib/$target_python/

  # Make scripts relocatable
  virtualenv -p python3 --relocatable $target_dir/plover-env

  
  # Fix dylibs
  echo 'Running macholib'
  pip3 install macholib
  python -m macholib standalone $app_dir

  echo 'Copying icon...'
  cp $osx_dir/plover.icns $app_dir/Contents/Resources/plover.icns

  echo 'Copying launcher...'
  cp $osx_dir/plover_launcher $app_dir/Contents/MacOS/Plover
  chmod +x $app_dir/Contents/MacOS/Plover


  echo 'Creating PLists'
  # This allows notifications to identify as from Plover.
  /usr/libexec/PlistBuddy -c 'Add :CFBundleIdentifier string "org.openstenoproject.plover"' $target_dir/plover-env/bin/Info.plist

  # Setup PList for our .app
  /usr/libexec/PlistBuddy -c 'Add :CFBundleDevelopmentRegion string "en"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :CFBundleIconFile string "plover.icns"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :CFBundleIdentifier string "org.openstenoproject.plover"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :CFBundleName string "Plover"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :CFBundleDisplayName string "Plover"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :CFBundleExecutable string "MacOS/Plover"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :CFBundlePackageType string "APPL"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :CFBundleShortVersionString string "1.2.3"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :CFBundleVersion string "1.2.3"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :CFBundleInfoDictionaryVersion string "6.0"' $app_dir/Contents/Info.plist
  year=$(date '+%Y')
  copyright="© $year, Open Steno Project"
  /usr/libexec/PlistBuddy -c "Add :NSHumanReadableCopyright string \"$copyright\"" $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :NSPrincipalClass string "NSApplication"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :NSAppSleepDisabled bool true' $app_dir/Contents/Info.plist

  deactivate
}

make_app
