#!/usr/bin/env python
import sys

try:
    from setuptools import setup, find_packages
except ImportError:
    import distribute_setup
    distribute_setup.use_setuptools()
    from setuptools import setup, find_packages

import tripy

if sys.version_info < (2, 7, 0):
    raise Exception('Python 2.7 is required.')

setup(name='tripy',
      version=tripy.__version__,
      description="""Tripy is a python tool for dealing with Trip data.""",
      author='Christopher Small',
      author_email='metasoarous@gmail.com',
      url='https://github.com/metasoarous/tripy',
      packages=find_packages(),
      entry_points={
          'console_scripts': [
              'trip = tripy.cli:main',
          ]
      },
      #test_suite='tripy.test.suite',
      #tests_require=['mock>=1.0.1']
      )
