from importlib.metadata import version

from .config import ALGORITHM_VERSION, CONFIG_HASH
from .input_adapter import (
    RawInputAdapter,
    RawInputAudit,
    RawInputChunk,
    RawSourceMetadata,
)
from .pair_product import (
    ExactPairProduct,
    PairChunk,
    PairFlags,
    PairView,
    VIEW_RAW,
    VIEW_SCREENED,
    build_pair_product,
    iter_pair_chunks,
)
from .quality import (  # pyright: ignore[reportMissingImports]
    QualityComputeResult,
    VisualDiagnostics,
    VisualDiagnosticsReducer,
    bin_edges,
    build_visual_diagnostics,
    compute_quality,
    count_conservation,
    select_excerpt,
)
from .temporal import (  # pyright: ignore[reportMissingImports]
    TemporalComputeResult,
    build_temporal_sections,
    compute_temporal,
    contiguous_eligible_hour_segments,
    daily_median_aggregates,
    hourly_median_aggregates,
)

EDA_DISTRIBUTIONS = (
    "numpy",
    "pandas",
    "matplotlib",
    "scipy",
    "statsmodels",
    "ruptures",
    "scikit-learn",
    "seaborn",
)


def toolchain_versions() -> dict[str, str]:
    return {
        "algorithm": ALGORITHM_VERSION,
        **{distribution: version(distribution) for distribution in EDA_DISTRIBUTIONS},
    }


__all__ = [
    "ALGORITHM_VERSION",
    "CONFIG_HASH",
    "EDA_DISTRIBUTIONS",
    "ExactPairProduct",
    "PairChunk",
    "PairFlags",
    "PairView",
    "QualityComputeResult",
    "RawInputAdapter",
    "RawInputAudit",
    "RawInputChunk",
    "RawSourceMetadata",
    "TemporalComputeResult",
    "VIEW_RAW",
    "VIEW_SCREENED",
    "VisualDiagnostics",
    "VisualDiagnosticsReducer",
    "bin_edges",
    "build_pair_product",
    "build_temporal_sections",
    "build_visual_diagnostics",
    "compute_quality",
    "compute_temporal",
    "contiguous_eligible_hour_segments",
    "count_conservation",
    "daily_median_aggregates",
    "hourly_median_aggregates",
    "iter_pair_chunks",
    "select_excerpt",
    "toolchain_versions",
]
