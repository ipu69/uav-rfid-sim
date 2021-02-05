import pytest
from pytest import approx

from model.objects.channel import TimeValueMap, THERMAL_NOISE


def test_get_min_value_on_empty_map():
    tvm = TimeValueMap()
    assert tvm.get_min(0, 1) == approx(THERMAL_NOISE)


def test_get_min_value_from_past():
    tvm = TimeValueMap()
    tvm.record(5, -10.0)
    assert tvm.get_min(0, 1) == approx(THERMAL_NOISE)


def test_get_min_value_from_future():
    tvm = TimeValueMap()
    tvm.record(5, -10.0)
    assert tvm.get_min(5, 7) == -10.0


def test_get_min_value_from_middle():
    tvm = TimeValueMap()
    tvm.record(2, -10.0)
    tvm.record(4, -8.0)
    tvm.record(6, -9.0)

    assert tvm.get_min(1, 3) == approx(THERMAL_NOISE)
    assert tvm.get_min(2, 3) == -10.0
    assert tvm.get_min(2.1, 3) == -10.0
    assert tvm.get_min(3, 5) == -10.0
    assert tvm.get_min(4, 7) == -9.0
