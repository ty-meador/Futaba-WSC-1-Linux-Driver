# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
import os, sys, tomllib
from pathlib import Path

PYPROJECT_PATH = Path(__file__).resolve().parents[2] / 'pyproject.toml'

# Add project root for pyproject.toml and build tools
sys.path.insert(0, os.path.abspath('../tools'))
# Add src for the Futaba package
sys.path.insert(0, os.path.abspath('../src'))

# Mock dependencies
autodoc_mock_imports = [
    'usb',
    'uinput',
]

project = 'futaba-rc-driver'
copyright = '2026, Ty Meador'
author = 'Ty Meador'
# Read from pyproject.toml so the documentation cannot name a different version
# than the package it is built from
with PYPROJECT_PATH.open('rb') as pyprojectFile:
    release = tomllib.load(pyprojectFile)['project']['version']

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration


extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',  # For Google/NumPy style docstrings
    'sphinx.ext.viewcode',
]

napoleon_google_docstring = True
napoleon_numpy_docstring = False

templates_path = ['_templates']
exclude_patterns = []



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
