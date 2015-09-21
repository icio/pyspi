import argparse
import os
from functools import partial

import pyspi

lazyproperty = pyspi.lazyproperty


def main(argv=None):
    # pyspi [-d] {init,auth,origin,pkg,build,clean}
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--dir', default='.')
    subs = parser.add_subparsers()

    # pyspi init
    init_cmd = subs.add_parser('init')
    init_cmd.set_defaults(_fn=main_init)

    # pyspi auth [ORIGIN ...]
    auth_cmd = subs.add_parser('auth')
    auth_cmd.set_defaults(_fn=main_auth)
    auth_cmd.add_argument('origin', nargs='*')

    # pyspi origin {type,list,show,add,remove}
    origin_cmd = subs.add_parser('origin')
    origin_subs = origin_cmd.add_subparsers()

    # pyspi origin type [TYPE]
    origin_type_cmd = origin_subs.add_parser('type')
    origin_type_cmd.set_defaults(_fn=main_origin_type)
    origin_type_cmd.add_argument('type', nargs='?')

    # pyspi origin list
    origin_list_cmd = origin_subs.add_parser('list')
    origin_list_cmd.set_defaults(_fn=main_origin_list)

    # pyspi origin show ORIGIN
    origin_show_cmd = origin_subs.add_parser('show')
    origin_show_cmd.set_defaults(_fn=main_origin_show)
    origin_show_cmd.add_argument('origin', nargs='+')

    # pyspi origin add ORIGIN TYPE ...
    origin_add_cmd = origin_subs.add_parser('add')
    origin_add_cmd.set_defaults(_fn=main_origin_add)
    origin_add_cmd.add_argument('origin')
    origin_add_cmd.add_argument('type')
    origin_add_cmd.add_argument('spec', nargs='*')

    # pyspi origin remove [-y] [--no-clean] ORIGIN
    origin_remove_cmd = origin_subs.add_parser('remove')
    origin_remove_cmd.set_defaults(_fn=main_origin_remove)
    origin_remove_cmd.add_argument('origin')
    origin_remove_cmd.add_argument('-y', '--yes')
    origin_remove_cmd.add_argument('--no-clean')

    # pyspi pkg {list,show,add,remove}
    pkg_cmd = subs.add_parser('pkg')
    pkg_subs = pkg_cmd.add_subparsers()

    # pyspi pkg list
    pkg_list_cmd = pkg_subs.add_parser('list')
    pkg_list_cmd.set_defaults(_fn=main_pkg_list)

    # pyspi pkg show PKG [...]
    pkg_show_cmd = pkg_subs.add_parser('show')
    pkg_show_cmd.set_defaults(_fn=main_pkg_show)
    pkg_show_cmd.add_argument('pkg', nargs='*')

    # pyspi pkg add [--no-build] PKG ORIGIN [...]
    pkg_add_cmd = pkg_subs.add_parser('add')
    pkg_add_cmd.set_defaults(_fn=main_pkg_add)
    pkg_add_cmd.add_argument('pkg')
    pkg_add_cmd.add_argument('origin')
    pkg_add_cmd.add_argument('spec', nargs='*')
    pkg_add_cmd.add_argument('--no-build')

    # pyspi pkg remove [-y] PKG [...]
    pkg_remove_cmd = pkg_subs.add_parser('remove')
    pkg_remove_cmd.set_defaults(_fn=main_pkg_remove)
    pkg_remove_cmd.add_argument('pkg', nargs='+')
    pkg_remove_cmd.add_argument('-y', '--yes')

    # pyspi publish ASSET [...]
    publish_cmd = subs.add_parser('publish')
    publish_cmd.set_defaults(_fn=main_publish)
    publish_cmd.add_argument('asset', nargs='+')

    # pyspi build [PKG ...]
    build_cmd = subs.add_parser('build')
    build_cmd.set_defaults(_fn=main_build)
    build_cmd.add_argument('pkg', nargs='*', default=[])

    # pyspi clean [PKG ...]
    clean_cmd = subs.add_parser('clean')
    clean_cmd.set_defaults(_fn=main_clean)
    clean_cmd.add_argument('pkg', nargs='*')

    args = parser.parse_args(argv)
    return args._fn(args, PySPIServices(args.dir))


class PySPIServices(object):
    def __init__(self, cwd):
        self.cwd = cwd
        self.config_origin = os.path.join(cwd, 'origins')
        self.config_pkg = os.path.join(cwd, 'packages')
        self.config_auth = os.path.join(cwd, 'auth')

    @lazyproperty
    def auth_store(self):
        return pyspi.OriginAuthStore(self.config_auth)

    @lazyproperty
    def origin_type_lookup(self):
        return pyspi.OriginTypeLocator()

    @lazyproperty
    def origin_types(self):
        return dict(list(self.origin_type_lookup))

    @lazyproperty
    def origin_factory(self):
        return pyspi.OriginFactory(self.auth_store, self.origin_types)

    @lazyproperty
    def origin_writer(self):
        return pyspi.OriginWriter(self.config_origin)

    @lazyproperty
    def origin_parser(self):
        return pyspi.OriginParser(self.origin_factory)

    @lazyproperty
    def iter_origins(self):
        return partial(self.origin_parser.parse_file, self.config_origin)

    @lazyproperty
    def origins(self):
        return dict(self.iter_origins())

    @lazyproperty
    def pkg_factory(self):
        return pyspi.PackageFactory(self.origins)

    @lazyproperty
    def pkg_writer(self):
        return pyspi.PackageWriter(self.config_pkg)

    @lazyproperty
    def pkg_parser(self):
        return pyspi.PackageParser(self.pkg_factory)

    @lazyproperty
    def iter_pkgs(self):
        return partial(self.pkg_parser.parse_file, self.config_pkg)

    @lazyproperty
    def builder(self):
        return pyspi.SimpleRepositoryBuilder(self.cwd, self.iter_pkgs)

    @lazyproperty
    def publisher(self):
        return pyspi.Publisher(self.iter_pkgs)


def main_init(args, services):
    raise NotImplemented  # TODO: Perhaps not necessary?


def main_auth(args, services):
    for name, origin in pyspi.name_filter(services.iter_origins(),
                                          args.origin):
        try:
            print 'Authenticating %s: %r' % (name, origin)
            auth = origin.authenticate
        except AttributeError:
            print '%r does not support authentication.' % origin
        else:
            auth()


def main_origin_type(args, services):
    if args.type:
        print services.origin_types[args.type]
    else:
        print services.origin_types


def main_origin_list(args, services):
    for name, origin in services.iter_origins():
        print '%s\t%r' % (name, origin)


def main_origin_show(args, services):
    for name, origin in services.origins.find(args.origin):
        # TODO: Allow origin types to offer documentation through show.
        print origin


def main_origin_add(args, services):
    spec = " ".join(args.spec)

    if args.origin in services.origins:
        raise ValueError('Origin already exists: %r' % args.origin)
    if args.type not in services.origin_types:
        raise ValueError('Unrecognised origin type: %r' % args.type)
    try:
        services.origin_factory.build(args.origin, args.type, spec)
    except pyspi.OriginConfigError:
        raise

    services.origin_writer.add(args.origin, args.type, spec)


def main_origin_remove(args, services):
    services.origin_writer.remove(args.origin)


def main_pkg_list(args, services):
    for name, pkg in services.iter_pkgs():
        print '%s\t%s\t%s' % (name, pkg.origin.name, pkg.url)


def main_pkg_show(args, services):
    for name, pkg in pyspi.name_filter(services.iter_pkgs(), args.pkg):
        print pkg


def main_pkg_add(args, services):
    services.pkg_writer.add(args.pkg, args.origin, " ".join(args.spec))
    if not args.no_build:
        services.builder.build([args.pkg])


def main_pkg_remove(args, services):
    services.pkg_writer.remove(args.pkg)


def main_publish(args, services):
    services.publisher.publish(args.asset)


def main_build(args, services):
    services.builder.build(args.pkg)


def main_clean(args, services):
    raise NotImplemented


if __name__ == '__main__':
    main()
