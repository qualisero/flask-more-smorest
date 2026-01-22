"""Test domain/tenant nomenclature aliases."""

import pytest
from flask import Flask

from flask_more_smorest.error.exceptions import (
    DomainNotFoundError,
    NoDomainAccessError,
    NoTenantAccessError,
    TenantNotFoundError,
)


def test_no_domain_access_error_alias():
    """Test that NoDomainAccessError is an alias for NoTenantAccessError."""
    # Verify they are the same class
    assert NoDomainAccessError is NoTenantAccessError

    # Verify both can be raised and caught
    app = Flask(__name__)
    with app.app_context():
        with pytest.raises(NoTenantAccessError):
            raise NoDomainAccessError("Test message")

        with pytest.raises(NoDomainAccessError):
            raise NoTenantAccessError("Test message")


def test_domain_not_found_error_alias():
    """Test that DomainNotFoundError is an alias for TenantNotFoundError."""
    # Verify they are the same class
    assert DomainNotFoundError is TenantNotFoundError

    # Verify both can be raised and caught
    app = Flask(__name__)
    with app.app_context():
        with pytest.raises(TenantNotFoundError):
            raise DomainNotFoundError("Test message")

        with pytest.raises(DomainNotFoundError):
            raise TenantNotFoundError("Test message")


def test_domain_alias_error_response():
    """Test that domain aliases produce correct error responses."""
    app = Flask(__name__)
    with app.app_context():
        # Create error using domain alias
        error = NoDomainAccessError("User lacks domain access")

        # Verify title and message
        assert error.TITLE == "Tenant Access Denied"
        assert "User does not have access to this tenant" in error.message


def test_tenant_original_error_response():
    """Test that original tenant errors still work."""
    app = Flask(__name__)
    with app.app_context():
        # Create error using original name
        error = NoTenantAccessError("User lacks tenant access")

        # Verify title and message
        assert error.TITLE == "Tenant Access Denied"
        assert "User does not have access to this tenant" in error.message


def test_both_aliases_work_interchangeably():
    """Test that domain and tenant names work interchangeably."""
    app = Flask(__name__)
    with app.app_context():
        # Both should be caught by the same except clause
        errors = []

        try:
            raise NoDomainAccessError("domain error")
        except NoTenantAccessError as e:
            errors.append(str(e))

        try:
            raise NoTenantAccessError("tenant error")
        except NoDomainAccessError as e:
            errors.append(str(e))

        assert len(errors) == 2
        assert "domain error" in errors[0]
        assert "tenant error" in errors[1]
