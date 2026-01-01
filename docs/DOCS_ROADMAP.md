# Documentation Roadmap for `flask-more-smorest`

This document outlines how to set up and maintain documentation for `flask-more-smorest`, including local Sphinx builds and Read the Docs (RTD) integration.

---

## 1. Add Sphinx-based documentation

From the project root (`/Users/dave/Projects/flask-more-smorest`):

### 1.1 Install documentation dependencies

Install Sphinx and related extensions (ideally into your dev environment):

```bash
pip install sphinx sphinx-autodoc-typehints sphinx-rtd-theme
```

You can later pin these in `pyproject.toml` or a dedicated `docs/requirements.txt`.

### 1.2 Initialize Sphinx

From the project root, run:

```bash
sphinx-quickstart docs
```

Recommended answers to the prompts:

- **Root path for the documentation**: `docs`
- **Separate source and build dirs**: `n` (keep it simple for now)
- **Project name**: `flask-more-smorest`
- **Author**: your name or organization
- **Project release**: e.g. `0.1.0` (or current version)
- **Enable autodoc**: `y`
- **Enable intersphinx**: `y` (optional, but useful)
- All other options: defaults are fine.

This will create at least:

- `docs/conf.py`
- `docs/index.rst`
- build helpers like `Makefile` / `make.bat`

---

## 2. Configure Sphinx for this project

Open `docs/conf.py` and make sure the project root is on `sys.path` so Sphinx can import `flask_more_smorest`:

```python
import os
import sys
sys.path.insert(0, os.path.abspath(".."))  # project root on sys.path
```

Enable useful extensions:

```python
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",          # Google/NumPy style docstrings
    "sphinx.ext.autosummary",
    "sphinx_autodoc_typehints",
]

autosummary_generate = True
autodoc_typehints = "description"
```

Use the Read the Docs theme:

```python
html_theme = "sphinx_rtd_theme"
```

Ensure basic metadata is correct:

```python
project = "flask-more-smorest"
```

You can also configure `copyright`, `author`, etc.

---

## 3. Add API autodoc stubs

Create `docs/api.rst` with a basic API overview that uses autosummary/autodoc:

```rst
API Reference
=============

.. autosummary::
   :toctree: _autosummary
   :recursive:

   flask_more_smorest
   flask_more_smorest.sqla.base_model
   flask_more_smorest.perms.base_perms_model
   flask_more_smorest.perms.model_mixins
   flask_more_smorest.perms.user_models
   flask_more_smorest.crud.crud_blueprint
```

Update `docs/index.rst` to include this new page:

```rst
Welcome to flask-more-smorest's documentation!
==============================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   api
```

As the project grows, you can add more pages (e.g. `getting-started.rst`, `permissions.rst`, `crud.rst`, `user-models.rst`) and include them in the toctree.

---

## 4. Build documentation locally

From the project root:

```bash
PYTHONPATH=$(pwd) sphinx-build -b html docs docs/_build/html
```

Then open:

```text
docs/_build/html/index.html
```

in your browser and verify that:

- The API reference page appears.
- Key classes like `BaseModel`, `BasePermsModel`, permission mixins, and CRUD blueprints show their docstrings properly.

If imports fail, Sphinx will show warnings/errors in the build output. Typically that means adjusting `sys.path` in `conf.py` or ensuring dependencies are installed.

---

## 5. Prepare for Read the Docs

### 5.1 Add Read the Docs configuration

Create `.readthedocs.yaml` at the project root:

```yaml
version: 2

build:
  os: ubuntu-22.04
  tools:
    python: "3.12"

sphinx:
  configuration: docs/conf.py

python:
  install:
    - method: pip
      path: .
    - method: pip
      requirements: docs/requirements.txt
```

Then create `docs/requirements.txt`:

```txt
sphinx
sphinx-autodoc-typehints
sphinx-rtd-theme
```

If your package requires additional dependencies just to be importable (e.g. Flask, SQLAlchemy, marshmallow), you can add them either:

- to `docs/requirements.txt`, or
- as extra `python.install` entries in `.readthedocs.yaml`.

### 5.2 Connect the repository on Read the Docs

1. Push the docs configuration and files to your main branch.
2. Go to https://readthedocs.org/ and log in.
3. Import the project from your Git hosting (GitHub/GitLab/etc.).
4. RTD will detect `.readthedocs.yaml` and use `docs/conf.py` to build.
5. Trigger a build and confirm it passes.

From then on, pushes to the configured branch will automatically rebuild the docs.

---

## 6. Docstring and structure guidelines

Good automated docs depend heavily on good docstrings and module layout.

### 6.1 Key classes to document well

Focus on high-level, user-facing classes and modules, for example:

- `flask_more_smorest.sqla.BaseModel`
  - Explain that it is permission-agnostic and provides CRUD + schema generation.
- `flask_more_smorest.perms.BasePermsModel`
  - Document:
    - `can_read`, `can_write`, `can_create` and their `_can_*` hooks.
    - How `bypass_perms()` and `perms_disabled` work.
    - That `get_by` enforces permissions and honors `RETURN_404_ON_ACCESS_DENIED`.
- Permission mixins in `flask_more_smorest.perms.model_mixins`:
  - `HasUserMixin`, `UserCanReadWriteMixin`, `UserOwnedResourceMixin`, etc.
- CRUD blueprints and query filtering modules:
  - `flask_more_smorest.crud.crud_blueprint.CRUDBlueprint`
  - `flask_more_smorest.crud.query_filtering` helpers.

### 6.2 Example docs structure

You can gradually add more narrative docs:

- `getting-started.rst`
  - Installation, minimal app, first CRUD blueprint.
- `permissions.rst`
  - How `BasePermsModel` works.
  - Using `User`/roles, `UserCanReadWriteMixin`, and `UserOwnedResourceMixin`.
- `crud.rst`
  - Configuring `CRUDBlueprint`, filters, pagination, and operationIds.
- `user-models.rst`
  - Custom user models, domains, roles, and tokens.

Include them in `index.rst`:

```rst
.. toctree::
   :maxdepth: 2

   getting-started
   permissions
   crud
   user-models
   api
```

---

## 7. Maintenance tips

- **Keep docstrings up to date** when changing public APIs.
- **Regenerate autosummary** when adding new modules/classes; Sphinx will do this automatically if `autosummary_generate = True`.
- **Run local builds** (`sphinx-build`) before pushing big changes to avoid RTD build failures.
- **Use versioning on RTD** if you plan multiple released versions; RTD can build docs per tag/branch.
