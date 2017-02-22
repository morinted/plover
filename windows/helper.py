#!/usr/bin/env python3

# Python 2/3 compatibility.
from __future__ import print_function

import argparse
import contextlib
import glob
import hashlib
import inspect
import os
import shutil
import subprocess
import sys
import traceback
import zipfile


PY3 = sys.version_info[0] >= 3
WIN_DIR = os.path.dirname(os.path.abspath(__file__))
TOP_DIR = os.path.dirname(WIN_DIR)
NULL = open(os.devnull, 'r+b')
TEMP_DIR = r'C:\Temp'
PROG_DIR = r'C:\Progs'


sys.path.insert(0, TOP_DIR)
os.chdir(TOP_DIR)


if sys.stdout.isatty() and not sys.platform.startswith('win32'):

    def info(fmt, *args):
        s = fmt % args
        print('[34m' + s + '[0m')

else:

    def info(fmt, *args):
        s = fmt % args
        print(s)

if sys.stderr.isatty():

    def error(fmt, *args):
        s = fmt % args
        print('[31m' + s + '[0m', file=sys.stderr)

else:

    def error(fmt, *args):
        s = fmt % args
        print(s, file=sys.stderr)


class CommandExecutionException(Exception):

    def __init__(self, args, exitcode, stdout='', stderr=''):
        super(CommandExecutionException, self).__init__()
        self.args = args
        self.exitcode = exitcode
        self.stdout = stdout
        self.stderr = stderr


class Environment(object):

    def __init__(self):
        self.dry_run = False
        self.verbose = False
        self._env = {}

    def setup(self):
        pass

    def get_realpath(self, path):
        return path

    def get_distdir(self):
        raise NotImplementedError

    def add_to_path(self, directory):
        raise NotImplementedError

    def run(self, args, cwd=None, redirection='auto'):
        if self.verbose:
            print('running', ' '.join(args))
        if self.dry_run:
            return 0, ''
        env = self._get_env()
        if 'auto' == redirection:
            to_pipe = not self.verbose
        elif 'never' == redirection:
            to_pipe = False
        elif 'always' == redirection:
            to_pipe = True
        else:
            raise ValueError('invalid redirection mode: %s' % redirection)
        if to_pipe:
            stdout = stderr = subprocess.PIPE
        else:
            stdout = stderr = None
        if cwd is None:
            old_cwd = None
        else:
            old_cwd = os.getcwd()
            os.chdir(cwd)
        try:
            proc = subprocess.Popen(args, env=env, stdout=stdout, stderr=stderr)
            stdout, stderr = proc.communicate()
            returncode = proc.wait()
        finally:
            if old_cwd is not None:
                os.chdir(old_cwd)
        if 0 != returncode:
            raise CommandExecutionException(args, returncode, stdout, stderr)
        return stdout

    def _get_env(self):
        env = dict(os.environ)
        env.update(self._env)
        return env


class WineEnvironment(Environment):

    def __init__(self, prefix):
        super(WineEnvironment, self).__init__()
        self._prefix = os.path.abspath(prefix)
        self._env['WINEPREFIX'] = self._prefix
        self._env['WINEARCH'] = 'win32'
        self._env['WINEDEBUG'] = '-all'
        self._env['WINETRICKS_OPT_SHAREDPREFIX'] = '1'

    def setup(self):
        if not os.path.exists(self._prefix):
            info('intializing Wine prefix')
            for cmd in (
                'env DISPLAY= wineboot --init',
                # Wait for previous command to finish.
                'wineserver -w',
                'winetricks --no-isolate --unattended corefonts vcrun2008',
                'winetricks win7',
            ):
                self.run(cmd.split())
        if self.dry_run:
            return
        tempdir = self.get_realpath(TEMP_DIR)
        progdir = self.get_realpath(PROG_DIR)
        distdir = self.get_distdir()
        for directory in (tempdir, progdir, distdir):
            if not os.path.exists(directory):
                os.makedirs(directory)

    def get_realpath(self, path):
        path = path.replace('\\', '/')
        if path.startswith('C:'):
            path = 'c:' + path[2:]
        return os.path.join(self._prefix, 'dosdevices', path)

    def get_distdir(self):
        return os.path.expanduser('~/.cache/wine')

    def add_to_path(self, directory):
        if self.verbose:
            print('adding "%s" to PATH' % directory)
        if self.dry_run:
            return
        path = self.run(('wine', 'cmd.exe', '/c', 'echo', '%PATH%'), redirection='always')
        path = path.strip().replace("\\", "\\\\")
        directory = directory.replace("\\", "\\\\")
        regfile = r'%s\path.reg' % TEMP_DIR
        real_regfile = self.get_realpath(regfile)
        with open(real_regfile, 'w') as fp:
            fp.write('REGEDIT4\r\n')
            fp.write('\r\n')
            fp.write('[HKEY_LOCAL_MACHINE\\System\\CurrentControlSet\\Control\\Session Manager\\Environment]\r\n')
            fp.write('"PATH"="%s;%s"\r\n' % (directory, path))
        try:
            self.run(('regedit', regfile))
        finally:
            os.unlink(real_regfile)

    def run(self, args, cwd=None, redirection='auto'):
        exe = args[0]
        if exe.endswith('.exe') or exe.endswith('.bat'):
            cmd = ('wine',) + tuple(args)
        else:
            cmd = args
        return super(WineEnvironment, self).run(cmd, cwd, redirection)

    def _get_env(self):
        env = super(WineEnvironment, self)._get_env()
        for var in (
            'PYTHONPATH',
            # Make sure GTK environment variables don't spill over to the Wine environment.
            'GDK_BACKEND',
            'GDK_NATIVE_WINDOWS',
            'GDK_PIXBUF_MODULE_FILE',
            'GDK_RENDERING',
            'GTK2_RC_FILES',
            'GTK3_MODULES',
            'GTK_DATA_PREFIX',
            'GTK_EXE_PREFIX',
            'GTK_IM_MODULE',
            'GTK_IM_MODULE_FILE',
            'GTK_MODULES',
            'GTK_PATH',
            'GTK_THEME',
        ):
            if var in env:
                del env[var]
        return env


class Win32Environment(Environment):

    def __init__(self):
        super(Win32Environment, self).__init__()
        self._path = None

    def setup(self):
        if self.dry_run:
            return
        tempdir = self.get_realpath(TEMP_DIR)
        progdir = self.get_realpath(PROG_DIR)
        distdir = self.get_distdir()
        for directory in (tempdir, progdir, distdir):
            if not os.path.exists(directory):
                os.makedirs(directory)

    def get_distdir(self):
        return r'C:\Dist'

    def add_to_path(self, directory):
        if self.verbose:
            print('adding "%s" to PATH' % directory)
        if self._path is None:
            self._path = self.run(('cmd.exe', '/c', 'echo', '%PATH%'), redirection='always').strip()
        self._path = directory + ';' + self._path
        batch = r'%s\setpath.bat' % TEMP_DIR
        with open(batch, 'w') as fp:
            fp.write('@ECHO off\r\n')
            fp.write('setx PATH "%s"\r\n' % self._path)
        try:
            self.run((batch,))
        finally:
            os.unlink(batch)


class Helper(object):

    if PY3:
        DEPENDENCIES = (
            # Update pip so hidapi install from wheel works.
            ('pip', 'pip:pip',
             None, None, (), None),
            ('pyqt-distutils', 'pip:pyqt-distutils',
             None, None, (), None),
            ('wheel', 'pip:wheel',
             None, None, (), None),
        )
    else:
        DEPENDENCIES = (
            ('Cython', 'https://pypi.python.org/packages/2.7/C/Cython/Cython-0.23.4-cp27-none-win32.whl',
             'd7c1978fe2037674b151622158881c700ac2f06a', None, (), None),
            ('VC for Python', 'https://download.microsoft.com/download/7/9/6/796EF2E4-801B-4FC4-AB28-B59FBF6D907B/VCForPython27.msi',
             '7800d037ba962f288f9b952001106d35ef57befe', None, (), None),
        )

    def __init__(self):
        self.dry_run = False
        self.verbose = False
        self.unattended = True
        self._parser = argparse.ArgumentParser(description='Windows Environment Helper')
        self._parser.add_argument('-v', '--verbose', dest='_verbose',
                                  action='store_true', help='enable verbose traces')
        self._parser.add_argument('-n', '--dry-run', dest='_dry_run',
                                  action='store_true', help='don\'t actuall run any command, but show what would be done')
        self._subparsers = self._parser.add_subparsers(dest='_command', metavar='COMMAND')

        for name in dir(self):
            if not name.startswith('cmd_'):
                continue
            cmd = getattr(self, name)
            argspec = inspect.getargspec(cmd)
            name = name[4:]
            doc = cmd.__doc__.strip().split('\n')
            help = doc[0]
            parser = self._subparsers.add_parser(name, help=help, add_help=False)
            args_help = {}
            for line in doc[1:]:
                line = line.strip()
                if not line:
                    continue
                name, doc = line.split(': ', 2)
                args_help[name] = doc
            short_opts = set()
            assert 'self' == argspec.args[0]
            for n, a in enumerate(argspec.args[1:]):
                if argspec.defaults is None or n >= len(argspec.defaults):
                    default = None
                else:
                    default = argspec.defaults[n]
                if default is None:
                    name_or_flags = (a,)
                    action = None
                else:
                    name = '--' + a
                    short_name = '-' + a[0]
                    if short_name not in short_opts:
                        short_opts.add(short_name)
                        name_or_flags = (short_name, name)
                    else:
                        name_or_flags = name,
                    if isinstance(default, bool):
                        action = 'store_' + str(not default).lower()
                    else:
                        action = 'store'
                parser.add_argument(*name_or_flags,
                                    action=action,
                                    default=default,
                                    help=args_help.get(a))
            if argspec.varargs is not None:
                parser.add_argument(argspec.varargs,
                                    nargs=argparse.REMAINDER,
                                    help=args_help.get(argspec.varargs))


        self._env = Environment()
        self._install_handlers = {
            'easy_install': self._easy_install,
            'pip'         : self._pip_install,
            '.exe'        : self._install_exe,
            '.msi'        : self._install_msi,
            '.rar'        : self._install_archive,
            '.zip'        : self._install_archive,
            '.whl'        : self._pip_install,
        }

    def _rmtree(self, path):
        if not os.path.exists(path):
            return
        if self.verbose:
            print('rm -rf', path)
        if self.dry_run:
            return
        shutil.rmtree(path)

    def _makedirs(self, path):
        if os.path.exists(path):
            return
        if self.verbose:
            print('mkdir -p', path)
        if self.dry_run:
            return
        os.makedirs(path)

    def _rename(self, old, new):
        if self.verbose:
            print('mv', old, new)
        if self.dry_run:
            return
        os.rename(old, new)

    def _copyfile(self, src, dst):
        if self.verbose:
            print('cp', src, dst)
        if self.dry_run:
            return
        shutil.copyfile(src, dst)

    def _copytree(self, src, dst):
        if self.verbose:
            print('cp -r', src, dst)
        if self.dry_run:
            return
        shutil.copytree(src, dst)

    def _extract(self, archive, destination, *args):
        if self.verbose:
            print('extracting %s to %s' % (archive, destination))
        cmd = ['7z.exe', 'x', archive, '-y', '-o%s' % destination]
        cmd.extend(args)
        realdir = self._env.get_realpath(destination)
        self._rmtree(realdir)
        self._env.run(cmd)
        if self.dry_run:
            return
        contents = os.listdir(realdir)
        if 1 == len(contents):
            tmpdir = '%s.tmp' % realdir
            os.rename(realdir, tmpdir)
            os.rename(os.path.join(tmpdir, contents[0]), realdir)
            os.rmdir(tmpdir)

    def _install_exe(self, filename, *options):
        cmd = [filename]
        cmd.extend(options)
        self._env.run(cmd)

    def _install_msi(self, filename, *options):
        cmd = ['msiexec.exe', '/i', filename]
        if self.unattended:
            cmd.append('/q')
        cmd.extend(options)
        self._env.run(cmd)

    def _install_archive(self, filename, install_basename, add_to_path=True):
        program_dir = r'%s\%s' % (PROG_DIR, install_basename)
        self._extract(filename, program_dir)
        if add_to_path:
            self._env.add_to_path(program_dir)

    def _easy_install(self, filename, *options):
        if not self.unattended and filename.endswith('.exe'):
            cmd = [filename]
        else:
            # Don't use easy_install.exe so setuptools
            # can update itself if needed.
            cmd = ['python.exe', '-m', 'easy_install']
            if not self.verbose:
                cmd.append('--quiet')
            cmd.extend(options)
            cmd.extend(('--', filename))
        self._env.run(cmd)

    def _pip_install(self, *args):
        # Don't use pip.exe so pip can update itself if needed.
        cmd = ['python.exe', '-m', 'pip',
               '--timeout=5',
               '--retries=2',
               '--disable-pip-version-check']
        if not self.verbose:
            cmd.append('--quiet')
        cmd.extend(('install', '--upgrade'))
        cmd.extend(args)
        self._env.run(cmd)

    def _download(self, url, checksum, dst):
        import requests
        retries = 0
        while retries < 2:
            if not os.path.exists(dst):
                retries += 1
                try:
                    with contextlib.closing(requests.get(url, stream=True)) as r:
                        with open(dst, 'wb') as fp:
                            for chunk in iter(lambda: r.raw.read(4 * 1024), b''):
                                fp.write(chunk)
                except Exception as e:
                    print('error', e)
                    continue
            h = hashlib.sha1()
            with open(dst, 'rb') as fp:
                while True:
                    d = fp.read(4 * 1024 * 1024)
                    if not d:
                        break
                    h.update(d)
            if h.hexdigest() == checksum:
                break
            print('sha1 does not match: %s instead of %s' % (h.hexdigest(), checksum))
            os.unlink(dst)
        assert os.path.exists(dst), 'could not successfully retrieve %s' % url

    def _zipdir(self, directory, compression=zipfile.ZIP_DEFLATED):
        print('zipping',  directory)
        zipname = '%s.zip' % directory
        prefix = os.path.dirname(directory)
        with zipfile.ZipFile(zipname, 'w', compression) as zf:
            for dirpath, dirnames, filenames in os.walk(directory):
                for name in filenames:
                    src = os.path.join(dirpath, name)
                    dst = os.path.relpath(src, prefix)
                    zf.write(src, dst)

    def install(self, name, src, checksum, handler_format=None, handler_args=(), path_dir=None):
        info('installing %s', name)
        if src.startswith('pip:'):
            handler_format = 'pip'
            dst = src[4:]
        else:
            distdir = self._env.get_distdir()
            dst = os.path.join(distdir, os.path.basename(src))
            if not self.dry_run:
                self._download(src, checksum, dst)
            if handler_format is None:
                root, handler_format = os.path.splitext(dst)
        handler = self._install_handlers.get(handler_format)
        assert handler, 'no handler for installing format %s' % handler_format
        handler(dst, *handler_args)
        if path_dir is not None:
            self._env.add_to_path(path_dir)

    def cmd_help(self, *commands):
        '''print detailed help'''
        if not commands:
            commands = self._subparsers.choices.keys()
            self._parser.print_help()
        for name in commands:
            print()
            parser = self._subparsers.choices.get(name)
            if parser is None:
                raise ValueError('unknown command name: %s' % name)
            print('%s COMMAND' % name.upper())
            print()
            parser.print_help()

    def cmd_setup(self, interactive=False):
        '''setup environment

        interactive: don't run unattended
        '''
        self.unattended = not interactive
        self._env.setup()
        for name, src, checksum, handler_format, handler_args, path_dir in self.DEPENDENCIES:
            self.install(name, src, checksum, handler_format=handler_format, handler_args=handler_args, path_dir=path_dir)
        info('install requirements')
        cmd = ('python.exe', 'setup.py', 'write_requirements')
        if PY3:
            cmd += ('gui_qt',)
        self._env.run(cmd)
        self._pip_install('-r', 'requirements.txt', '-c', 'requirements_constraints.txt')

    def cmd_run(self, executable, *args):
        '''run command in environment

        executable: name of the executable to run
        args: additional arguments to pass to the executable
        '''
        self._env.run((executable,) + tuple(args), redirection='never')

    def cmd_dist(self):
        '''create windows distribution

        keep: don't remove build/dist directories at start
        '''
        self._rmtree('build')
        self._rmtree('dist')
        info('creating distribution')
        self._env.run(('python.exe', 'setup.py', 'bdist_win'))

    if PY3:

        def cmd_newdist(self, keep=False):
            '''create windows distribution
            '''
            from plover import __version__
            if not keep:
                self._rmtree('build')
                self._rmtree('dist')
            info('creating distribution')
            def download(src, checksum):
                dst = os.path.join(self._env.get_distdir(), os.path.basename(src))
                self._download(src, checksum, dst)
                return dst
            # Generate and cache wheels.
            wheels_dir = os.path.join(self._env.get_distdir(), 'wheels')
            self._env.run(('python.exe', 'setup.py', 'write_requirements',
                           'nosetup', 'notests', 'gui_qt'))
            self._env.run(('python.exe', '-m', 'pip', 'wheel',
                           '-w', wheels_dir,
                           '-r', 'requirements.txt',
                           '-c', 'requirements_constraints.txt'))
            # Setup embedded Python distribution.
            # Note: python35.zip is decompressed to prevent errors when 2to3 is
            # used (including indirectly by setuptools `build_py` command.
            py_embedded = download('https://www.python.org/ftp/python/3.5.2/python-3.5.2-embed-win32.zip',
                                   'a62675cd88736688bb87999e8b86d13ef2656312')
            dist_dir = os.path.join('dist', 'plover-%s-py3' % __version__)
            stdlib = os.path.join(dist_dir, 'python35.zip')
            os.makedirs(dist_dir)
            for path in (py_embedded, stdlib):
                with zipfile.ZipFile(path) as zip:
                    zip.extractall(dist_dir)
            os.unlink(stdlib)
            dist_py = (os.path.join(dist_dir, 'python.exe'),)
            # Install pip.
            get_pip = download('https://bootstrap.pypa.io/get-pip.py',
                               '3d45cef22b043b2b333baa63abaa99544e9c031d')
            self._env.run(dist_py + (get_pip,))
            dist_pip = dist_py + ('-m', 'pip')
            # Install dependencies.
            self._env.run(dist_pip + (
                'install',
                '--upgrade',
                '-f', wheels_dir,
                '-r', 'requirements.txt',
            ))
            # Install Plover.
            # Note: do not use the embedded Python executable with
            # `setup.py install` to prevent setuptools from installing
            # extra development dependencies...
            self._env.run(('python.exe', 'setup.py', 'bdist_wheel'))
            self._env.run(dist_pip + (
                'install',
                '--no-deps',
                '--ignore-installed',
                glob.glob('dist/plover-*.whl')[0],
            ))
            # List installed packages.
            self._env.run(dist_pip + ('list',))
            # Trim the fat...
            for pattern in '''
            Lib/site-packages/PyQt5/**/*AxContainer*
            Lib/site-packages/PyQt5/**/*Bluetooth*
            Lib/site-packages/PyQt5/**/*CLucene*
            Lib/site-packages/PyQt5/**/*DBus*
            Lib/site-packages/PyQt5/**/*Designer*
            Lib/site-packages/PyQt5/**/*Help*
            Lib/site-packages/PyQt5/**/*Location*
            Lib/site-packages/PyQt5/**/*Multimedia*
            Lib/site-packages/PyQt5/**/*Network*
            Lib/site-packages/PyQt5/**/*Nfc*
            Lib/site-packages/PyQt5/**/*OpenGL*
            Lib/site-packages/PyQt5/**/*Position*
            Lib/site-packages/PyQt5/**/*Print*
            Lib/site-packages/PyQt5/**/*Qml*
            Lib/site-packages/PyQt5/**/*Quick*
            Lib/site-packages/PyQt5/**/*Sensors*
            Lib/site-packages/PyQt5/**/*Serial*
            Lib/site-packages/PyQt5/**/*Sql*
            Lib/site-packages/PyQt5/**/*Test*
            Lib/site-packages/PyQt5/**/*Web*
            Lib/site-packages/PyQt5/**/*WinExtras*
            Lib/site-packages/PyQt5/**/*Xml*
            Lib/site-packages/PyQt5/**/*qtwebengine*
            Lib/site-packages/PyQt5/Qt/bin/libeay32.dll
            Lib/site-packages/PyQt5/Qt/bin/ssleay32.dll
            Lib/site-packages/PyQt5/Qt/plugins/audio
            Lib/site-packages/PyQt5/Qt/plugins/bearer
            Lib/site-packages/PyQt5/Qt/plugins/generic
            Lib/site-packages/PyQt5/Qt/plugins/geoservices
            Lib/site-packages/PyQt5/Qt/plugins/mediaservice
            Lib/site-packages/PyQt5/Qt/plugins/playlistformats
            Lib/site-packages/PyQt5/Qt/plugins/position
            Lib/site-packages/PyQt5/Qt/plugins/printsupport
            Lib/site-packages/PyQt5/Qt/plugins/sceneparsers
            Lib/site-packages/PyQt5/Qt/plugins/sensor*
            Lib/site-packages/PyQt5/Qt/plugins/sqldrivers
            Lib/site-packages/PyQt5/Qt/qml
            Lib/site-packages/PyQt5/Qt/resources
            Lib/site-packages/PyQt5/Qt/translations/qt_help_*
            Lib/site-packages/PyQt5/Qt/translations/qtconnectivity_*
            Lib/site-packages/PyQt5/Qt/translations/qtdeclarative_*
            Lib/site-packages/PyQt5/Qt/translations/qtlocation_*
            Lib/site-packages/PyQt5/Qt/translations/qtmultimedia_*
            Lib/site-packages/PyQt5/Qt/translations/qtquick*
            Lib/site-packages/PyQt5/Qt/translations/qtserialport_*
            Lib/site-packages/PyQt5/Qt/translations/qtwebsockets_*
            Lib/site-packages/PyQt5/pylupdate*
            Lib/site-packages/PyQt5/pyrcc*
            Lib/site-packages/PyQt5/uic
            Lib/site-packages/plover/gui_qt/*.ui
            Lib/site-packages/plover/gui_qt/messages/**/*.po
            Lib/site-packages/plover/gui_qt/messages/plover.pot
            Lib/site-packages/plover/gui_qt/resources
            Scripts
            '''.split():
                pattern = os.path.join(dist_dir, pattern)
                for path in reversed(glob.glob(pattern, recursive=True)):
                    if self.verbose:
                        print('removing', path)
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.unlink(path)
            # Add miscellaneous files: icon, license, ...
            for src in (
                'LICENSE.txt',
                'plover/assets/plover.ico',
            ):
                dst = os.path.join(dist_dir, os.path.basename(src))
                self._copyfile(src, dst)
            # Create launchers.
            for entrypoint, gui in (
                ('plover                = plover.main:main'                  , True ),
                ('plover_console        = plover.main:main'                  , False),
                ('plover_plugin_install = plover.scripts.plugin_install:main', False),
            ):
                self._env.run(dist_py + ('-c', ';'.join(
                    '''
                    from pip._vendor.distlib.scripts import ScriptMaker
                    sm = ScriptMaker(source_dir='{dist_dir}', target_dir='{dist_dir}')
                    sm.executable = 'python.exe'
                    sm.variants = set(('',))
                    sm.make('{entrypoint}', options={{'gui': {gui}}})
                    '''.format(dist_dir=dist_dir,
                               entrypoint=entrypoint,
                               gui=gui).strip().split('\n'))))
            # Make distribution source-less.
            self._env.run(dist_py + (
                '-m', 'utils.source_less',
                # Don't touch pip._vendor.distlib sources,
                # or `pip install` will not be usable...
                dist_dir, '*/pip/_vendor/distlib/*',
            ))
            # Zip results.
            self._zipdir(dist_dir)

    def main(self, args):
        opts = self._parser.parse_args(args)
        self.dry_run = self._env.dry_run = opts._dry_run
        self.verbose = self._env.verbose = opts._verbose
        args = {
            name: value
            for name, value
            in opts._get_kwargs()
            if not name.startswith('_')
        }
        cmd = getattr(self, 'cmd_%s' % opts._command)
        argspec = inspect.getargspec(cmd)
        args = []
        assert 'self' == argspec.args[0]
        for a in argspec.args[1:]:
            args.append(getattr(opts, a))
        if argspec.varargs is not None:
            args.extend(getattr(opts, argspec.varargs))
        try:
            cmd(*args)
        except CommandExecutionException as e:
            if e.stdout:
                print(e.stdout, file=sys.stdout)
            if e.stderr:
                print(e.stderr, file=sys.stderr)
            error('execution failed, returned %u: %s',
                  e.exitcode, ' '.join(e.args))
            return e.exitcode
        except Exception as e:
            error('exception: %s', str(e))
            traceback.print_exc()
            return -1
        return 0


class WineHelper(Helper):

    if PY3:
        DEPENDENCIES = (
            ('Python', 'https://www.python.org/ftp/python/3.5.2/python-3.5.2.exe',
             '3873deb137833a724be8932e3ce659f93741c20b', None, ('PrependPath=1', '/S'), None),
        ) + Helper.DEPENDENCIES
    else:
        DEPENDENCIES = (
            ('Python', 'https://www.python.org/ftp/python/2.7.12/python-2.7.12.msi',
             '662142691e0beba07a0bacee48e5e93a02537ff7', None, (), None),
        ) + Helper.DEPENDENCIES

    def __init__(self):
        super(WineHelper, self).__init__()
        self._env = WineEnvironment(os.path.join(WIN_DIR, '.wine'))

    def cmd_run(self, executable, *args):
        '''run command in environment

        executable: executable to run (the executable will be automatically run with Wine when it ends with ".exe")
        args: additional arguments to pass to the executable
        '''
        super(WineHelper, self).cmd_run(executable, *args)


class Win32Helper(Helper):

    DEPENDENCIES = (
        # Install wget first, since we'll be using it for fetching some of the other dependencies.
        ('requests', 'pip:requests', None, None, (), None),
    ) + Helper.DEPENDENCIES

    def __init__(self):
        super(Win32Helper, self).__init__()
        self._env = Win32Environment()


if '__main__' == __name__:
    if sys.platform.startswith('linux'):
        h = WineHelper()
    elif sys.platform.startswith('win32'):
        h = Win32Helper()
    sys.exit(h.main(sys.argv[1:]))

