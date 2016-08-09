
from PyQt5.QtCore import QSettings, QSize, Qt, QRectF
from PyQt5.QtWidgets import (
    QMainWindow,
    QMenu,
    QToolBar,
    QToolButton,
    QStyleFactory,
)
from PyQt5.QtGui import QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer

import sys

action_icons = {
    'action_Clear': ':/erase.svg',
    'action_Save': ':/save.svg',
    'action_ToggleOnTop': ':/pin.svg',
    'action_ToggleOnTop_off': ':/pin-off.svg',
    'action_SelectFont': ':/font.svg',
    'action_Configure': ':/settings.svg',
    'action_Reconnect': ':/refresh.svg',
    'action_AddTranslation': ':/add-translation.svg',
    'action_Lookup': ':/magnify.svg',
    'action_ManageDictionaries': ':/books.svg',
    'action_PaperTape': ':/tape.svg',
    'action_Suggestions': ':/lightbulb.svg',
    'action_Delete': ':/delete.svg',
    'action_New': ':/add.svg',
    'action_Undo': ':/undo.svg',
    'action_EditDictionaries': ':/pencil.svg',
    'action_RemoveDictionaries': ':/delete.svg',
    'action_AddDictionaries': ':/add.svg',
}

def SetSvgIcons(widget):
    for action in [a for a in dir(widget) if a.startswith('action_')]:
        icon_path = action_icons.get(action)
        button = getattr(widget, action)
        if action is 'action_ToggleOnTop':
            icon = QIcon()
            icon.addPixmap(
                GetSvgPixmap(action_icons.get('action_ToggleOnTop_off')),
                QIcon.Normal,
                QIcon.Off
            )
            icon.addPixmap(
                GetSvgPixmap(icon_path),
                QIcon.Normal,
                QIcon.On
            )
            button.setIcon(icon)
            button.setObjectName(action)
        elif icon_path is not None:
            icon = QIcon()
            icon.addPixmap(GetSvgPixmap(icon_path))
            button.setIcon(icon)
            button.setObjectName(action)



def GetSvgPixmap(icon_path, color=None):
    renderer = QSvgRenderer(icon_path)
    icon_pixmap = QPixmap(48, 48)
    icon_pixmap.fill(Qt.transparent)
    renderer.render(QPainter(icon_pixmap), QRectF(icon_pixmap.rect()))

    # Colorize the icon if desired
    if color is not None:
        painter = QPainter(icon_pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(icon_pixmap.rect(), color)
        painter.end()
    return icon_pixmap


def ToolButton(action):
    button = QToolButton()
    button.setDefaultAction(action)
    return button


def ToolBar(*action_list):
    toolbar = QToolBar()
    for action in action_list:
        toolbar.addWidget(ToolButton(action))
    if sys.platform.startswith('darwin'):
        toolbar.setStyle(QStyleFactory.create('windows'))
        toolbar.setIconSize(QSize(24, 24))
    return toolbar


class WindowState(object):

    ROLE = None

    def _save_state(self, settings):
        pass

    def save_state(self):
        assert self.ROLE
        settings = QSettings()
        settings.beginGroup(self.ROLE)
        settings.setValue('geometry', self.saveGeometry())
        if isinstance(self, QMainWindow):
            settings.setValue('state', self.saveState())
        self._save_state(settings)
        settings.endGroup()

    def _restore_state(self, settings):
        pass

    def restore_state(self):
        assert self.ROLE
        settings = QSettings()
        settings.beginGroup(self.ROLE)
        geometry = settings.value('geometry')
        if geometry is not None:
            self.restoreGeometry(geometry)
        if isinstance(self, QMainWindow):
            state = settings.value('state')
            if state is not None:
                self.restoreState(state)
        self._restore_state(settings)
        settings.endGroup()


def find_menu_actions(menu, root=''):
    '''Recursively find and return a menu actions.'''
    actions_dict = {}
    for action in menu.actions():
        if not action.text():
            continue
        action_id = root
        if action_id:
            action_id += '.'
        action_id += action.text().replace('&', '')
        actions_dict[action_id] = action
    for sub_menu in menu.findChildren(QMenu):
        sub_root = root
        if sub_root:
            sub_root += '.'
        sub_root += sub_menu.title().replace('&', '')
        actions_dict.update(find_menu_actions(sub_menu, sub_root))
    return actions_dict
