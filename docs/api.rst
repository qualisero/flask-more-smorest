API Reference
=============

This page provides detailed API documentation for all public modules and classes in flask-more-smorest.

Core Modules
------------

.. autosummary::
   :toctree: _autosummary
   :recursive:

   flask_more_smorest

SQLAlchemy Base Models
----------------------

.. autosummary::
   :toctree: _autosummary
   :recursive:

   flask_more_smorest.sqla.base_model
   flask_more_smorest.sqla.db

Permissions System
------------------

.. autosummary::
   :toctree: _autosummary
   :recursive:

   flask_more_smorest.perms.base_perms_model
   flask_more_smorest.perms.model_mixins
   flask_more_smorest.perms.models
   flask_more_smorest.perms.user_context
   flask_more_smorest.perms.user_blueprint
   flask_more_smorest.perms.jwt

CRUD Blueprints
---------------

.. autosummary::
   :toctree: _autosummary
   :recursive:

   flask_more_smorest.crud.crud_blueprint
   flask_more_smorest.crud.query_filtering

Blueprint Extensions
--------------------

.. autosummary::
   :toctree: _autosummary
   :recursive:

   flask_more_smorest.crud.blueprint_operationid
   flask_more_smorest.perms.perms_blueprint
   flask_more_smorest.crud.pagination

Utilities
---------

.. autosummary::
   :toctree: _autosummary
   :recursive:

   flask_more_smorest.utils
   flask_more_smorest.error.exceptions
