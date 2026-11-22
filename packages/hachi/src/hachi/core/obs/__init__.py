"""Observability package — trace context, event sink, and metrics facade.

Behind the ``[observability]`` config flag; all components degrade gracefully
(no-op) when tracing is not configured so the default runtime is unchanged.
"""

from hachi.core.obs.trace import TraceContext, bind, current

__all__ = ["TraceContext", "bind", "current"]
