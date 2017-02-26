import re
import os
import shutil
import glob
import sys


def fix_icons(ui_file_path):
    with open(ui_file_path, 'r') as fin:
        content = fin.read()
    # replace ``addPixmap(QtGui.QPixmap(":/settings.svg"),``
    # by ``addFile(":/settings.svg", QtCore.QSize(),``
    content = re.sub(r'\baddPixmap\(QtGui.QPixmap\(("[^"]*")\),',
                     r'addFile(\1, QtCore.QSize(),', content)
    with open(ui_file_path, 'w') as fout:
        fout.write(content)


def trim_extras(target_dir):
    # Trim the fat...
    for pattern in '''
    site-packages/PyQt5/**/*AxContainer*
    site-packages/PyQt5/**/*Bluetooth*
    site-packages/PyQt5/**/*CLucene*
    site-packages/PyQt5/**/*DBus*
    site-packages/PyQt5/**/*Designer*
    site-packages/PyQt5/**/*Help*
    site-packages/PyQt5/**/*Location*
    site-packages/PyQt5/**/*Multimedia*
    site-packages/PyQt5/**/*Network*
    site-packages/PyQt5/**/*Nfc*
    site-packages/PyQt5/**/*Position*
    site-packages/PyQt5/**/*Qml*
    site-packages/PyQt5/**/*Quick*
    site-packages/PyQt5/**/*Sensors*
    site-packages/PyQt5/**/*Serial*
    site-packages/PyQt5/**/*Sql*
    site-packages/PyQt5/**/*Test*
    site-packages/PyQt5/**/*Web*
    site-packages/PyQt5/**/*Xml*
    site-packages/PyQt5/**/*qtwebengine*
    site-packages/PyQt5/Qt/bin/*eay32.dll
    site-packages/PyQt5/Qt/bin/ssleay32.dll
    site-packages/PyQt5/Qt/plugins/audio
    site-packages/PyQt5/Qt/plugins/bearer
    site-packages/PyQt5/Qt/plugins/generic
    site-packages/PyQt5/Qt/plugins/geoservices
    site-packages/PyQt5/Qt/plugins/mediaservice
    site-packages/PyQt5/Qt/plugins/playlistformats
    site-packages/PyQt5/Qt/plugins/position
    site-packages/PyQt5/Qt/plugins/printsupport
    site-packages/PyQt5/Qt/plugins/sceneparsers
    site-packages/PyQt5/Qt/plugins/sensor*
    site-packages/PyQt5/Qt/plugins/sqldrivers
    site-packages/PyQt5/Qt/qml
    site-packages/PyQt5/Qt/resources
    site-packages/PyQt5/Qt/translations/qt_help_*
    site-packages/PyQt5/Qt/translations/qtconnectivity_*
    site-packages/PyQt5/Qt/translations/qtdeclarative_*
    site-packages/PyQt5/Qt/translations/qtlocation_*
    site-packages/PyQt5/Qt/translations/qtmultimedia_*
    site-packages/PyQt5/Qt/translations/qtquick*
    site-packages/PyQt5/Qt/translations/qtserialport_*
    site-packages/PyQt5/Qt/translations/qtwebsockets_*
    site-packages/PyQt5/pylupdate*
    site-packages/PyQt5/pyrcc*
    site-packages/PyQt5/uic
    site-packages/plover/gui_qt/*.ui
    site-packages/plover/gui_qt/messages/**/*.po
    site-packages/plover/gui_qt/messages/plover.pot
    site-packages/plover/gui_qt/resources
    Scripts
    '''.split():
        pattern = os.path.join(target_dir, pattern)
        for path in reversed(glob.glob(pattern, recursive=True)):
            print('removing', path)
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.unlink(path)

if __name__ == '__main__':
    directory = sys.argv[1]
    trim_extras(directory)
