"""What the page needs from Python that the browser does not already have.

Loaded into Pyodide by pyodide_boot.js and run before anything imports
handlebodies.web.  Two things are missing there.

Singular is not present, so the Groebner work falls back to sympy.  That needs
no code: handlebodies looks for the binary at runtime and has always run
either way.  A surface of a degree high enough to want Singular is one to run
locally.

plotly is not present either, and is not worth carrying: the figures are only
ever serialised for the page to draw, so the handful of constructors web.py
uses are supplied here rather than fetching a multi-megabyte wheel that would
be thrown away directly after `to_plotly_json`.
"""

import json
import math
import sys
import types

import numpy as np

#: layout properties that take sub-properties, so that plotly's underscore
#: shorthand -- xaxis_title for xaxis.title -- can be spelled out.  A property
#: whose name is not one of these keeps its underscore and stays whole.
CONTAINERS = {'xaxis', 'yaxis', 'zaxis', 'scene', 'legend', 'margin',
              'title', 'font', 'camera'}


def plain(value):
    """The same value with nothing in it that ``json.dumps`` would refuse.

    Arrays become lists and numpy scalars become plain numbers.  A value that
    is not finite becomes null, which plotly draws as a break in the line --
    which is what it means: the point where a path could not be followed.
    """
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, np.ndarray):
        return plain(value.tolist())
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def expand(layout, key, value):
    """Set one layout property, spelling out the underscore shorthand."""
    head, _, rest = key.partition('_')
    if rest and head in CONTAINERS:
        inner = layout.setdefault(head, {})
        if isinstance(inner, dict):
            return expand(inner, rest, value)
    layout[key] = value


def titles(value):
    """Titles given as bare strings, written the long way plotly writes them."""
    if not isinstance(value, dict):
        return value
    return {k: {'text': v} if k == 'title' and isinstance(v, str) else titles(v)
            for k, v in value.items()}


class Trace(dict):
    """One plotly trace.

    A trace is a dictionary on the wire, and web.py reads `x` and `y` back off
    the traces of a finished figure to work out its bounds, so it has to be
    readable both ways.  Keys given as None are dropped, as plotly drops them.
    """

    def __init__(self, kind, **kw):
        super().__init__(type=kind)
        self.update({k: v for k, v in kw.items() if v is not None})

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name) from None


class Figure:
    """Traces and a layout, and nothing else that plotly's Figure would do."""

    def __init__(self, *traces):
        self.data = []
        self.layout = {}
        for trace in traces:
            self.add_trace(trace)

    def add_trace(self, trace):
        self.data.append(trace)
        return self

    def update_layout(self, **kw):
        for key, value in kw.items():
            if value is not None:
                expand(self.layout, key, value)
        return self

    def to_plotly_json(self):
        return plain({'data': list(self.data), 'layout': titles(self.layout)})


def install():
    """Put the stand-in where ``import plotly.graph_objects`` will find it.

    Named templates are left as the string web.py asks for; the page puts the
    real one back, so a 6 KB theme is not copied out of Python per figure.
    """
    if 'plotly.graph_objects' in sys.modules:
        return
    go = types.ModuleType('plotly.graph_objects')
    go.Figure = Figure
    go.Scatter = lambda **kw: Trace('scatter', **kw)
    go.Scatter3d = lambda **kw: Trace('scatter3d', **kw)
    plotly = types.ModuleType('plotly')
    plotly.graph_objects = go
    sys.modules['plotly'] = plotly
    sys.modules['plotly.graph_objects'] = go


def dispatch(path, body):
    """Answer one of the page's API calls.  JSON text in, JSON text out.

    Failures are reported the way the local server reports them rather than
    raised, so a surface that cannot be computed leaves the page standing.
    """
    install()
    from handlebodies.compute import answer
    try:
        result = answer(path, json.loads(body or '{}'))
    except Exception as exc:
        result = {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
    return json.dumps(result)
