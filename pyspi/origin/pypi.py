class PyPIOrigin(object):
    def __init__(self, name, auth, spec=None):
        self.auth = auth
        self.root = spec or 'https://pypi.python.org/simple/'

    def __repr__(self):
        return '<PyPI %r>' % self.root

    def package(self, pkg):
        pass

    def publish(self, assets):
        pass


class PyPIPackage(object):
    def __init__(self, pkg, endpoint):
        self.pkg = pkg
        self.endpoint = endpoint

    @property
    def url(self):
        pass

    def iter_assets(self):
        pass

    def publish(self):
        pass
