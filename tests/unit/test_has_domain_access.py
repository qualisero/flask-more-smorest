"""Test DefaultUser.has_domain_access method."""

import uuid

from flask_more_smorest.perms.models.defaults import DefaultUser, DefaultUserRole
from flask_more_smorest.sqla import db as sqla_db


def test_has_domain_access_with_specific_domain(unit_app, db_session):
    """Test has_domain_access with a specific domain ID."""
    sqla_db.create_all()

    # Create user with role for specific domain
    user = DefaultUser(email="test@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.flush()

    domain_id = uuid.uuid4()
    role = DefaultUserRole(user_id=user.id, role="user", domain_id=domain_id)
    sqla_db.session.add(role)
    sqla_db.session.commit()

    # DefaultUser should have access to their domain
    assert user.has_domain_access(domain_id) is True

    # DefaultUser should not have access to other domain
    other_domain_id = uuid.uuid4()
    assert user.has_domain_access(other_domain_id) is False


def test_has_domain_access_with_none(unit_app, db_session):
    """Test has_domain_access with None (global access)."""
    sqla_db.create_all()

    user = DefaultUser(email="test@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.flush()

    # DefaultUser without roles should still have access to None
    assert user.has_domain_access(None) is True


def test_has_domain_access_with_wildcard(unit_app, db_session):
    """Test has_domain_access with wildcard role."""
    sqla_db.create_all()

    # Create user with wildcard role
    user = DefaultUser(email="test@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.flush()

    # Role with no domain_id (represented as "*" in domain_ids)
    role = DefaultUserRole(user_id=user.id, role="admin", domain_id=None)
    sqla_db.session.add(role)
    sqla_db.session.commit()

    # DefaultUser should have access to any domain
    domain_id = uuid.uuid4()
    assert user.has_domain_access(domain_id) is True
    assert user.has_domain_access(None) is True


def test_has_domain_access_multiple_domains(unit_app, db_session):
    """Test has_domain_access with multiple domain roles."""
    sqla_db.create_all()

    user = DefaultUser(email="test@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.flush()

    domain1_id = uuid.uuid4()
    domain2_id = uuid.uuid4()

    role1 = DefaultUserRole(user_id=user.id, role="user", domain_id=domain1_id)
    role2 = DefaultUserRole(user_id=user.id, role="admin", domain_id=domain2_id)
    sqla_db.session.add_all([role1, role2])
    sqla_db.session.commit()

    # DefaultUser should have access to both domains
    assert user.has_domain_access(domain1_id) is True
    assert user.has_domain_access(domain2_id) is True

    # DefaultUser should not have access to other domain
    domain3_id = uuid.uuid4()
    assert user.has_domain_access(domain3_id) is False


def test_has_domain_access_no_roles(unit_app, db_session):
    """Test has_domain_access for user without roles."""
    sqla_db.create_all()

    user = DefaultUser(email="test@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.commit()

    # DefaultUser without roles has no domain access (except None)
    domain_id = uuid.uuid4()
    assert user.has_domain_access(domain_id) is False
    assert user.has_domain_access(None) is True


def test_domain_ids_property(unit_app, db_session):
    """Test domain_ids property returns correct set."""
    sqla_db.create_all()

    user = DefaultUser(email="test@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.flush()

    domain1_id = uuid.uuid4()
    domain2_id = uuid.uuid4()

    role1 = DefaultUserRole(user_id=user.id, role="user", domain_id=domain1_id)
    role2 = DefaultUserRole(user_id=user.id, role="admin", domain_id=domain2_id)
    role3 = DefaultUserRole(user_id=user.id, role="superadmin", domain_id=None)  # Wildcard
    sqla_db.session.add_all([role1, role2, role3])
    sqla_db.session.commit()

    # domain_ids should contain both specific domains and wildcard
    assert domain1_id in user.domain_ids
    assert domain2_id in user.domain_ids
    assert "*" in user.domain_ids


def test_has_domain_access_docstring_examples(unit_app, db_session):
    """Test the examples from the has_domain_access docstring."""
    sqla_db.create_all()

    user = DefaultUser(email="test@example.com", password="test123")
    sqla_db.session.add(user)
    sqla_db.session.flush()

    domain_id = uuid.uuid4()
    role = DefaultUserRole(user_id=user.id, role="user", domain_id=domain_id)
    sqla_db.session.add(role)
    sqla_db.session.commit()

    # Example 1: Check specific domain access
    assert user.has_domain_access(domain_id) is True

    # Example 2: Global access check
    assert user.has_domain_access(None) is True
