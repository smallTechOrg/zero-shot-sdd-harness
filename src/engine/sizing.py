"""Phase-1 sizing subset of the IRS design engine (spec/capabilities/irs-engine.md).

Deterministic closed-form sizing: member thicknesses (RDSO family proportions,
honouring user overrides), external dimensions, and barrel length. Pure Python —
no LLM, no DB, no file I/O. Load cases, frame analysis and IRS CBC member checks
land in Phase 2.
"""

from pydantic import BaseModel

from domain.culvert import Assumption, BoxGeometry, CalcStep, CulvertParams
from engine.defaults import (
    CITATION_BOX_GEOMETRY,
    CITATION_BRIDGE_MANUAL,
    CITATION_RDSO_FAMILY,
    CITATION_USER_INPUT,
    MIN_MEMBER_THICKNESS_MM,
    SLAB_SPAN_DIVISOR,
    WALL_OPENING_DIVISOR,
    auto_slab_thickness_mm,
    auto_wall_thickness_mm,
)
from engine.trail import TrailRecorder

_SLAB_FORMULA = (
    f"t = ceil50(max(1000 * L / {SLAB_SPAN_DIVISOR:g}, {MIN_MEMBER_THICKNESS_MM:g} mm))"
)
_WALL_FORMULA = (
    f"t = ceil50(max(1000 * max(L, H) / {WALL_OPENING_DIVISOR:g}, {MIN_MEMBER_THICKNESS_MM:g} mm))"
)


class SizingResult(BaseModel):
    """Everything `engine.size_culvert` returns — geometry plus its full provenance."""

    geometry: BoxGeometry
    assumptions: list[Assumption]
    trail: list[CalcStep]
    warnings: list[str]


def size_culvert(params: CulvertParams) -> SizingResult:
    """Size a single-cell box: thicknesses, external dims, barrel length — fully traced."""
    trail = TrailRecorder()
    assumptions: list[Assumption] = []
    warnings: list[str] = []

    trail.record(
        description="Clear span of the box (inside face of wall to inside face of wall)",
        formula="L = clear_span_m (user requirement)",
        inputs={"clear_span_m": params.clear_span_m},
        value=params.clear_span_m,
        unit="m",
        citation=CITATION_USER_INPUT,
    )
    trail.record(
        description="Clear height of the box (top slab soffit to bottom slab top)",
        formula="H = clear_height_m (user requirement)",
        inputs={"clear_height_m": params.clear_height_m},
        value=params.clear_height_m,
        unit="m",
        citation=CITATION_USER_INPUT,
    )
    trail.record(
        description="Cushion — fill from top of top slab to formation level",
        formula="c = cushion_m (user requirement)",
        inputs={"cushion_m": params.cushion_m},
        value=params.cushion_m,
        unit="m",
        citation=CITATION_USER_INPUT,
    )

    top_slab_mm = _resolve_member_thickness(
        field="top_slab_thickness_mm",
        label="Top slab thickness",
        override_mm=params.top_slab_thickness_mm,
        sized_mm=auto_slab_thickness_mm(params.clear_span_m),
        sizing_formula=_SLAB_FORMULA,
        sizing_inputs={"clear_span_m": params.clear_span_m},
        trail=trail,
        assumptions=assumptions,
        warnings=warnings,
    )
    bottom_slab_mm = _resolve_member_thickness(
        field="bottom_slab_thickness_mm",
        label="Bottom slab thickness",
        override_mm=params.bottom_slab_thickness_mm,
        # RDSO family practice: bottom slab matched to the top slab.
        sized_mm=auto_slab_thickness_mm(params.clear_span_m),
        sizing_formula=_SLAB_FORMULA + " (bottom slab matched to top slab)",
        sizing_inputs={"clear_span_m": params.clear_span_m},
        trail=trail,
        assumptions=assumptions,
        warnings=warnings,
    )
    wall_mm = _resolve_member_thickness(
        field="wall_thickness_mm",
        label="Wall thickness",
        override_mm=params.wall_thickness_mm,
        sized_mm=auto_wall_thickness_mm(params.clear_span_m, params.clear_height_m),
        sizing_formula=_WALL_FORMULA,
        sizing_inputs={
            "clear_span_m": params.clear_span_m,
            "clear_height_m": params.clear_height_m,
        },
        trail=trail,
        assumptions=assumptions,
        warnings=warnings,
    )

    haunch_mm = trail.record(
        description="Haunch leg size at each inside corner (45-degree, both legs equal)",
        formula="h = haunch_mm (150 mm standard detail unless specified)",
        inputs={"haunch_mm": params.haunch_mm},
        value=params.haunch_mm,
        unit="mm",
        citation=CITATION_RDSO_FAMILY,
    )

    external_width_m = trail.record(
        description="External (overall) width of the box",
        formula="W_ext = L + 2 * t_wall / 1000",
        inputs={"clear_span_m": params.clear_span_m, "wall_thickness_mm": wall_mm},
        value=round(params.clear_span_m + 2 * wall_mm / 1000.0, 3),
        unit="m",
        citation=CITATION_BOX_GEOMETRY,
    )
    external_height_m = trail.record(
        description="External (overall) height of the box",
        formula="H_ext = H + (t_top + t_bottom) / 1000",
        inputs={
            "clear_height_m": params.clear_height_m,
            "top_slab_thickness_mm": top_slab_mm,
            "bottom_slab_thickness_mm": bottom_slab_mm,
        },
        value=round(
            params.clear_height_m + (top_slab_mm + bottom_slab_mm) / 1000.0, 3
        ),
        unit="m",
        citation=CITATION_BOX_GEOMETRY,
    )

    fill_at_base_m = trail.record(
        description="Height of fill from the underside of the box to formation level",
        formula="D = c + H_ext",
        inputs={"cushion_m": params.cushion_m, "external_height_m": external_height_m},
        value=round(params.cushion_m + external_height_m, 3),
        unit="m",
        citation=CITATION_BRIDGE_MANUAL,
    )
    barrel_length_m = trail.record(
        description="Barrel length of the box along the track axis",
        formula="L_barrel = W_formation + 2 * s * D",
        inputs={
            "formation_width_m": params.formation_width_m,
            "side_slope_h_per_v": params.side_slope_h_per_v,
            "fill_at_base_m": fill_at_base_m,
        },
        value=round(
            params.formation_width_m + 2 * params.side_slope_h_per_v * fill_at_base_m, 2
        ),
        unit="m",
        citation=CITATION_BRIDGE_MANUAL,
    )
    assumptions.append(
        Assumption(
            field="barrel_length_m",
            value=barrel_length_m,
            source="engine_default",
            note=(
                f"Barrel length computed from formation width {params.formation_width_m:g} m "
                f"and {params.side_slope_h_per_v:g}H:1V side slopes over {fill_at_base_m:g} m "
                f"of fill at the box base — {CITATION_BRIDGE_MANUAL}."
            ),
        )
    )

    geometry = BoxGeometry(
        clear_span_m=params.clear_span_m,
        clear_height_m=params.clear_height_m,
        cushion_m=params.cushion_m,
        top_slab_thickness_mm=top_slab_mm,
        bottom_slab_thickness_mm=bottom_slab_mm,
        wall_thickness_mm=wall_mm,
        haunch_mm=haunch_mm,
        external_width_m=external_width_m,
        external_height_m=external_height_m,
        barrel_length_m=barrel_length_m,
    )
    return SizingResult(
        geometry=geometry, assumptions=assumptions, trail=trail.steps, warnings=warnings
    )


def _resolve_member_thickness(
    *,
    field: str,
    label: str,
    override_mm: float | None,
    sized_mm: float,
    sizing_formula: str,
    sizing_inputs: dict[str, float],
    trail: TrailRecorder,
    assumptions: list[Assumption],
    warnings: list[str],
) -> float:
    """Adopt the auto-sized thickness, or honour a user override (warning when thinner)."""
    if override_mm is None:
        trail.record(
            description=f"{label} — auto-sized",
            formula=sizing_formula,
            inputs=sizing_inputs,
            value=sized_mm,
            unit="mm",
            citation=CITATION_RDSO_FAMILY,
        )
        assumptions.append(
            Assumption(
                field=field,
                value=sized_mm,
                source="engine_default",
                note=(
                    f"Auto-sized {label.lower()}: {sizing_formula} = {sized_mm:g} mm, "
                    f"per {CITATION_RDSO_FAMILY}."
                ),
            )
        )
        return sized_mm

    trail.record(
        description=f"{label} — user override (auto-sized reference {sized_mm:g} mm)",
        formula=f"t = user override; auto-size reference: {sizing_formula}",
        inputs={**sizing_inputs, "override_mm": override_mm, "auto_sized_mm": sized_mm},
        value=override_mm,
        unit="mm",
        citation=CITATION_RDSO_FAMILY,
    )
    if override_mm < sized_mm:
        warnings.append(
            f"{label} override {override_mm:g} mm is thinner than the auto-sized "
            f"{sized_mm:g} mm ({CITATION_RDSO_FAMILY}) — possible under-design; "
            "member checks will verify it."
        )
    return override_mm
