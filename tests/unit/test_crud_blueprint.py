from __future__ import annotations

import pytest

from flask_more_smorest import CRUDBlueprint, CRUDMethod


def test_normalize_methods_from_list() -> None:
    normalized = CRUDBlueprint._normalize_methods(None, [CRUDMethod.INDEX, CRUDMethod.GET])  # type: ignore[arg-type]
    assert sorted(normalized.keys()) == [CRUDMethod.GET, CRUDMethod.INDEX]
    assert all(config == {} for config in normalized.values())


def test_normalize_methods_from_mapping() -> None:
    raw = {
        "GET": True,
        "POST": {"admin_only": True},
        "DELETE": False,
    }
    normalized = CRUDBlueprint._normalize_methods(None, raw)  # type: ignore[arg-type]
    assert CRUDMethod.GET in normalized and normalized[CRUDMethod.GET] == {}
    assert CRUDMethod.POST in normalized and normalized[CRUDMethod.POST] == {"admin_only": True}
    assert CRUDMethod.DELETE not in normalized


def test_normalize_methods_rejects_invalid_values() -> None:
    raw = {"GET": 123}
    with pytest.raises(TypeError):
        CRUDBlueprint._normalize_methods(None, raw)  # type: ignore[arg-type]
