// The page's back end when there is no server: the same Python the local
// tool runs, inside the browser.  It is started as soon as the page loads,
// because a surface has to be typed in before anything can be asked of it,
// and that is long enough to cover the download.
(function(){
'use strict';

const PYODIDE = '__PYODIDE_URL__';
const RUNTIME = __RUNTIME__;      // tools/browser_runtime.py, injected

const style = document.createElement('style');
style.textContent = `
#boot{position:fixed;left:50%;transform:translateX(-50%);bottom:1rem;z-index:50;
      padding:.45rem 1rem;border-radius:999px;border:1px solid var(--line);
      background:var(--panel);color:var(--muted);font-size:.85rem;
      box-shadow:0 1px 6px rgba(0,0,0,.08);transition:opacity .6s .8s}
#boot.gone{opacity:0;pointer-events:none}
#boot.bad{border-color:var(--bad);color:var(--bad);background:#fdf3f2}`;
document.head.appendChild(style);

const banner = document.createElement('div');
banner.id = 'boot';
document.body.appendChild(banner);
function say(text, state){
  banner.textContent = text;
  banner.className = state || '';
}

// The figures name their theme rather than carrying it, so that a 6 KB
// template is not copied out of Python once per plot.  It is put back here.
let THEME = null;
function themed(value){
  if (Array.isArray(value)) return value.map(themed);
  if (value && typeof value === 'object'){
    if (value.layout && value.layout.template === 'plotly_white' && THEME)
      value.layout.template = THEME;
    for (const k of Object.keys(value)) themed(value[k]);
  }
  return value;
}

function script(src){
  return new Promise((ok, no) => {
    const el = document.createElement('script');
    el.src = src;
    el.onload = ok;
    el.onerror = () => no(new Error('could not load ' + src));
    document.head.appendChild(el);
  });
}

let ready = null;
async function boot(){
  say('starting Python in the browser…');
  const [, theme] = await Promise.all([
    script(PYODIDE + 'pyodide.js'),
    fetch('plotly_white.json').then(r => r.json()).catch(() => null),
  ]);
  THEME = theme;
  const py = await loadPyodide({indexURL: PYODIDE});
  say('loading sympy and numpy…');
  await py.loadPackage(['numpy', 'sympy']);
  const zip = await fetch('handlebodies.zip').then(r => r.arrayBuffer());
  py.unpackArchive(zip, 'zip', {extractDir: '/home/pyodide'});
  // The stand-in for plotly has to be in place before anything imports
  // handlebodies.web, so it is registered before the first call, not lazily.
  py.runPython(RUNTIME + '\ninstall()\n');
  const dispatch = py.runPython('dispatch');
  say('ready', 'gone');
  return dispatch;
}

window.HANDLEBODIES_BACKEND = async function(path, body){
  try {
    const dispatch = await (ready || (ready = boot()));
    // The computation holds the only thread there is, so yield first and let
    // the button that started it paint as busy before everything stops.
    await new Promise(r => setTimeout(r, 0));
    return themed(JSON.parse(dispatch(path, body || '{}')));
  } catch (e){
    say('could not start: ' + (e.message || e), 'bad');
    return {ok: false, error: String(e.message || e)};
  }
};

ready = boot();
ready.catch(() => {});      // the error is already on the banner
})();
