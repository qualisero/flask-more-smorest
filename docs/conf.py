# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

# Add project root to sys.path so Sphinx can import flask_more_smorest
sys.path.insert(0, os.path.abspath(".."))

# Import version and perms registration helpers after path setup.
from flask_more_smorest import __version__
from flask_more_smorest.perms import clear_registration, init_fms
from flask_more_smorest.perms.models import defaults as _defaults

# Register default perms models so user_schemas.py (which calls get_user_model() at
# import time) can be imported by autodoc without raising a RuntimeError.
clear_registration()
init_fms(
    user=_defaults.User,
    role=_defaults.UserRole,
    token=_defaults.Token,
    domain=_defaults.Domain,
    setting=_defaults.UserSetting,
)

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "flask-more-smorest"
copyright = "2026, Qualisero"
author = "Qualisero"
release = __version__
version = ".".join(__version__.split(".")[:2])  # Short X.Y version

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",  # Google/NumPy style docstrings
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",  # Add links to source code
    "sphinx_autodoc_typehints",
    "myst_parser",  # Support for markdown files
]

# Autosummary settings
autosummary_generate = True

# Autodoc settings
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
    # ignore-module-all: prevents re-exported __all__ members from being
    # documented in the importing module; combined with check_module this
    # skips imported classes (e.g. BaseModel in flask_more_smorest.__init__)
    # so each class is only described once — in the module that defines it.
    "ignore-module-all": True,
}
autodoc_typehints = "description"
autodoc_typehints_description_target = "documented"

templates_path = ["_templates"]
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "DOCS_ROADMAP.md",
    "crud_methods_cleanup.md",
    "readme_updates.md",
]

language = "en"

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = []

html_theme_options = {
    "navigation_depth": 4,
    "collapse_navigation": False,
    "sticky_navigation": True,
    "includehidden": True,
}

# -- Options for intersphinx extension ---------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/intersphinx.html#configuration

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "flask": ("https://flask.palletsprojects.com/en/latest/", None),
    "sqlalchemy": ("https://docs.sqlalchemy.org/en/latest/", None),
    "marshmallow": ("https://marshmallow.readthedocs.io/en/stable/", None),
}

# -- Napoleon settings for Google/NumPy docstrings ---------------------------
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = True
# ivar fields instead of .. attribute:: blocks: avoids duplicating the annotated
# attributes that autodoc already documents via undoc-members.
napoleon_use_ivar = True
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = True
napoleon_type_aliases = None
napoleon_attr_annotations = True

# -- MyST (Markdown) settings ------------------------------------------------
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
]

# Suppress forward-reference warnings for third-party names (SQLAlchemy,
# SansIOResponse, Response) that live under TYPE_CHECKING and never resolve to
# intersphinx links in this build.
# Suppress guarded_import for sqlalchemy.orm.instrumentation: SQLAlchemy's own
# TYPE_CHECKING-only relative imports inside that module can't be resolved by
# sphinx-autodoc-typehints; it's a third-party module, never fixable here.
suppress_warnings = [
    "sphinx_autodoc_typehints.forward_reference",
    "sphinx_autodoc_typehints.guarded_import",
]
