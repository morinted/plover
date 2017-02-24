#!/usr/bin/env bash

python3_location=$(greadlink -f $(which python3))
pip3=$(greadlink -f $(which pip3))
pyvenv3=$(greadlink -f $(which pyvenv))
python3_bin_dir=$(dirname $python3_location)
python3_dir=$(dirname $python3_bin_dir)

py_version=$(basename $python3_dir)

target_dir=$(pwd)/build_app

target_python=python${py_version}
target_pip=pip${py_version}
target_pyvenv=pyvenv-${py_version}

rm -rf $target_dir
mkdir $target_dir

cd $target_dir

cp $python3_dir/Python $target_dir/lib${target_python}.dylib
cp -R $python3_dir/include $target_dir/include
cp -R $python3_dir/lib $target_dir/lib
rm $target_dir/lib/lib${target_python}.dylib
rm $target_dir/lib/lib${target_python}m.dylib
rm -r $target_dir/lib/pkgconfig

# Get pip and pvenv over here
cp $pip3 $target_dir/$target_pip
cp $pyvenv3 $target_dir/$target_pyvenv
# Replace their shebang with local python
sed -i '' "1s/.*/#!.\/$target_python/" $target_pip
sed -i '' "1s/.*/#!.\/$target_python/" $target_pyvenv

# Launcher
cp $python3_dir/Resources/Python.app/Contents/MacOS/Python $target_dir/${target_python}

# Change binary our own dylib
install_name_tool -change $python3_dir/Python @executable_path/lib${target_python}.dylib ${target_python}

# Change libpython similarly
chmod 777 lib${target_python}.dylib
install_name_tool -id @executable_path/lib${target_python}.dylib lib${target_python}.dylib

cd ../..
python3 setup.py write_requirements
pip3 install -r requirements.txt -c requirements_constraints.txt
python3 setup.py bdist_wheel

cd $target_dir

./$target_python -m venv plover-env
source plover-env/bin/activate

/usr/libexec/PlistBuddy -c 'Add :CFBundleIdentifier string "org.python.python"' ./plover-env/bin/Info.plist

plover_wheel=$(find ../../dist -name '*.whl')

pip install $plover_wheel -c ../../requirements_constraints.txt
