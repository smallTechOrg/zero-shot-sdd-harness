"""Culvert domain models — the typed core the engine, drawing, 3D and graph slices share.

`CulvertParams` is the single parameter model (extraction schema, engine input,
drawing input, audit record). Field names, defaults and hard ranges are normative
per spec/data.md. `BoxGeometry`, `Assumption` and `CalcStep` are the engine's
outputs consumed by the drawing, calc-sheet and 3D-model slices.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Gauge(str, Enum):
    """Track gauge — BG (broad gauge) only in the POC."""

    BG = "BG"


class LoadingStandard(str, Enum):
    """Railway loading standard — 25t Loading-2008 only in the POC (pluggable later)."""

    T25_2008 = "25t-2008"


class ConcreteGrade(str, Enum):
    M25 = "M25"
    M30 = "M30"
    M35 = "M35"


class SteelGrade(str, Enum):
    FE415 = "Fe415"
    FE500 = "Fe500"


AssumptionSource = Literal["user", "preset", "engine_default"]


class CulvertParams(BaseModel):
    """Validated design parameters for one single-cell RCC box culvert run.

    The three critical fields (`clear_span_m`, `clear_height_m`, `cushion_m`)
    must come from the user — they carry no default. `None` on a thickness field
    means "auto-size" (the engine decides and records an Assumption).
    """

    model_config = ConfigDict(extra="forbid")

    clear_span_m: float = Field(
        ..., ge=1.0, le=8.0, description="Clear (inside) span between wall faces, m"
    )
    clear_height_m: float = Field(
        ..., ge=1.0, le=6.0, description="Clear (inside) height between slab soffits, m"
    )
    cushion_m: float = Field(
        ..., ge=0.0, le=10.0, description="Fill from top of top slab to formation level, m"
    )
    gauge: Gauge = Field(default=Gauge.BG, description="Track gauge (BG only in POC)")
    tracks: int = Field(default=1, ge=1, le=1, description="Number of tracks (1 only in POC)")
    loading_standard: LoadingStandard = Field(
        default=LoadingStandard.T25_2008, description="Railway loading standard"
    )
    concrete_grade: ConcreteGrade = Field(default=ConcreteGrade.M30)
    steel_grade: SteelGrade = Field(default=SteelGrade.FE500)
    clear_cover_mm: float = Field(default=50, ge=40, le=75, description="Clear cover to reinforcement, mm")
    soil_unit_weight_kn_m3: float = Field(
        default=18.0, ge=15, le=22, description="Unit weight of fill, kN/m³"
    )
    angle_of_friction_deg: float = Field(
        default=30.0, ge=25, le=40, description="Angle of internal friction of fill, degrees"
    )
    formation_width_m: float = Field(
        default=6.85, gt=0, description="Formation width (BG single line default), m — drives barrel length"
    )
    side_slope_h_per_v: float = Field(
        default=2.0, ge=0, description="Embankment side slope, horizontal per vertical — drives barrel length"
    )
    top_slab_thickness_mm: float | None = Field(
        default=None, description="Top slab thickness override, mm; None = auto-size"
    )
    bottom_slab_thickness_mm: float | None = Field(
        default=None, description="Bottom slab thickness override, mm; None = auto-size"
    )
    wall_thickness_mm: float | None = Field(
        default=None, description="Side wall thickness override, mm; None = auto-size"
    )
    haunch_mm: float = Field(
        default=150, ge=0, le=300, description="Haunch leg size at inside corners, mm"
    )

    @field_validator("top_slab_thickness_mm", "bottom_slab_thickness_mm", "wall_thickness_mm")
    @classmethod
    def _thickness_override_must_be_positive(cls, value: float | None) -> float | None:
        if value is not None and value <= 0:
            raise ValueError("thickness override must be a positive value in mm")
        return value


class BoxGeometry(BaseModel):
    """Fully-sized single-cell box — the one geometry source for the GA drawing,
    the 3D model, and the audit record. All `_m` fields are metres, `_mm` millimetres.
    """

    clear_span_m: float = Field(description="Clear inside opening between wall faces, m")
    clear_height_m: float = Field(description="Clear inside opening between slab soffits, m")
    cushion_m: float = Field(description="Fill from top of top slab to formation level, m")
    top_slab_thickness_mm: float = Field(description="Top slab thickness (sized or overridden), mm")
    bottom_slab_thickness_mm: float = Field(description="Bottom slab thickness (sized or overridden), mm")
    wall_thickness_mm: float = Field(description="Side wall thickness (sized or overridden), mm")
    haunch_mm: float = Field(description="45-degree haunch leg size at each inside corner (both legs equal), mm")
    external_width_m: float = Field(description="Overall box width = clear span + 2 x wall thickness, m")
    external_height_m: float = Field(
        description="Overall box height = clear height + top slab + bottom slab, m"
    )
    barrel_length_m: float = Field(
        description="Box length along the track axis = formation width + 2 x side slope x "
        "(cushion + external height), m"
    )


class Assumption(BaseModel):
    """One defaulted value made explicit — shown in the calc sheet and audit record.

    The engine only ever emits `source="engine_default"`; the graph tags
    user/preset-sourced values itself.
    """

    field: str
    value: float | int | str
    source: AssumptionSource
    note: str


class CalcStep(BaseModel):
    """One traceable computation: formula, substituted inputs, result, and citation.

    Phase 2's calc sheet renders these as the drill-down trail — no number in any
    artefact may lack a CalcStep.
    """

    step_id: str
    description: str
    formula: str
    inputs: dict[str, float | int | str]
    value: float
    unit: str
    citation: str


# Unusual-value thresholds per spec/data.md (flag and proceed — not hard limits).
SPAN_WARNING_THRESHOLD_M = 6.0
CUSHION_WARNING_THRESHOLD_M = 8.0


def unusual_value_warnings(params: CulvertParams) -> list[str]:
    """Param-level unusual-value flags per spec/data.md. The run proceeds; the UI shows them."""
    warnings: list[str] = []
    if params.clear_span_m > SPAN_WARNING_THRESHOLD_M:
        warnings.append(
            f"Clear span {params.clear_span_m:g} m exceeds {SPAN_WARNING_THRESHOLD_M:g} m — "
            "beyond the RDSO B-10152/R standard single-cell box family; the design proceeds "
            "but warrants special review."
        )
    if params.cushion_m > CUSHION_WARNING_THRESHOLD_M:
        warnings.append(
            f"Cushion {params.cushion_m:g} m exceeds {CUSHION_WARNING_THRESHOLD_M:g} m — "
            "abnormally high fill for a box culvert; the design proceeds but warrants "
            "special review."
        )
    return warnings
