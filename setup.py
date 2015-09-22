from setuptools import setup

from pyspi import __version__

setup(
    name='pyspi',
    version=__version__,
    packages=['pyspi'],
    author='Paul Scott <paul.scotto@gmail.com>',
    install_requires=['github3.py >0.9.0,<1.0.0'],
    entry_points={
        'console_scripts': [
            'pyspi = pyspi.__main__:main'
        ],
        'pyspi_origin_types': [
            'github = pyspi.origin.github:GithubOrigin',
            'pypi = pyspi.origin.pypi:PyPIOrigin',
        ]
    }
)
