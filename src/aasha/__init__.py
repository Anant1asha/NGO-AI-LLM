
from pathlib import Path as _Path
_pipeline_pkg = _Path(__file__).resolve().parents[2] / "Aasha-AI" / "aasha-pipeline-with-master-json" / "src" / "aasha"
if _pipeline_pkg.exists() and str(_pipeline_pkg) not in __path__:
    __path__.append(str(_pipeline_pkg))
