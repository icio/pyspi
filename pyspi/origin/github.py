import os
import re

from github3.github import GitHub, GitHubEnterprise

from pyspi import lazyproperty, PackageConfigError, Asset


class GithubOrigin(object):
    def __init__(self, name, auth, spec=None):
        self.name = name
        self.auth = auth

        # TODO: Can enterprise be hosted at https://api.*?
        self.base_url = spec.rstrip('/') if spec else 'https://github.com'
        self.enterprise = bool(spec)
        self.__make_client()

    def __repr__(self):
        return '<Github %r>' % self.client._session.base_url

    def __make_client(self):
        token = (
            self.auth.get('token') or
            os.environ.get('%s_TOKEN' % self.name.upper())
        )
        if self.enterprise:
            self.client = GitHubEnterprise(url=self.base_url, token=token)
        else:
            self.client = GitHub(token=token)
        return self.client

    def authenticate(self):
        default = self.auth.get('token')
        if default:
            prompt = '%s API Token ("-" to reset; blank to skip): '
        else:
            prompt = '%s API Token ("-" or blank to skip): '

        target = self.base_url if self.enterprise else 'GitHub'
        token = raw_input(prompt % target).strip() or default

        if default and token == '-':
            token = None
            self.auth.set()
            self.__make_client()
            print 'Removed authentication.'
        elif not token:
            print 'Skipped authentication.'
        else:
            self.auth.set(token=token)
            client = self.__make_client()
            if token:
                print 'Authenticated as %s.' % client.user()

    def package(self, pkg, spec):
        try:
            user, repo = spec.split('/')
        except ValueError:
            raise PackageConfigError

        url = '%s/%s/%s' % (self.base_url, user, repo)
        return GithubPackage(pkg, self, url, user, repo)


class GithubPackage(object):
    """A package with installable assets attached to tagged github releases.

    Args:
        name: The name of the package.
        origin: The GithubOrigin which hosts the package repository.
        url: The project URL.
        user: The user who owns the Github repository.
        repository: The name of the GitHub repository.
    """
    def __init__(self, name, origin, url, user, repository):
        self.name = name
        self.origin = origin
        self.url = url
        self.gh_repo = (user, repository)

    def __repr__(self):
        return '<GitHubPackage %s %s>' % (self.name, self.url)

    @lazyproperty
    def repo(self):
        """The repository on which the package is hosted."""
        return self.origin.client.repository(*self.gh_repo)

    def iter_assets(self):
        """The assets which might be python package distributions."""
        for release in self.repo.iter_releases():
            for asset in release.iter_assets():
                url = asset._json_data['browser_download_url']
                yield Asset(
                    url=url,
                    filename=os.path.basename(url),
                    md5=self.extract_md5(asset.label or '')
                )

    def publish(self, assets):
        releases = {}

        # Create the releases.
        for asset in assets:
            if asset.version in releases:
                continue

            release = self.release(
                asset.version,
                title='%s Release' % asset.version
            )
            releases[asset.version] = (
                release,
                {rasset.name for rasset in release.iter_assets()}
            )

        # Upload the assets.
        for asset in assets:
            release, release_assets = releases[asset.version]
            name = asset.basename
            if name in release_assets:
                print 'Skipping %s for %s. Already exists' % (asset.path, self)
                continue  # Cowardly refusing to overwrite.

            print 'Uploading %s to %s...' % (asset.path, self)
            with open(asset.path, 'rb') as f:
                rass = release.upload_asset(
                    'application/octet-stream',
                    name,
                    f
                )
            rass.edit(name, label='%s (md5:%s)' % (name, asset.md5))
            release_assets.add(name)

    def release(self, tag_name, title, description=None):
        """Get or create a release on the package's github repo."""
        tag = self.repo.ref('tags/%s' % tag_name)
        if not tag:
            raise Exception('Could not find tag %s' % tag_name)

        for release in self.repo.iter_releases():
            if release.tag_name == tag_name:
                return release

        return self.repo.create_release(
            tag_name=tag_name,
            name=title,
            body=description,
        )

    def extract_md5(self, label):
        match = re.search(r'\(md5:([0-9a-f]{32})\)', label, re.IGNORECASE)
        return match.group(1).lower() if match else None
