"""This module serves as documentation of the classes that you can implement
new package sources (origins) with, and you should not extend any of the
classes within this module.

To register your own Origin implementation you must specify a
"pyspi_origin_types" entry_point of some form similar to:

    setup(name='my_package', ...
          entry_points={
              'pyspi_origin_types': [
                  'my_origin_type = my_package:MyOrigin'
              ]
          })

where my_package.MyOrigin is a callable that returns an object implementing the
methods as documented here (e.g. a class reference, or a regular function) in
pyspi.interface.Origin, and 'my_origin_type' is the type specified in the
origins config file. For example:

    # ORIGIN TYPE SPEC...
    my_origin my_origin_type ...

which would then be referenced from the packages config file as:

    # PACKAGE ORIGIN SPEC...
    my_package my_origin ...

TODO: Add some methods to the Origin for getting documentation blocks.
"""


def iface(cls):
    """Interfaces are for documentation purposes only."""
    return None


@iface
class Origin(object):
    """The Origin is the main entry-point for a python package source.

    Args:
        name: The name given this instance of the Origin.
        auth: The authentication-info store for this origin.
        spec: Additional info the user has specified to identify the source.
            The spec is any trailing arguments specified in the origins config
            file, from lines of format "ORIGIN TYPE [SPEC...]".

    Raises:
        pyspi.OriginConfigError if the spec is not properly formatted.
    """
    def __init__(self, name, auth, spec):
        raise NotImplemented

    def __repr__(self):
        raise NotImplemented

    def package(self, name, spec):
        """
        Returns:
            An object conforming to pyspi.interface.Package.
        """
        raise NotImplemented

    def authenticate(self):
        """(Optional)
        """
        pass


@iface
class Package(object):
    def __init__(self):
        #: The name of the python package.
        self.name = None
        #: The URL at which the user can learn more about the package.
        self.url = None
        #: The origin from which the package is available.
        self.origin = None

    def iter_assets(self):
        raise NotImplemented

    def publish(self, assets):
        """(Optional)

        Args:
            assets: A list of pyspi.PublishAsset objects that represent what
                the user wants to publish to the origin.

        Raises:
            # TODO: An exception describing the lack of authentication?
        """
        pass
