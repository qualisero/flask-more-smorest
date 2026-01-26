.. flask-more-smorest documentation master file

Flask-More-Smorest Documentation
=================================

.. image:: https://img.shields.io/pypi/v/flask-more-smorest.svg
   :target: https://pypi.org/project/flask-more-smorest/
   :alt: PyPI version

.. image:: https://img.shields.io/pypi/pyversions/flask-more-smorest.svg
   :target: https://pypi.org/project/flask-more-smorest/
   :alt: Python Support

.. image:: https://readthedocs.org/projects/flask-more-smorest/badge/?version=latest
   :target: https://flask-more-smorest.readthedocs.io/en/latest/
   :alt: Documentation Status (Latest)

.. image:: https://readthedocs.org/projects/flask-more-smorest/badge/?version=stable
   :target: https://flask-more-smorest.readthedocs.io/en/stable/
   :alt: Documentation Status (Stable)

.. image:: https://img.shields.io/badge/License-MIT-yellow.svg
   :target: https://opensource.org/licenses/MIT
   :alt: License: MIT

.. image:: https://img.shields.io/pypi/dm/flask-more-smorest.svg
   :target: https://pypi.org/project/flask-more-smorest/
   :alt: Downloads

Flask-More-Smorest extends **Flask-Smorest** with batteries-included CRUD blueprints, 
SQLAlchemy helpers, and an opinionated user/permission system.

Features
--------

- **Automatic CRUD endpoints** with filtering and pagination
- **Blueprint mixins** for public/admin annotations and operation IDs
- **SQLAlchemy base model** with Marshmallow schemas and permission hooks
- **Optional JWT-powered** user, role, and token models

Quick Example
-------------

.. code-block:: python

   from flask import Flask
   from flask_more_smorest import BaseModel, CRUDBlueprint, init_db
   from flask_more_smorest.perms import Api
   from flask_more_smorest.sqla import db
   from sqlalchemy.orm import Mapped, mapped_column

   app = Flask(__name__)
   app.config.update(
       SQLALCHEMY_DATABASE_URI="sqlite:///app.db",
       SECRET_KEY="secret",
       JWT_SECRET_KEY="jwt-secret",
   )

   # Define your model
   class Product(BaseModel):
       name: Mapped[str] = mapped_column(db.String(100))
       price: Mapped[float] = mapped_column(db.Float)

   init_db(app)
   api = Api(app)

   # Automatic CRUD endpoints using model class
   products = CRUDBlueprint(
       "products",
       __name__,
       model=Product,           # Use class (preferred)
       schema=Product.Schema,   # Auto-generated schema
       url_prefix="/api/products/",
   )

   api.register_blueprint(products)

This automatically creates RESTful endpoints with filtering, pagination, and permission checks.

User Authentication
-------------------

Get instant authentication with ``UserBlueprint``:

.. code-block:: python

   from flask_more_smorest import UserBlueprint
   from flask_more_smorest.perms import init_fms
   from flask_more_smorest.perms.models.defaults import (
       Domain,
       Token,
       User,
       UserRole,
       UserSetting,
   )

   # Register default models explicitly
   init_fms(
       user=User,
       role=UserRole,
       token=Token,
       domain=Domain,
       setting=UserSetting,
   )

   # Instant login and profile endpoints
   user_bp = UserBlueprint(register=False)
   api.register_blueprint(user_bp)

This provides ``POST /api/users/login/``, ``GET /api/users/me/``, and full CRUD for user management.

Documentation Contents
----------------------

.. toctree::
   :maxdepth: 2
   :caption: User Guide:

   getting-started
   configuration
   permissions
   user-extension
   custom-user-context
   demoapp-style-integration
   crud
   user-models
   testing

.. toctree::
   :maxdepth: 3
   :caption: API Reference:

   api

.. toctree::
   :maxdepth: 1
   :caption: Additional Resources:

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


