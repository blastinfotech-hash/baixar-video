from __future__ import annotations

import os

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from jinja2 import Template

from app.queueing import enqueue_download, get_job_state
from app.settings import settings
from app.yt_meta import list_formats


security = HTTPBasic(auto_error=False)


INDEX_HTML = Template(
    """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>baixar</title>
  <style>
    :root { --bg:#0b1220; --card:#121b2f; --muted:#9bb0d1; --text:#e7efff; --acc:#43d3a5; --danger:#ff6b6b; }
    body{ margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; background: radial-gradient(1200px 600px at 10% 10%, #16244b 0%, var(--bg) 60%); color:var(--text); }
    .wrap{ max-width:980px; margin:40px auto; padding:0 16px; }
    .card{ background: rgba(18,27,47,.92); border:1px solid rgba(255,255,255,.08); border-radius:14px; padding:18px; box-shadow: 0 20px 60px rgba(0,0,0,.35); }
    h1{ font-size:20px; margin:0 0 12px; letter-spacing:.4px; }
    .row{ display:flex; gap:10px; flex-wrap:wrap; }
    input, select, button{ border-radius:10px; border:1px solid rgba(255,255,255,.14); background: rgba(255,255,255,.06); color:var(--text); padding:10px 12px; }
    input{ flex:1; min-width:260px; }
    button{ cursor:pointer; background: linear-gradient(180deg, rgba(67,211,165,.22), rgba(67,211,165,.12)); border-color: rgba(67,211,165,.45); }
    button:disabled{ opacity:.55; cursor:not-allowed; }
    .muted{ color:var(--muted); font-size:13px; }
    .status{ margin-top:14px; padding:12px; border-radius:10px; background: rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.08); }
    .bar{ height:10px; background: rgba(255,255,255,.08); border-radius:999px; overflow:hidden; margin-top:8px; }
    .bar > div{ height:100%; width:0%; background: linear-gradient(90deg, var(--acc), #62a7ff); transition: width .2s ease; }
    a{ color:#8fd3ff; }
    .err{ color: var(--danger); }
    code{ color: #cfe4ff; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>baixar (uso interno)</h1>
      <div class="row">
        <input id="url" placeholder="Cole o link do YouTube aqui" />
        <button id="btnFormats">Buscar formatos</button>
      </div>

      <div style="margin-top:12px" class="row">
        <select id="modeSelect" style="min-width: 170px;">
          <option value="auto">Video (auto)</option>
          <option value="audio_mp3">Audio (mp3)</option>
        </select>
        <select id="formatSelect" style="flex:1; min-width: 360px;">
          <option value="">Primeiro busque os formatos...</option>
        </select>
        <select id="containerSelect" style="min-width: 160px;">
          <option value="mp4">MP4</option>
          <option value="mkv">MKV</option>
          <option value="webm">WEBM</option>
        </select>
        <button id="btnDownload" disabled>Baixar</button>
      </div>

      <div class="muted" style="margin-top:8px">
        Arquivos expiram em 24h para economizar espaco.
      </div>

      <div id="status" class="status" style="display:none">
        <div id="statusLine"></div>
        <div class="bar"><div id="barFill"></div></div>
        <div id="linkLine" style="margin-top:10px"></div>
      </div>
    </div>
  </div>

<script>
const elUrl = document.getElementById('url');
const btnFormats = document.getElementById('btnFormats');
const modeSelect = document.getElementById('modeSelect');
const formatSelect = document.getElementById('formatSelect');
const containerSelect = document.getElementById('containerSelect');
const btnDownload = document.getElementById('btnDownload');

const statusBox = document.getElementById('status');
const statusLine = document.getElementById('statusLine');
const barFill = document.getElementById('barFill');
const linkLine = document.getElementById('linkLine');

let cachedFormats = null;

async function readJsonResponse(res) {
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : {};
  } catch (e) {
    data = null;
  }
  if (!res.ok) {
    const msg = (data && (data.detail || data.error)) ? (data.detail || data.error) : (text || `HTTP ${res.status}`);
    throw new Error(msg);
  }
  if (data === null) {
    throw new Error('Resposta invalida do servidor');
  }
  return data;
}

function showStatus(text, pct, linkHtml, isError=false) {
  statusBox.style.display = 'block';
  statusLine.innerHTML = isError ? `<span class="err">${text}</span>` : text;
  barFill.style.width = (pct || 0) + '%';
  linkLine.innerHTML = linkHtml || '';
}

function renderFormatOptions() {
  const mode = modeSelect.value;
  const list = mode === 'audio_mp3' ? (cachedFormats?.audio_formats || []) : (cachedFormats?.video_formats || []);
  formatSelect.innerHTML = '';
  if (!cachedFormats) {
    formatSelect.innerHTML = '<option value="">Primeiro busque os formatos...</option>';
    return;
  }
  if (!list.length) {
    formatSelect.innerHTML = '<option value="">Nenhum formato encontrado</option>';
    return;
  }
  for (const f of list) {
    const opt = document.createElement('option');
    opt.value = f.format_id;
    opt.textContent = f.label;
    formatSelect.appendChild(opt);
  }
}

modeSelect.addEventListener('change', () => {
  renderFormatOptions();
});

btnFormats.addEventListener('click', async () => {
  const url = elUrl.value.trim();
  if (!url) return;

  btnFormats.disabled = true;
  btnDownload.disabled = true;
  cachedFormats = null;
  formatSelect.innerHTML = '<option value="">Carregando...</option>';
  showStatus('Buscando formatos...', 5);

  try {
    const res = await fetch('/api/formats', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({url})
    });
    const data = await readJsonResponse(res);
    cachedFormats = data;
    renderFormatOptions();
    btnDownload.disabled = false;
    showStatus(`OK: ${data.title || 'video'} - escolha e baixe`, 15);
  } catch (e) {
    formatSelect.innerHTML = '<option value="">Erro</option>';
    showStatus(e.message, 0, '', true);
  } finally {
    btnFormats.disabled = false;
  }
});

btnDownload.addEventListener('click', async () => {
  const url = elUrl.value.trim();
  const format_id = formatSelect.value;
  const container = containerSelect.value;
  const mode = modeSelect.value;

  if (!url || !format_id) return;

  btnDownload.disabled = true;
  showStatus('Enfileirando...', 20);

  try {
    const res = await fetch('/api/jobs', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({url, format_id, container, mode})
    });
    const data = await readJsonResponse(res);

    const jobId = data.job_id;
    const poll = async () => {
      const r = await fetch(`/api/jobs/${jobId}`);
      const s = await readJsonResponse(r);

      const pct = s.progress || 0;
      if (s.status === 'finished') {
        showStatus('Finalizado.', 100, `<a href="${s.download_url}">Clique para baixar</a>`);
        btnDownload.disabled = false;
        return;
      }
      if (s.status === 'failed') {
        showStatus('Falhou: ' + (s.error || 'erro desconhecido'), pct, '', true);
        btnDownload.disabled = false;
        return;
      }
      const msg = s.message ? ` - ${s.message}` : '';
      showStatus(`${s.status}${msg}`, pct);
      setTimeout(poll, 1200);
    };
    poll();
  } catch (e) {
    showStatus(e.message, 0, '', true);
    btnDownload.disabled = false;
  }
});
</script>
</body>
</html>"""
)


def optional_basic_auth(credentials: HTTPBasicCredentials = Depends(security)) -> None:
    user = (settings.basic_auth_user or "").strip()
    pw = (settings.basic_auth_pass or "").strip()
    if not user and not pw:
        return
    if not credentials or credentials.username != user or credentials.password != pw:
        raise HTTPException(status_code=401, detail="Unauthorized")


app = FastAPI()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Frontend expects JSON; keep error responses JSON even for 500s.
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error", "error": str(exc)})


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/", response_class=HTMLResponse, dependencies=[Depends(optional_basic_auth)])
def index() -> str:
    return INDEX_HTML.render()


@app.post("/api/formats", dependencies=[Depends(optional_basic_auth)])
def api_formats(payload: dict) -> dict:
    url = (payload.get("url") or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url required")
    try:
        return list_formats(url)
    except HTTPException:
        raise
    except Exception as e:
        # yt-dlp errors are common (age restriction, bot check, etc.)
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/jobs", dependencies=[Depends(optional_basic_auth)])
def api_jobs(payload: dict) -> dict:
    url = (payload.get("url") or "").strip()
    format_id = (payload.get("format_id") or "").strip()
    container = (payload.get("container") or "mp4").strip().lower()
    mode = (payload.get("mode") or "auto").strip().lower()

    if not url or not format_id:
        raise HTTPException(status_code=400, detail="url and format_id required")
    if container not in ("mp4", "mkv", "webm"):
        raise HTTPException(status_code=400, detail="invalid container")
    if mode not in ("auto", "audio_mp3"):
        raise HTTPException(status_code=400, detail="invalid mode")

    try:
        job_id = enqueue_download(url=url, format_id=format_id, container=container, mode=mode)
        return {"job_id": job_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/jobs/{job_id}", dependencies=[Depends(optional_basic_auth)])
def api_job(job_id: str) -> dict:
    state = get_job_state(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="job not found")
    return state


@app.get("/download/{job_id}", dependencies=[Depends(optional_basic_auth)])
def download(job_id: str):
    state = get_job_state(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="job not found")
    if state.get("status") != "finished":
        raise HTTPException(status_code=409, detail="job not finished")

    path = state.get("file_path")
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="file not found (maybe expired)")
    filename = os.path.basename(path)
    return FileResponse(path, filename=filename, media_type="application/octet-stream")


def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", str(settings.port))))


if __name__ == "__main__":
    main()
