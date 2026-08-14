"""Test defaults_module.User.has_domain_access method."""

import uuid

from flask import Flask

from flask_more_smorest.perms.models import defaults as defaults_module
from flask_more_smorest.sqla import db as sqla_db


def test_has_domain_access_with_specific_domain(unit_app: Flask, db_session: None):
    """Test has_domain_access with a specific domain ID."""
    sqla_db.create_all()

    # Create user with role for specific domain
    user = defaults_module.User(email="test@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.flush()

    domain_id = uuid.uuid4()
    role = defaults_module.UserRole(user_id=user.id, role="user", domain_id=domain_id)
    sqla_db.session.add(role)
    sqla_db.session.commit()

    # defaults_module.User should have access to their domain
    assert user.has_domain_access(domain_id) is True

    # defaults_module.User should not have access to other domain
    other_domain_id = uuid.uuid4()
    assert user.has_domain_access(other_domain_id) is False


def test_has_domain_access_with_none(unit_app: Flask, db_session: None):
    """Test has_domain_access with None (global access)."""
    sqla_db.create_all()

    user = defaults_module.User(email="test@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.flush()

    # defaults_module.User without roles should still have access to None
    assert user.has_domain_access(None) is True


def test_has_domain_access_with_wildcard(unit_app: Flask, db_session: None):
    """Test has_domain_access with wildcard role."""
    sqla_db.create_all()

    # Create user with wildcard role
    user = defaults_module.User(email="test@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.flush()

    # Role with no domain_id (represented as "*" in domain_ids)
    role = defaults_module.UserRole(user_id=user.id, role="admin", domain_id=None)
    sqla_db.session.add(role)
    sqla_db.session.commit()

    # defaults_module.User should have access to any domain
    domain_id = uuid.uuid4()
    assert user.has_domain_access(domain_id) is True
    assert user.has_domain_access(None) is True


def test_has_domain_access_multiple_domains(unit_app: Flask, db_session: None):
    """Test has_domain_access with multiple domain roles."""
    sqla_db.create_all()

    user = defaults_module.User(email="test@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.flush()

    domain1_id = uuid.uuid4()
    domain2_id = uuid.uuid4()

    role1 = defaults_module.UserRole(user_id=user.id, role="user", domain_id=domain1_id)
    role2 = defaults_module.UserRole(user_id=user.id, role="admin", domain_id=domain2_id)
    sqla_db.session.add_all([role1, role2])
    sqla_db.session.commit()

    # defaults_module.User should have access to both domains
    assert user.has_domain_access(domain1_id) is True
    assert user.has_domain_access(domain2_id) is True

    # defaults_module.User should not have access to other domain
    domain3_id = uuid.uuid4()
    assert user.has_domain_access(domain3_id) is False


def test_has_domain_access_no_roles(unit_app: Flask, db_session: None):
    """Test has_domain_access for user without roles."""
    sqla_db.create_all()

    user = defaults_module.User(email="test@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.commit()

    # defaults_module.User without roles has no domain access (except None)
    domain_id = uuid.uuid4()
    assert user.has_domain_access(domain_id) is False
    assert user.has_domain_access(None) is True


def test_domain_ids_property(unit_app: Flask, db_session: None):
    """Test domain_ids property returns correct set."""
    sqla_db.create_all()

    user = defaults_module.User(email="test@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.flush()

    domain1_id = uuid.uuid4()
    domain2_id = uuid.uuid4()

    role1 = defaults_module.UserRole(user_id=user.id, role="user", domain_id=domain1_id)
    role2 = defaults_module.UserRole(user_id=user.id, role="admin", domain_id=domain2_id)
    role3 = defaults_module.UserRole(user_id=user.id, role="superadmin", domain_id=None)  # Wildcard
    sqla_db.session.add_all([role1, role2, role3])
    sqla_db.session.commit()

    # domain_ids should contain both specific domains and wildcard
    assert domain1_id in user.domain_ids
    assert domain2_id in user.domain_ids
    assert "*" in user.domain_ids


def test_has_domain_access_docstring_examples(unit_app: Flask, db_session: None):
    """Test the examples from the has_domain_access docstring."""
    sqla_db.create_all()

    user = defaults_module.User(email="test@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.flush()

    domain_id = uuid.uuid4()
    role = defaults_module.UserRole(user_id=user.id, role="user", domain_id=domain_id)
    sqla_db.session.add(role)
    sqla_db.session.commit()

    # Example 1: Check specific domain access
    assert user.has_domain_access(domain_id) is True

    # Example 2: Global access check
    assert user.has_domain_access(None) is True
