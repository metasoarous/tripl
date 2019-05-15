#!/usr/bin/env python
import sys

try:
    from setuptools import setup, find_packages
except ImportError:
    import distribute_setup
    distribute_setup.use_setuptools()
    from setuptools import setup, find_packages

import tripl

if sys.version_info < (2, 7, 0):
    raise Exception('Python 2.7 is required.')

setup(name='tripl',
      version=tripl.__version__,
      description="""tripl is a python tool for dealing with Trip data.""",
      author='Christopher Small',
      author_email='metasoarous@gmail.com',
      url='https://github.com/metasoarous/tripl',
      packages=find_packages(),
      entry_points={
          'console_scripts': [
              'tripl = tripl.cli:main',
          ]
      },
      setup_requires=["pytest-runner"],
      tests_require=["pytest", "hypothesis"],
      )
