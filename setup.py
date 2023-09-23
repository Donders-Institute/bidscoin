from setuptools import setup
from build_manpages import build_manpages, get_build_py_cmd, get_install_cmd

setup(cmdclass = {'build_manpages': build_manpages,
                  'build_py': get_build_py_cmd(),
                  'install': get_install_cmd()})
