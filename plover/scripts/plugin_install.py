
import os
import sys

from pkg_resources import load_entry_point

from plover.registry import PLUGINS_DIR, PLUGINS_PLATFORM, registry
from plover import __version__, log


def main():
    registry.load_plugins()
    argv = [
        'pip',
        'install',
        '--prefix', os.path.join(PLUGINS_DIR, PLUGINS_PLATFORM),
        'plover==%s' % __version__,
    ]
    argv += sys.argv[1:]
    log.info('%s', ' '.join(argv))
    sys.argv = argv
    sys.exit(load_entry_point('pip',
                              'console_scripts',
                              'pip')())

if '__main__' == __name__:
    main()
