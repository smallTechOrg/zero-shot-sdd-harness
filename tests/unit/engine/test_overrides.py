"""User thickness overrides — honoured, compared against auto-sized values, warned when thinner."""

from domain.culvert import CulvertParams
from engine import size_culvert

CANONICAL = {"clear_span_m": 4.0, "clear_height_m": 3.0, "cushion_m": 2.5}
# Auto-sized references for the canonical case: top/bottom 400 mm, wall 350 mm.


def test_thinner_top_slab_override_is_honoured_but_warned():
    params = CulvertParams(**CANONICAL, top_slab_thickness_mm=250.0)

    result = size_culvert(params)

    assert result.geometry.top_slab_thickness_mm == 250.0
    assert len(result.warnings) == 1
    assert "250" in result.warnings[0]
    assert "400" in result.warnings[0]
    assert "thinner" in result.warnings[0].lower()


def test_thicker_top_slab_override_is_honoured_without_warning():
    params = CulvertParams(**CANONICAL, top_slab_thickness_mm=500.0)

    result = size_culvert(params)

    assert result.geometry.top_slab_thickness_mm == 500.0
    assert result.warnings == []


def test_override_equal_to_auto_sized_value_raises_no_warning():
    params = CulvertParams(**CANONICAL, top_slab_thickness_mm=400.0)

    result = size_culvert(params)

    assert result.geometry.top_slab_thickness_mm == 400.0
    assert result.warnings == []


def test_each_thinner_member_override_raises_its_own_warning():
    params = CulvertParams(
        **CANONICAL,
        top_slab_thickness_mm=200.0,
        bottom_slab_thickness_mm=300.0,
        wall_thickness_mm=300.0,
    )

    result = size_culvert(params)

    assert len(result.warnings) == 3
    joined = " ".join(result.warnings).lower()
    assert "top slab" in joined
    assert "bottom slab" in joined
    assert "wall" in joined


def test_overridden_field_gets_no_engine_default_assumption():
    params = CulvertParams(**CANONICAL, top_slab_thickness_mm=250.0)

    result = size_culvert(params)
    assumed_fields = {a.field for a in result.assumptions}

    assert "top_slab_thickness_mm" not in assumed_fields
    assert "bottom_slab_thickness_mm" in assumed_fields
    assert "wall_thickness_mm" in assumed_fields


def test_external_dimensions_follow_the_overridden_thicknesses():
    params = CulvertParams(
        **CANONICAL,
        top_slab_thickness_mm=500.0,
        bottom_slab_thickness_mm=500.0,
        wall_thickness_mm=400.0,
    )

    g = size_culvert(params).geometry

    assert g.external_width_m == 4.8  # 4.0 + 2 * 0.4
    assert g.external_height_m == 4.0  # 3.0 + 0.5 + 0.5
