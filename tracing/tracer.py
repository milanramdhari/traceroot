import time
import functools    
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional
from nanoid import generate


from tracing.span import Span
from tracing.trace import Trace


# Context variables holding the active trace and span for the current execution
_active_trace: ContextVar[Optional[Trace]] = ContextVar("_active_trace", default=None)
_active_span: ContextVar[Optional[Span]] = ContextVar("_active_span", default=None)


def get_active_span() -> Optional[Span]:
    return _active_span.get()


def get_active_trace() -> Optional[Trace]:
    return _active_trace.get()


def _now() -> str:
    return time.time()


def start_trace() -> Trace:
    trace = Trace(
        trace_id=generate(size=8),
        started_at=_now(),
    )
    _active_trace.set(trace)
    return trace


def finish_trace(trace: Trace, final_output: Optional[dict] = None, error: Optional[str] = None) -> Trace:
    trace.finished_at = _now()
    trace.final_output = final_output

    if error:
        trace.status = "failure"
    else:
        confidences = [s.confidence for s in trace.spans if s.confidence is not None]
        if any(s.error for s in trace.spans):
            trace.status = "failure"
        elif confidences and min(confidences) < 3:
            trace.status = "degraded"
        else:
            trace.status = "success"
    return trace


def instrument(step_name: str):
    """
    Decorator that wraps a pipeline step function with span tracing.
    Usage: @instrument("extraction")
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            span = Span(
                step=step_name,
                started_at=_now(),
                input=_serialize_args(args, kwargs),
            )
            token = _active_span.set(span)
            t0 = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
                span.output = result
                return result
            except Exception as exc:
                span.error = str(exc)
                raise
            finally:
                span.latency_ms = (time.perf_counter() - t0) * 1000
                _active_span.reset(token)
                trace = _active_trace.get()
                if trace is not None:
                    trace.spans.append(span)
        return wrapper
    return decorator


def _serialize_args(args, kwargs) -> dict:
    """Best-effort serialization of function arguments for the span input."""
    result = {}
    if args:
        result["args"] = [_safe_serialize(a) for a in args]
    if kwargs:
        result["kwargs"] = {k: _safe_serialize(v) for k, v in kwargs.items()}
    return result


def _safe_serialize(val):
    if isinstance(val, (str, int, float, bool, type(None))):
        return val
    if isinstance(val, dict):
        return val
    if isinstance(val, (list, tuple)):
        return list(val)
    return str(val)
