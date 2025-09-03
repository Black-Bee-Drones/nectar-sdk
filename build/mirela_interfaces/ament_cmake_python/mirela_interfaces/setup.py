from setuptools import find_packages
from setuptools import setup

setup(
    name='mirela_interfaces',
    version='0.0.0',
    packages=find_packages(
        include=('mirela_interfaces', 'mirela_interfaces.*')),
)
