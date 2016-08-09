# Python 2/3 compatibility.
from __future__ import print_function

import sys
import signal

import sip
sip.setapi('QVariant', 2)

from PyQt5.QtCore import (
    QCoreApplication,
    QLibraryInfo,
    QTimer,
    QTranslator,
    Qt,
)
from PyQt5.QtWidgets import QApplication, QMessageBox

from plover import log
from plover import __name__ as __software_name__
from plover import __version__

from plover.gui_qt.i18n import get_language, install_gettext


class Application(object):

    def __init__(self, config, use_qt_notifications):

        # This is done dynamically so localization
        # support can be configure beforehand.
        from plover.gui_qt.engine import Engine
        from plover.gui_qt.main_window import MainWindow

        self._app = None
        self._win = None
        self._engine = None
        self._translator = None

        QCoreApplication.setApplicationName(__software_name__.capitalize())
        QCoreApplication.setApplicationVersion(__version__)
        QCoreApplication.setOrganizationName('Open Steno Project')
        QCoreApplication.setOrganizationDomain('openstenoproject.org')

        self._app = QApplication(sys.argv[:1])
        self._app.setAttribute(Qt.AA_UseHighDpiPixmaps)

        # Enable localization of standard Qt controls.
        self._translator = QTranslator()
        translations_dir = QLibraryInfo.location(QLibraryInfo.TranslationsPath)
        self._translator.load('qtbase_' + get_language(), translations_dir)
        self._app.installTranslator(self._translator)

        QApplication.setQuitOnLastWindowClosed(False)

        signal.signal(signal.SIGINT, lambda signum, stack: QCoreApplication.quit())

        # Make sure the Python interpreter runs at least every second,
        # so signals have a chance to be processed.
        self._timer = QTimer()
        self._timer.timeout.connect(lambda: None)
        self._timer.start(1000)

        self._engine = Engine(config)

        self._win = MainWindow(self._engine, use_qt_notifications)

        self._app.aboutToQuit.connect(self._win.on_quit)

    def __del__(self):
        del self._win
        del self._app
        del self._engine
        del self._translator

    def run(self):
        self._app.exec_()
        self._engine.quit()
        self._engine.wait()


def show_error(title, message):
    print(message)
    app = QApplication([])
    QMessageBox.critical(None, title, message)
    del app


def main(config):

    handler = None
    try:
        if sys.platform.startswith('linux'):
            from plover.oslayer.log_dbus import DbusNotificationHandler
            handler = DbusNotificationHandler
        elif sys.platform.startswith('darwin'):
            from plover.oslayer.log_osx import OSXNotificationHandler
            handler = OSXNotificationHandler
    except Exception:
        log.info('could not import platform gui log', exc_info=True)
    if handler is not None:
        log.add_handler(handler())
        use_qt_notifications = False
    else:
        use_qt_notifications = True

    # Setup internationalization support.
    install_gettext()

    app = Application(config, use_qt_notifications)
    app.run()
    del app
