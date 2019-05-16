from distutils.core import setup

import openelec

long_description = """
OpenElec is a prototype for a general purpose tool for creating
optimised national electricity access pathways, and finding villages
for private off-grid development. The tool has functionality for both
national- and local-level analysis. 
"""

setup(
    name='openelec',
    version=openelec.__version__,
    author='Chris Arderne',
    author_email='chris@rdrn.me',
    description='A tool for optimising electricity access pathways',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/carderne/openelec',
    packages=['openelec'],
    install_requires=[
        'flask>=1.0.2',
        'numpy>=1.14.2',
        'pandas>=0.22.0',
        'geopandas>=0.4.0',
        'shapely>=1.6.4',
        'scipy>=1.0.0',
        'scikit-learn>=0.17.1',
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
    ],
)
