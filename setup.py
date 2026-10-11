from setuptools import setup
from setuptools import find_packages

setup(name='mychirp',
      description='A cross-platform cross-radio programming tool',
      packages=find_packages(include=["mychirp*"]),
      include_package_data=True,
      version=0,
      url='https://chirp.danplanet.com',
      python_requires=">=3.10,<4",
      install_requires=[
          'pyserial',
          'requests',
          'yattag',
          'suds',
          'lark',
          'flet',
      ],
      extras_require={
          'wx': ['wxPython'],
      },
      entry_points={
          'console_scripts': [
              "mychirp=mychirp.fletui:run",
              "mychirp-wx=mychirp.wxui:chirpmain",
              "mychirpc=mychirp.cli.main:main",
              "experttune=mychirp.cli.experttune:main",
          ],
      },
      )
