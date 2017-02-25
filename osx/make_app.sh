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

  cd $target_dir

  cp $python3_dir/Python $target_dir/lib${target_python}.dylib
  cp -R $python3_dir/include $target_dir/include
  cp -R $python3_dir/lib $target_dir/lib
  rm $target_dir/lib/lib${target_python}.dylib
  rm $target_dir/lib/lib${target_python}m.dylib
  rm -r $target_dir/lib/pkgconfig

  # Launcher
  cp $python3_dir/Resources/Python.app/Contents/MacOS/Python $target_dir/${target_python}

  # Change binary our own dylib
  install_name_tool -change $python3_dir/Python @executable_path/lib${target_python}.dylib ${target_python}

  # Change libpython similarly
  chmod 777 lib${target_python}.dylib
  install_name_tool -id @executable_path/lib${target_python}.dylib lib${target_python}.dylib

  cd $plover_dir
  python3 setup.py write_requirements
  pip3 install -r requirements.txt -c requirements_constraints.txt
  python3 setup.py bdist_wheel

  $target_dir/$target_python -m venv $app_dir/Contents/MacOS
  source $app_dir/Contents/MacOS/bin/activate

  plover_wheel=$(find $plover_dir/dist -name '*.whl')
  pip install $plover_wheel -c $plover_dir/requirements_constraints.txt

  ln $app_dir/Contents/MacOS/bin/plover $app_dir/Contents/MacOS/Plover

  # Make distribution source-less
  python3 -m utils.source_less $app_dir/Contents/MacOS */pip/_vendor/distlib/*
  # Trim big PyQt5 pieces
  python3 -m utils.pyqt $app_dir/Contents/MacOS/lib/$target_python/

  # Copy icon
  cp $osx_dir/plover.icns $app_dir/Contents/Resources/plover.icns

  # This allows notifications to identify as from Plover.
  /usr/libexec/PlistBuddy -c 'Add :CFBundleIdentifier string "org.openstenoproject.plover"' $app_dir/Contents/MacOS/bin/Info.plist

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

  mv $app_dir $plover_dir/dist/Plover.app

}

make_app
