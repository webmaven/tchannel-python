from setuptools import find_packages, setup

import re

version = None
with open('tchannel/__init__.py', 'r') as f:
    for line in f:
        m = re.match(r'^__version__\s*=\s*(["\'])([^"\']+)\1', line)
        if m:
            version = m.group(2)
            break

if not version:
    raise Exception(
        'Could not determine version number from tchannel/__init__.py'
    )


setup(
    name='tchannel',
    version=version,
    author=', '.join([
        'Abhinav Gupta',
        'Aiden Scandella',
        'Bryce Lampe',
        'Grayson Koonce',
        'Junchao Wu',
    ]),
    author_email='abg@uber.com',
    description='Network multiplexing and framing protocol for RPC',
    license='MIT',
    url='https://github.com/uber/tchannel-python',
    packages=find_packages(exclude=['tests', 'tests.*']),
    package_data={
        '': ['*.thrift'],
    },
    install_requires=[
        # stdlib backports, no constraints needed
        'contextlib2',

        # external deps
        'crcmod>=1,<2',
        'tornado>=4.2,<5',

        # tchannel deps
        'thriftrw>=0.4,<2',
        'threadloop>=1,<2',
    ],
    extras_require={
        'vcr': ['PyYAML', 'mock', 'wrapt'],
    },
    entry_points={
        'console_scripts': [
            'tcurl.py = tchannel.tcurl:start_ioloop'
        ]
    },
)
