"""Build the interactive handlebodies page for the site.

    python tools/build_web.py                      # from the pinned release
    python tools/build_web.py --source ../affine_handlebodies

The result is a directory of plain files served as they are: the page, the
handlebodies package zipped for Pyodide to unpack, and plotly's theme.  All
the computation happens in the visitor's browser, so nothing here is
precomputed and any surface can be entered.

The package is a dependency, pinned to a tag, so that work landing on its main
branch -- a heavier solver, say -- cannot reach the live site until the pin is
moved deliberately.  Build with --source to try a checkout before tagging it.
"""

import argparse
import datetime
import gzip
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
HERE = pathlib.Path(__file__).resolve().parent

REPO = 'https://github.com/ViveLeFrance/AffineHandlebodies'
#: the release the site is built from; move it deliberately
PIN = 'v0.2.1.2'

#: Pinned, because the build is only as good as the versions behind it: this
#: release carries sympy 1.13.3 and numpy 2.2.5, which the package's examples
#: are checked against.  It has no plotly, hence tools/browser_runtime.py.
PYODIDE = 'https://cdn.jsdelivr.net/pyodide/v0.28.3/full/'
MATHJAX = 'https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-svg.js'
PLOTLY = 'https://cdn.jsdelivr.net/npm/plotly.js-dist-min@{}/plotly.min.js'

#: these serve the page over HTTP and start it; neither can run in a browser,
#: and nothing the page asks for imports them
NOT_IN_BROWSER = {'app.py', '__main__.py'}


def plotly_js_version():
    """Which plotly.js the local tool renders with, so the site matches it."""
    import plotly.offline
    head = plotly.offline.get_plotlyjs()[:400]
    found = re.search(r'plotly\.js v([0-9]+\.[0-9]+\.[0-9]+)', head)
    if not found:
        raise SystemExit('could not read the bundled plotly.js version')
    return found.group(1)


def fetch(repo, tag, into):
    """Install the pinned release, and hand back the package directory."""
    print(f'  installing {repo}@{tag}')
    # --no-deps because only the source files are wanted: nothing here is
    # imported from that install, and sympy and numpy are the browser's to
    # fetch.  plotly is needed, but from the environment doing the building.
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--quiet',
                    '--no-deps', '--target', str(into), f'git+{repo}@{tag}'],
                   check=True)
    return into


def package_zip(source, dest):
    """The package, as the browser will unpack it onto its own path."""
    written = []
    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as z:
        for src in sorted((source / 'handlebodies').glob('*.py')):
            if src.name not in NOT_IN_BROWSER:
                z.write(src, f'handlebodies/{src.name}')
                written.append(src.name)
    if 'compute.py' not in written:
        raise SystemExit(f'no handlebodies package under {source}')
    return written


def page(source, vendor):
    """page.html with the browser back end appended.

    The preset placeholder is left alone: null is a blank study, which is what
    the site opens as.
    """
    html = (source / 'handlebodies' / 'page.html').read_text()
    if 'HANDLEBODIES_BACKEND' not in html:
        raise SystemExit('page.html has no api() hook -- the source is too old')
    boot = (HERE / 'pyodide_boot.js').read_text()
    boot = boot.replace('__PYODIDE_URL__', PYODIDE)
    boot = boot.replace('__RUNTIME__',
                        json.dumps((HERE / 'browser_runtime.py').read_text()))
    if not vendor:
        html = html.replace('src="plotly.min.js"',
                            f'src="{PLOTLY.format(plotly_js_version())}"')
        html = html.replace('src="tex-svg.js"', f'src="{MATHJAX}"')
    # The page has no closing body tag to slot into; it ends where its own
    # script ends, and the back end goes on after it.
    return html + f'<script>\n{boot}\n</script>\n'


def theme():
    """plotly's plotly_white template, which the page puts back into figures."""
    import plotly.io
    return plotly.io.templates['plotly_white'].to_plotly_json()


def build(out, source, tag, vendor):
    out.mkdir(parents=True, exist_ok=True)
    (out / 'index.html').write_text(page(source, vendor))
    modules = package_zip(source, out / 'handlebodies.zip')
    (out / 'plotly_white.json').write_text(json.dumps(theme(),
                                                      separators=(',', ':')))
    if vendor:
        import plotly.offline
        (out / 'plotly.min.js').write_text(plotly.offline.get_plotlyjs())
        (out / 'tex-svg.js').write_bytes(gzip.decompress(
            (source / 'handlebodies' / 'tex-svg.js.gz').read_bytes()))
    # Jekyll would otherwise decide what to do with these; Pages should not.
    (out / '.nojekyll').write_text('')
    (out / 'BUILD.txt').write_text(
        f'built {datetime.date.today()}\n'
        f'from  {tag}\n'
        f'pyodide {PYODIDE}\n'
        f'modules {" ".join(modules)}\n')
    return modules


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('outdir', nargs='?', default=ROOT / 'handlebodies',
                    type=pathlib.Path)
    ap.add_argument('--source', type=pathlib.Path,
                    help='build from this checkout instead of the pinned tag')
    ap.add_argument('--tag', default=PIN, help=f'release to build (default {PIN})')
    ap.add_argument('--repo', default=REPO,
                    help='where to fetch it from; a file:// clone works, which '
                         'is how a tag is tried before it is pushed')
    ap.add_argument('--vendor', action='store_true',
                    help='copy plotly and MathJax in rather than link a CDN')
    args = ap.parse_args(argv)

    if args.source:
        source = args.source.resolve()
        described = subprocess.run(['git', '-C', str(source), 'describe',
                                    '--always', '--dirty'],
                                   capture_output=True, text=True)
        where = f'{source} ({described.stdout.strip() or "not a checkout"})'
        build(args.outdir, source, where, args.vendor)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            source = fetch(args.repo, args.tag, pathlib.Path(tmp))
            build(args.outdir, source, f'{args.repo}@{args.tag}', args.vendor)

    total = 0
    for f in sorted(args.outdir.rglob('*')):
        if f.is_file():
            total += f.stat().st_size
            name = str(f.relative_to(args.outdir))
            print(f'  {name:<22} {f.stat().st_size/1024:6.0f} KB')
    print(f'{args.outdir}  ({total/1024:.0f} KB)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
