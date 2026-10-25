from setuptools import setup
from setuptools import find_packages

setup(name='mychirp',
      description='A cross-platform cross-radio programming tool',
      packages=find_packages(include=["mychirp*"]),
      include_package_data=True,
      version="2.0.1-beta",
      url='https://chirp.danplanet.com',
      python_requires=">=3.10,<4",
      install_requires=[
          'pyserial',
          'requests',
          'yattag',
          'suds',
          'lark',
          'PySide6',
      ],
      extras_require={},
      entry_points={
          'console_scripts': [
              "mychirp=mychirp.pysideui:run",
              "mychirpc=mychirp.cli.main:main",
              "mychirp-fw=mychirp.cli.fw:main",
              "experttune=mychirp.cli.experttune:main",
          ],
      },
      )
