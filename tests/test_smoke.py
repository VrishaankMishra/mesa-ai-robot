"""Baseline smoke tests — prove the package imports and pytest runs green (INFRA-001)."""

import mesa


def test_package_has_version():
    assert isinstance(mesa.__version__, str)
    assert mesa.__version__


def test_subpackages_importable():
    # Each subsystem package should import without pulling in heavy/hardware deps.
    import mesa.audio  # noqa: F401
    import mesa.dashboard  # noqa: F401
    import mesa.data  # noqa: F401
    import mesa.engine  # noqa: F401
    import mesa.hardware  # noqa: F401
    import mesa.vision  # noqa: F401
