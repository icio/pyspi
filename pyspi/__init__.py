import hashlib
import os
import re
import stat
from cgi import escape
from ConfigParser import RawConfigParser, NoSectionError
from itertools import groupby
from pkg_resources import iter_entry_points
from shutil import copyfile
from tempfile import NamedTemporaryFile
from textwrap import dedent


__version__ = '1.0.0'


class lazyproperty(object):  # NOQA
    """lazyproperty is a property decorator which calls the factory only once.
    Author: http://stackoverflow.com/a/6849299/123600
    """
    def __init__(self, fget):
        self.fget = fget
        self.func_name = fget.__name__

    def __get__(self, obj, cls):
        if obj is None:
            return None
        value = self.fget(obj)
        setattr(obj, self.func_name, value)
        return value


class OriginConfigError(ValueError):
    pass


class OriginNotFoundError(ValueError):
    pass


class PackageConfigError(ValueError):
    pass


class OriginAuthStore(object):
    def __init__(self, config_file):
        self.config_file = config_file
        self.config = RawConfigParser()
        self.config.read(config_file)

    def origin(self, name):
        return OriginAuth(self, name)

    def __getitem__(self, origin_name):
        try:
            return dict(self.config.items(origin_name))
        except NoSectionError:
            return {}

    def __setitem__(self, origin_name, auth):
        try:
            self.config.remove_section(origin_name)
        except NoSectionError:
            pass

        if auth:
            self.config.add_section(origin_name)
            for key, val in auth.iteritems():
                self.config.set(origin_name, key, val)

        with open(self.config_file, 'w') as f:
            self.config.write(f)

        try:
            os.chmod(self.config_file, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            print 'Unable to chmod 600 %s' % self.config_file  # TODO: Test


class OriginAuth(object):
    def __init__(self, store, name):
        self.store = store
        self.name = name

    def __getitem__(self, key):
        return self.read()[key]

    def get(self, key, default=None):
        return self.read().get(key, default)

    def read(self):
        return self.store[self.name]

    def set(self, auth=None, **kwargs):
        self.store[self.name] = dict(
            (auth.items() if auth else []) +
            kwargs.items()
        )


class OriginTypeLocator(object):
    def __init__(self, group='pyspi_origin_types'):
        self.group = group

    def __iter__(self):
        for entry in iter_entry_points(self.group):
            yield entry.name, entry.load()


class OriginFactory(object):
    def __init__(self, auth_store, types):
        self.auth_store = auth_store
        self.types = types

    def build(self, name, kind, spec):
        if kind not in self.types:
            raise OriginNotFoundError('Origin type %r unrecognised from %r' %
                                      (kind, self.types.keys()))
        return self.types[kind](name, self.auth_store.origin(name), spec)


class LineParser(object):
    def parse(self, config):
        return self.parse_lines(config.split('\n'))

    def parse_file(self, config_file):
        with open(config_file, 'r') as fp:
            for item in self.parse_fp(fp):
                yield item

    def parse_fp(self, fp):
        return self.parse_lines(iter(fp))

    def parse_lines(self, lines):
        return (
            self.parse_line(line) for line in lines
            if line.strip() and not line.lstrip().startswith('#')
        )

    def parse_line(self, line):
        raise NotImplemented


class OriginParser(LineParser):
    def __init__(self, origin_factory):
        self.origins = origin_factory

    def parse_file(self, config_file):
        try:
            for item in super(OriginParser, self).parse_file(config_file):
                yield item
        except IOError:
            return

    def parse_line(self, line):
        args = line.strip().split(None, 2)
        try:
            name, kind = args[0], args[1]
        except IndexError:
            raise OriginConfigError('Error parsing: %r' % line)
        try:
            spec = args[2]
        except IndexError:
            spec = None

        return name, self.origins.build(name, kind, spec)


def add_line_to_file(path, line):
    added = False
    comp = line.lower()

    with NamedTemporaryFile('w') as tmp:
        with open(path, 'r') as original:
            for orig_line in iter(original):
                if not added and orig_line.lower() > comp:
                    added = True
                    tmp.write(line)
                tmp.write(orig_line)
            if not added:
                tmp.write(line)
        tmp.flush()
        copyfile(tmp.name, path)


def remove_line_from_file(path, skip_pattern, flags=0):
    with NamedTemporaryFile('w') as tmp:
        with open(path, 'r') as original:
            for orig_line in iter(original):
                if not re.search(skip_pattern, orig_line, flags):
                    tmp.write(orig_line)
        tmp.flush()
        copyfile(tmp.name, path)


class OriginWriter(object):
    def __init__(self, config):
        self.config = config

    def add(self, origin, origin_type, spec):
        # Create empty file.
        if not os.path.exists(self.config):
            with open(self.config, 'w') as f:
                f.write('# ORIGIN ORIGIN_TYPE SPEC...\n')

        add_line_to_file(
            self.config,
            "\t".join((origin, origin_type, spec)) + "\n",
        )

    def remove(self, origin):
        if not os.path.exists(self.config):
            return

        remove_line_from_file(
            self.config,
            r'^%s\b' % re.escape(origin),
            re.IGNORECASE
        )


class PackageWriter(object):
    def __init__(self, config):
        self.config = config

    def add(self, pkg, origin, spec):
        # Create empty file.
        if not os.path.exists(self.config):
            with open(self.config, 'w') as f:
                f.write('# PKG ORIGIN SPEC...\n')

        add_line_to_file(
            self.config,
            "\t".join((pkg, origin, spec)) + "\n"
        )

    def remove(self, pkg):
        remove_line_from_file(
            self.config,
            r'^(%s)\b' % '|'.join(map(re.escape, pkg)),
            re.IGNORECASE
        )


class PackageFactory(object):
    def __init__(self, origins):
        self.origins = origins

    def build(self, pkg, origin, spec):
        try:
            origin = self.origins[origin]
        except KeyError:
            raise PackageConfigError(
                'Origin %r not found for package %r' % (origin, pkg)
            )

        return origin.package(pkg, spec)


class PackageParser(LineParser):
    def __init__(self, package_factory):
        self.packages = package_factory

    def parse_file(self, config_file):
        try:
            for item in super(PackageParser, self).parse_file(config_file):
                yield item
        except IOError:
            return

    def parse_line(self, line):
        args = line.strip().split(None, 2)
        try:
            package, origin = args[0], args[1]
        except IndexError:
            raise PackageConfigError('Error parsing: %r' % line)
        try:
            spec = args[2]
        except IndexError:
            spec = None

        return package, self.packages.build(package, origin, spec)


class Asset(object):
    def __init__(self, url, filename, md5=None):
        self.url = url
        self.filename = filename
        self.md5 = md5


class PublishAsset(object):
    def __init__(self, package_name, version, basename, path, md5):
        self.package_name = package_name
        self.version = version
        self.basename = basename
        self.path = path
        self.md5 = md5

    def __repr__(self):
        return '<PublishAsset %s@%s %r>' % (self.package_name, self.version,
                                            self.path)


class Publisher(object):
    def __init__(self, iter_pkgs):
        self.iter_pkgs = iter_pkgs

    def publish(self, paths):
        pkg_assets = {
            pkg_name.lower(): list(assets)
            for pkg_name, assets in groupby(
                sorted(
                    (self.publishable_asset(path) for path in paths),
                    key=lambda asset: asset.package_name.lower()
                ),
                key=lambda asset: asset.package_name.lower()
            )
        }
        for pkg_name, pkg in name_filter(self.iter_pkgs(), pkg_assets.keys()):
            pkg.publish(pkg_assets[pkg.name.lower()])

    def publishable_asset(self, path):
        basename = os.path.basename(path)
        pkg, version = self.parse_name(basename)
        return PublishAsset(
            package_name=pkg,
            version=version,
            basename=basename,
            path=path,
            md5=md5_file(path)
        )

    def parse_name(self, name):
        try:
            pkg, version, _ = name.split('-', 2)
            return pkg, version
        except ValueError:
            pass

        try:
            pkg, version = name.split('-', 1)
            version = re.search(r'^((\d+\.?)*)', version) or None
            return pkg, version
        except ValueError:
            pass

        raise ValueError("Unable to extract pkg info from file: %s" % name)


def name_filter(iterable, names=()):
    if not names:
        return iterable

    names = {name.lower() for name in names}
    return (
        (name, item) for name, item in iterable
        if name.lower() in names
    )


class SimpleRepositoryBuilder(object):
    def __init__(self, base_dir, iter_pkgs, version=__version__):
        self.base_dir = base_dir
        self.iter_pkgs = iter_pkgs
        self.version = version

    def build(self, pkgs=()):
        for name, pkg in name_filter(self.build_index_iter(), pkgs):
            self.build_pkg(pkg)

    def build_index(self):
        for _ in self.build_index_iter():
            pass

    def build_index_iter(self):
        index_file = os.path.join(self.__dir('simple'), 'index.html')
        with open(index_file, 'w') as index:
            index.write(dedent("""\
                <html>
                <head>
                    <meta name="generator" content="PySPI {version}" />
                    <meta name="api-version" value="2" />
                </head>
                <body>
            """).format(
                version=escape(self.version)
            ))
            for name, pkg in self.iter_pkgs():
                index.write(dedent("""\
                    <a href="{url}">{name}</a>
                """).format(
                    url=escape(name.lower()),
                    name=escape(name),
                ))
                yield name, pkg
            index.write(dedent("""\
                </body>
                </html>
            """))

    def build_pkg(self, pkg):
        pkg_file = os.path.join(
            self.__dir('simple', pkg.name.lower()),
            'index.html'
        )
        with open(pkg_file, 'w') as pkg_assets:
            pkg_assets.write(dedent("""\
                <html>
                <head>
                    <title>{name}</title>
                    <meta name="generator" content="PySPI {version}" />
                    <meta name="api-version" value="2" />
                </head>
                <body>
                <h1>{name} <small><a href="{url}">{url}</a></small></h1>
            """).format(
                name=escape(pkg.name),
                url=escape(pkg.url),
                version=escape(self.version),
            ))
            for asset in self.assets_filter(pkg.iter_assets()):
                pkg_assets.write(dedent("""\
                    <a href="{url}{md5_suffix}">{filename}</a><br />
                """).format(
                    url=escape(asset.url),
                    filename=escape(asset.filename),
                    md5_suffix=(
                        escape('#md5=%s' % asset.md5) if asset.md5 else ''
                    )
                ))
            pkg_assets.write(dedent("""\
                </body>
                </html>
            """))

    def __dir(self, *parts):
        pkg_dir = os.path.join(self.base_dir, *parts)
        try:
            os.makedirs(pkg_dir)
        except OSError:
            # No worries if the directory already exists.
            pass
        return pkg_dir

    def assets_filter(self, assets):
        # TODO: Should we be limiting what kinds of assets we list?
        # Obvious formats of distro are .whl, .egg, and .tar.gz. Others?
        for asset in assets:
            yield asset


def md5_file(path):
    with open(path, 'rb') as f:
        h = hashlib.md5()
        for chunk in iter(lambda: f.read(4096), ''):
            h.update(chunk)
        return h.hexdigest()
