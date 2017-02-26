#!/usr/bin/env bash
set -e
function make_app {
  osx_dir=$(dirname "$0")

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

  # Get Python launcher
  cp $python3_dir/Resources/Python.app/Contents/MacOS/Python $target_dir/${target_python}

  # Build Plover
  cd $plover_dir
  python3 setup.py write_requirements
  pip3 install -r requirements.txt -c requirements_constraints.txt
  pip3 install macholib
  python3 setup.py bdist_wheel

  plover_wheel=$(find $plover_dir/dist -name '*.whl')

  python3 -m macholib standalone $app_dir

  # Make site-packages Local Again
  python_home=$target_dir/Python.framework/Versions/$py_version/
  target_libs=$python_home/lib/$target_python
  # Replace symlink with real folder
  rm $target_libs/site-packages
  mkdir $target_libs/site-packages
  # # Add sitecustomize.py that will add the folder to site
  cp $plover_dir/osx/sitecustomize.py $target_libs/sitecustomize.py
  # Disable user site-packages by changing a constant in site.py
  sed -ie 's/ENABLE_USER_SITE = None/ENABLE_USER_SITE = False/g' $target_libs/site.py

  full_target_python=$target_dir/$target_python
  local_sys_prefix=$($full_target_python -c 'import sys; print(sys.prefix)')
  curl https://bootstrap.pypa.io/get-pip.py | $full_target_python - --prefix=$local_sys_prefix

  # Install Plover
  $full_target_python -m pip install --prefix=$local_sys_prefix $plover_wheel -c $plover_dir/requirements_constraints.txt --upgrade

  # Make launcher
  launcher_file=$app_dir/Contents/MacOS/Plover
  cp $osx_dir/plover_app_launcher.sh $launcher_file
  sed -i '' "s/pythonexecutable/$target_python/g" $launcher_file
  chmod +x $launcher_file

  # Copy icon
  cp $osx_dir/plover.icns $app_dir/Contents/Resources/plover.icns

  # Get current version
  plover_version=$($full_target_python -c "from plover import __version__; print(__version__)")

  # This allows notifications from our Python binary to identify as from Plover.
  /usr/libexec/PlistBuddy -c 'Add :CFBundleIdentifier string "org.openstenoproject.plover"' $app_dir/Contents/Frameworks/Info.plist

  # Setup PList for our .app
  /usr/libexec/PlistBuddy -c 'Add :CFBundleDevelopmentRegion string "en"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :CFBundleIconFile string "plover.icns"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :CFBundleIdentifier string "org.openstenoproject.plover"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :CFBundleName string "Plover"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :CFBundleDisplayName string "Plover"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :CFBundleExecutable string "MacOS/Plover"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :CFBundlePackageType string "APPL"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string \"$plover_version\"" $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c "Add :CFBundleVersion string \"$plover_version\"" $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :CFBundleInfoDictionaryVersion string "6.0"' $app_dir/Contents/Info.plist
  year=$(date '+%Y')
  copyright="© $year, Open Steno Project"
  /usr/libexec/PlistBuddy -c "Add :NSHumanReadableCopyright string \"$copyright\"" $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :NSPrincipalClass string "NSApplication"' $app_dir/Contents/Info.plist
  /usr/libexec/PlistBuddy -c 'Add :NSAppSleepDisabled bool true' $app_dir/Contents/Info.plist

  # Start stripping contents
  rm -rf $python_home/Resources
  rm -rf $python_home/share
  rm -rf $python_home/bin
  rm -rf $python_home/headers
  rm -rf $python_home/include
  rm -rf $python_home/lib/pkgconfig

  # Some extra standard library stuff
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
}

make_app
