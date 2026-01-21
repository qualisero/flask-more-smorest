# Comparison: `User.get_current_user()` vs `User.current_user`

## Summary

**TL;DR:** `User.get_current_user()` is the **preferred and only** documented way to get the current user. `User.current_user` exists as a **private reference** to JWT's current user for internal use only and should not be used directly.

---

## User.get_current_user() - The Preferred Way

### What It Is
A **classmethod** on the `User` model (and any subclass) that provides type-safe access to the current authenticated user.

### Location
- `flask_more_smorest/perms/user_context.py` - Module-level function
- `flask_more_smorest/perms/models/user.py` - Classmethod on User model

### Implementation
```python
def get_current_user(user_type: type[UserT] | None = None) -> UserProtocol | None:
    """Get the current authenticated user."""
    state, _ = _get_state()
    get_user_func = cast(GetCurrentUserFunc | None, state.get("get_current_user_func"))

    if get_user_func is not None:
        user = get_user_func()  # Use custom getter if registered
    else:
        # Fall back to built-in JWT authentication
        from .models import _get_jwt_current_user
        user = _get_jwt_current_user()

    if user_type is not None:
        if user is None:
            return None
        if not isinstance(user, user_type):
            return None
        return user

    return user
```

### Usage
```python
# Untyped access (returns User | None)
from flask_more_smorest import User

user = User.get_current_user()
if user:
    print(f"User {user.email} is logged in")

# Typed access with custom user class
class MyUser(User):
    employee_id = mapped_column(db.String(32))

user = MyUser.get_current_user()  # Returns MyUser | None
```

### How It Works
1. **Resolution Order:**
   - Checks if a custom getter was registered via `register_user_class()`
   - Falls back to JWT authentication (`_get_jwt_current_user()`) if no custom getter

2. **Type Safety:**
   - `user_type` parameter allows getting typed access for custom User subclasses
   - `MyUser.get_current_user()` returns `MyUser | None` instead of `User | None`

3. **Delegates to Module:**
   - The classmethod calls `get_current_user()` from `user_context` module
   - Provides a clean, single source of truth for user retrieval

### Advantages
✅ **Type-safe** - Returns the exact User subclass type when used as `MyUser.get_current_user()`
✅ **Configurable** - Supports custom authentication systems via `register_user_class()`
✅ **Documented** - Official documented approach in README and docs
✅ **Single API** - One function to rule them all, no confusion

---

## User.current_user - Internal Reference Only

### What It Is
A **module-level variable** in `flask_more_smorest/perms/models/user.py` that points directly to Flask-JWT-Extended's `current_user` proxy.

### Location
- `flask_more_smorest/perms/models/user.py` - Line 32

### Implementation
```python
from flask_jwt_extended import current_user as jwt_current_user

# Set the current_user reference to JWT current user
current_user: UserProtocol = cast("UserProtocol", jwt_current_user)


def _get_jwt_current_user() -> UserProtocol | None:
    """JWT-based current user getter (private helper).

    Used as the default fallback when no custom function is registered.
    Applications should use get_current_user() from user_context instead.

    Returns:
        Current user instance if authenticated, None otherwise
    """
    try:
        verify_jwt_in_request()
    except exceptions.JWTExtendedException:
        return None
    except Exception as e:
        logger.exception("Error verifying JWT for current user: %s", e)
        return None

    # Resolve LocalProxy to get the actual user object
    try:
        resolved = current_user._get_current_object()  # type: ignore[attr-defined]
        return cast("UserProtocol | None", resolved)
    except (AttributeError, RuntimeError):
        return None
```

### Usage in Codebase
❌ **NOT exported** - Not in `__all__` of any module
❌ **Not documented** - Not mentioned in README or docs
❌ **Limited** - Only works with JWT authentication, ignores custom getters

### Why It Exists
- Provides the default JWT-based user getter
- Used internally by `User.get_current_user()` as fallback
- Allows internal code to access JWT current user without going through `get_current_user()`

### Disadvantages
❌ **Not configurable** - Bypasses custom `get_current_user()` registration
❌ **Not type-safe** - Always returns `UserProtocol`, not the actual subclass
❌ **Confusing** - Two ways to access current user (`User.current_user` vs `get_current_user()`)
❌ **Not discoverable** - Hidden in internals, not part of public API

---

## Key Differences

| Feature | `User.get_current_user()` | `User.current_user` |
|----------|---------------------------|------------------|
| **Type** | Classmethod | Module variable |
| **Access** | `User.get_current_user()` or `MyUser.get_current_user()` | `User.current_user` |
| **Return Type** | `User \| None` or `MyUser \| None` | `UserProtocol \| None` |
| **Custom Auth** | ✅ Yes (via `register_user_class()`) | ❌ No (JWT only) |
| **Type Safety** | ✅ Yes (with `user_type` parameter) | ❌ No (always `UserProtocol`) |
| **Documented** | ✅ Yes (README, docs) | ❌ No |
| **Exported** | ✅ Yes (`__all__`) | ❌ No |
| **Public API** | ✅ Yes | ❌ No (internal reference) |

---

## Examples

### ✅ Correct: Using User.get_current_user()

```python
from flask_more_smorest import User

# In permission methods
def _can_write(self, current_user) -> bool:
    if not current_user:
        return False
    return self.id == current_user.id or current_user.is_admin

# In routes
from flask_more_smorest import User

user = User.get_current_user()
if user:
    print(f"Logged in as {user.email}")
```

### ✅ Correct: Using get_current_user() with custom class

```python
from flask_more_smorest import User, get_current_user, register_user_class
from flask import session

class MyUser(User):
    employee_id = mapped_column(db.String(32))

def get_my_user() -> MyUser | None:
    user_id = session.get("user_id")
    return MyUser.query.get(user_id) if user_id else None

register_user_class(MyUser, get_current_user=get_my_user)

# Now use with type safety
user = MyUser.get_current_user()  # Returns MyUser | None
```

### ❌ Incorrect: Using User.current_user directly

```python
from flask_more_smorest import User

# This works but is NOT recommended:
user = User.current_user  # Always UserProtocol, not MyUser

# And this will fail if you register a custom getter:
register_user_class(MyUser, get_current_user=my_custom_getter)
user = User.current_user  # Still returns JWT user, ignores my_custom_getter!
```

### ⚠️  When User.current_user Might Be Used Internally

In **permission methods** (like `_can_write()`, `_can_read()`, `_can_create()`), the `current_user` parameter refers to the current authenticated user, NOT to `User.current_user`:

```python
def _can_write(self, current_user) -> bool:
    """Default write permission: users can edit their own profile.

    Args:
        current_user: The current authenticated user, or None
    """
    if not current_user:
        return False
    try:
        return self.id == current_user.id or current_user.is_admin
    except Exception:
        return False
```

This is correct - the parameter name is `current_user` but it's passed by the caller, not accessed from `User.current_user`.

---

## Recommendation

**Always use `get_current_user()` instead of `User.current_user`**

1. **Type Safety**: `MyUser.get_current_user()` returns `MyUser | None`
2. **Flexibility**: Works with custom authentication via `register_user_class()`
3. **Consistency**: Single, documented API across the codebase
4. **Future-proof**: Custom authentication systems work correctly

**`User.current_user` is only for internal use** - it's the JWT fallback used by `get_current_user()` when no custom getter is registered.

---

## Migration Guide

If you're using `User.current_user` in your code:

### Change from:
```python
from flask_more_smorest import User

user = User.current_user
```

### To:
```python
from flask_more_smorest import User

user = User.get_current_user()
```

### For custom User classes:
```python
from flask_more_smorest import User

class MyUser(User):
    employee_id = mapped_column(db.String(32))

user = MyUser.get_current_user()  # Returns MyUser | None
```

---

## Are Both Needed?

**No.** Only `get_current_user()` is needed for application code.

- `get_current_user()` - **Public API**, documented, type-safe, configurable
- `User.current_user` - **Internal reference**, used only as JWT fallback

The internal `User.current_user` reference should remain for the fallback mechanism to work, but should not be used directly in application code.
