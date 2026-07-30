"""
ClipForge AI - MVP em arquivo único
===================================

Executar:
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  python app.py

Dependências:
  fastapi
  uvicorn[standard]
  python-multipart
  openai
  httpx

Requisitos do sistema:
  ffmpeg e ffprobe instalados no PATH.

Opcional:
  OPENAI_API_KEY para análise/transcrição com OpenAI.
  Sem a chave, o sistema permite upload, cortes manuais e processamento
  básico, mas não faz seleção inteligente/transcrição por IA.

IMPORTANTE:
- O processamento deve ser usado apenas com vídeos que o usuário tenha
  autorização/direito de reutilizar.
- A publicação em YouTube/TikTok não é implementada como "login por senha".
  As rotas OAuth abaixo deixam a integração preparada para credenciais oficiais.
- Para um produto de produção, separar workers, banco, armazenamento e frontend.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


APP_NAME = "ClipForge AI"
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
JOB_DIR = DATA_DIR / "jobs"

for directory in (DATA_DIR, UPLOAD_DIR, OUTPUT_DIR, JOB_DIR):
    directory.mkdir(parents=True, exist_ok=True)

app = FastAPI(title=APP_NAME, version="0.1.0")
JOBS: dict[str, dict] = {}

MAX_UPLOAD_MB = 1024
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def ffprobe_duration(path: Path) -> float:
    result = run_cmd([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ])
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe falhou: {result.stderr[-1000:]}")
    try:
        return float(result.stdout.strip())
    except ValueError:
        raise RuntimeError("Não foi possível obter a duração do vídeo.")


def clean_filename(name: str) -> str:
    name = Path(name or "video.mp4").name
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", name)
    return name[:180]


def update_job(job_id: str, **values):
    JOBS.setdefault(job_id, {}).update(values)
    (JOB_DIR / f"{job_id}.json").write_text(
        json.dumps(JOBS[job_id], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_job(job_id: str) -> dict:
    if job_id in JOBS:
        return JOBS[job_id]
    file = JOB_DIR / f"{job_id}.json"
    if file.exists():
        data = json.loads(file.read_text(encoding="utf-8"))
        JOBS[job_id] = data
        return data
    raise HTTPException(404, "Projeto não encontrado.")


def get_openai_client():
    key = os.getenv("OPENAI_API_KEY")
    if not key or OpenAI is None:
        return None
    return OpenAI(api_key=key)


def parse_json_from_model(text: str):
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text, flags=re.I).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}|\[.*\]", text, flags=re.S)
        if match:
            return json.loads(match.group(0))
    raise ValueError("A IA não retornou JSON válido.")


def make_candidate_windows(duration: float, target: int) -> list[dict]:
    """
    Fallback determinístico quando não existe IA.
    Gera janelas distribuídas pelo vídeo, mas não afirma que sejam 'virais'.
    """
    if duration <= 0:
        return []

    length = min(max(target, 10), 180)
    if duration <= length:
        return [{"start": 0.0, "end": duration, "score": 50}]

    max_start = max(0.0, duration - length)
    count = min(30, max(5, int(duration // max(10, length // 2))))
    count = max(1, count)

    windows = []
    for i in range(count):
        start = (max_start * i) / max(1, count - 1)
        windows.append({
            "start": round(start, 3),
            "end": round(min(duration, start + length), 3),
            "score": 50,
        })
    return windows


def cut_video(
    source: Path,
    destination: Path,
    start: float,
    end: float,
    vertical: bool = True,
):
    duration = max(0.1, end - start)

    # Escala vertical com crop central. Para produção, trocar por tracking
    # de rosto/objeto usando OpenCV/YOLO ou serviço equivalente.
    if vertical:
        vf = (
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920"
        )
    else:
        vf = "scale=1920:-2"

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(max(0, start)),
        "-i", str(source),
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "21",
        "-c:a", "aac",
        "-b:a", "160k",
        "-movflags", "+faststart",
        str(destination),
    ]

    result = run_cmd(cmd)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-2500:])


def make_srt_placeholder(start: float, end: float, text: str, path: Path):
    """
    Legenda mínima. A versão com sincronização palavra-a-palavra pode ser
    gerada quando houver transcrição real.
    """
    def fmt(sec):
        sec = max(0, float(sec))
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        ms = int(round((sec - int(sec)) * 1000))
        if ms >= 1000:
            s += 1
            ms = 0
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    path.write_text(
        f"1\n{fmt(0)} --> {fmt(end-start)}\n{text or ' '}\n",
        encoding="utf-8",
    )


async def transcribe_with_openai(path: Path) -> dict:
    client = get_openai_client()
    if client is None:
        return {"text": "", "segments": []}

    # A API de transcrição aceita arquivo de áudio/vídeo conforme o modelo
    # disponível na conta. Usamos um modelo atual configurável por ambiente.
    model = os.getenv("OPENAI_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe")

    def call():
        with path.open("rb") as audio:
            response = client.audio.transcriptions.create(
                model=model,
                file=audio,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )
        segments = []
        raw_segments = getattr(response, "segments", None) or []
        for seg in raw_segments:
            if isinstance(seg, dict):
                segments.append(seg)
            else:
                segments.append({
                    "start": getattr(seg, "start", 0),
                    "end": getattr(seg, "end", 0),
                    "text": getattr(seg, "text", ""),
                })
        return {
            "text": getattr(response, "text", "") or "",
            "segments": segments,
        }

    return await asyncio.to_thread(call)


async def rank_candidates_with_ai(transcript: dict, duration: float, target: int, amount: int):
    client = get_openai_client()
    segments = transcript.get("segments", [])

    if client is None or not segments:
        return make_candidate_windows(duration, target)

    compact = []
    for s in segments:
        compact.append({
            "start": round(float(s.get("start", 0)), 2),
            "end": round(float(s.get("end", 0)), 2),
            "text": str(s.get("text", ""))[:500],
        })

    prompt = f"""
Você é um editor de vídeos curtos.
Analise a transcrição com timestamps abaixo e encontre trechos independentes
com alto potencial de retenção. O usuário quer aproximadamente {target}
segundos por corte e deseja até {amount} cortes.

REGRAS:
- Não invente falas.
- Não corte uma frase no meio.
- O trecho deve ter contexto suficiente.
- Prefira ganchos fortes no começo.
- Evite trechos repetidos.
- Use somente timestamps presentes na transcrição.
- Gere mais candidatos do que a quantidade solicitada quando possível.
- Dê uma nota de 0 a 100.
- Retorne SOMENTE JSON.

Formato:
[
  {{
    "start": 123.4,
    "end": 183.1,
    "score": 94,
    "reason": "motivo curto",
    "hook": "gancho curto"
  }}
]

TRANSCRIÇÃO:
{json.dumps(compact, ensure_ascii=False)}
"""

    def call():
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_ANALYSIS_MODEL", "gpt-4o-mini"),
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": "Você é um editor especializado em short-form video.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        return parse_json_from_model(response.choices[0].message.content or "[]")

    try:
        result = await asyncio.to_thread(call)
        if isinstance(result, dict):
            result = result.get("candidates", [])
        candidates = []
        for item in result:
            start = float(item["start"])
            end = float(item["end"])
            if end <= start:
                continue
            candidates.append({
                "start": max(0, start),
                "end": min(duration, end),
                "score": float(item.get("score", 50)),
                "reason": item.get("reason", ""),
                "hook": item.get("hook", ""),
            })
        if candidates:
            return candidates
    except Exception as exc:
        print("Falha na análise por IA:", exc)

    return make_candidate_windows(duration, target)


def select_top_candidates(candidates: list[dict], amount: int, target: int):
    # Ordena por score e evita sobreposição forte.
    candidates = sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)
    selected = []

    for c in candidates:
        start, end = float(c["start"]), float(c["end"])
        overlap = False

        for s in selected:
            a, b = s["start"], s["end"]
            intersection = max(0, min(end, b) - max(start, a))
            union = max(end, b) - min(start, a)
            if union and intersection / union > 0.45:
                overlap = True
                break

        if not overlap:
            c = dict(c)
            c["start"] = round(start, 3)
            c["end"] = round(end, 3)
            c["duration"] = round(end - start, 2)
            selected.append(c)

        if len(selected) >= amount:
            break

    return selected


async def process_project(job_id: str):
    job = load_job(job_id)
    source = Path(job["source"])
    amount = job["amount"]
    target = job["target_duration"]

    try:
        update_job(job_id, status="processando", progress=5, message="Verificando vídeo")
        if not command_exists("ffmpeg") or not command_exists("ffprobe"):
            raise RuntimeError(
                "FFmpeg/ffprobe não encontrados. Instale o FFmpeg no sistema."
            )

        duration = ffprobe_duration(source)
        update_job(
            job_id,
            duration=duration,
            progress=15,
            message="Transcrevendo e analisando conteúdo",
        )

        transcript = await transcribe_with_openai(source)

        transcript_file = JOB_DIR / f"{job_id}_transcript.json"
        transcript_file.write_text(
            json.dumps(transcript, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        candidates = await rank_candidates_with_ai(
            transcript, duration, target, amount
        )

        selected = select_top_candidates(candidates, amount, target)

        if not selected:
            raise RuntimeError("Nenhum candidato de corte foi encontrado.")

        update_job(
            job_id,
            progress=35,
            message=f"{len(selected)} cortes selecionados",
            candidates=candidates,
            selected=selected,
        )

        outputs = []
        total = len(selected)

        for index, candidate in enumerate(selected, 1):
            destination = OUTPUT_DIR / f"{job_id}_corte_{index:02d}.mp4"
            cut_video(
                source,
                destination,
                candidate["start"],
                candidate["end"],
                vertical=True,
            )

            # Se houver transcrição, montar legenda SRT simples com o texto
            # correspondente. Para animação palavra-a-palavra, a próxima etapa
            # pode renderizar ASS/Karaoke via FFmpeg.
            text = ""
            if transcript.get("segments"):
                parts = []
                for seg in transcript["segments"]:
                    ss = float(seg.get("start", 0))
                    ee = float(seg.get("end", 0))
                    if ee >= candidate["start"] and ss <= candidate["end"]:
                        parts.append(str(seg.get("text", "")))
                text = " ".join(parts).strip()

            srt = OUTPUT_DIR / f"{job_id}_corte_{index:02d}.srt"
            make_srt_placeholder(
                candidate["start"],
                candidate["end"],
                text,
                srt,
            )

            outputs.append({
                "index": index,
                "file": f"/outputs/{destination.name}",
                "subtitle": f"/outputs/{srt.name}",
                "start": candidate["start"],
                "end": candidate["end"],
                "duration": candidate["duration"],
                "score": candidate.get("score", 0),
                "reason": candidate.get("reason", ""),
                "hook": candidate.get("hook", ""),
            })

            progress = 35 + int(index / total * 60)
            update_job(
                job_id,
                progress=progress,
                message=f"Renderizando corte {index}/{total}",
                outputs=outputs,
            )

        update_job(
            job_id,
            status="concluido",
            progress=100,
            message="Todos os cortes foram processados.",
            outputs=outputs,
        )

    except Exception as exc:
        update_job(
            job_id,
            status="erro",
            progress=100,
            message=str(exc),
        )


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(INDEX_HTML)


@app.get("/health")
def health():
    return {
        "ok": True,
        "app": APP_NAME,
        "ffmpeg": command_exists("ffmpeg"),
        "ffprobe": command_exists("ffprobe"),
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
    }


@app.post("/api/projects")
async def create_project(
    video: UploadFile = File(...),
    amount: int = Form(5),
    target_duration: int = Form(60),
):
    if amount < 1 or amount > 100:
        raise HTTPException(400, "A quantidade deve estar entre 1 e 100.")

    if target_duration < 10 or target_duration > 180:
        raise HTTPException(400, "A duração deve estar entre 10 e 180 segundos.")

    filename = clean_filename(video.filename)
    suffix = Path(filename).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            "Formato não suportado. Use MP4, MOV, MKV, WEBM, AVI ou M4V.",
        )

    job_id = uuid.uuid4().hex
    source = UPLOAD_DIR / f"{job_id}_{filename}"

    size = 0
    with source.open("wb") as f:
        while True:
            chunk = await video.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_UPLOAD_MB * 1024 * 1024:
                source.unlink(missing_ok=True)
                raise HTTPException(
                    413,
                    f"Arquivo maior que {MAX_UPLOAD_MB} MB.",
                )
            f.write(chunk)

    update_job(
        job_id,
        id=job_id,
        status="fila",
        progress=0,
        message="Projeto criado.",
        source=str(source),
        filename=filename,
        amount=amount,
        target_duration=target_duration,
    )

    asyncio.create_task(process_project(job_id))

    return {
        "job_id": job_id,
        "status": "fila",
        "message": "Processamento iniciado.",
    }


@app.get("/api/projects/{job_id}")
def project_status(job_id: str):
    return load_job(job_id)


@app.get("/outputs/{filename}")
def output_file(filename: str):
    safe = Path(filename).name
    path = OUTPUT_DIR / safe
    if not path.exists():
        raise HTTPException(404, "Arquivo não encontrado.")
    return FileResponse(path)


@app.get("/api/oauth/status")
def oauth_status():
    return {
        "youtube": {
            "configured": bool(
                os.getenv("YOUTUBE_CLIENT_ID")
                and os.getenv("YOUTUBE_CLIENT_SECRET")
            ),
            "message": "Integração OAuth oficial deve ser configurada.",
        },
        "tiktok": {
            "configured": bool(
                os.getenv("TIKTOK_CLIENT_KEY")
                and os.getenv("TIKTOK_CLIENT_SECRET")
            ),
            "message": "Integração OAuth oficial deve ser configurada.",
        },
    }


@app.get("/api/oauth/youtube/start")
def youtube_oauth_start():
    raise HTTPException(
        501,
        "Configure OAuth do YouTube com credenciais oficiais e redirect URI "
        "antes de habilitar esta rota.",
    )


@app.get("/api/oauth/tiktok/start")
def tiktok_oauth_start():
    raise HTTPException(
        501,
        "Configure OAuth do TikTok com credenciais oficiais e permissões "
        "de publicação disponíveis para sua aplicação.",
    )


INDEX_HTML = r"""
<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ClipForge AI</title>
<style>
:root{
  --bg:#0b0d12;--panel:#131722;--panel2:#1a1f2b;--text:#f5f7fb;
  --muted:#98a2b3;--line:#283041;--accent:#7c5cff;--ok:#35d07f;
  --danger:#ff5d73;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:Inter,system-ui,Arial}
header{padding:24px 5%;border-bottom:1px solid var(--line);display:flex;justify-content:space-between}
.logo{font-weight:800;font-size:22px}.logo span{color:var(--accent)}
main{max-width:1200px;margin:35px auto;padding:0 20px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:22px}
h1{font-size:38px;margin:10px 0}.muted{color:var(--muted)}
label{display:block;margin:16px 0 7px;color:#cbd2df}
input,select,button{
  width:100%;border-radius:10px;border:1px solid var(--line);
  background:var(--panel2);color:var(--text);padding:13px
}
button{background:var(--accent);border:0;font-weight:800;cursor:pointer;margin-top:16px}
button:disabled{opacity:.5;cursor:not-allowed}
.progress{height:12px;background:#252b38;border-radius:99px;overflow:hidden;margin-top:15px}
.bar{height:100%;width:0;background:var(--accent);transition:.3s}
.status{margin-top:12px;white-space:pre-wrap}
.cuts{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:15px;margin-top:18px}
.cut{background:var(--panel2);border:1px solid var(--line);border-radius:14px;padding:12px}
video{width:100%;border-radius:10px;background:#000;max-height:450px}
.badge{display:inline-block;padding:5px 8px;border-radius:8px;background:#282f40;margin:4px 0}
a{color:#b7a8ff}
.notice{padding:12px;border-radius:10px;background:#201d31;color:#d9d2ff;margin-top:15px}
@media(max-width:800px){.grid{grid-template-columns:1fr}h1{font-size:30px}}
</style>
</head>
<body>
<header>
  <div class="logo">ClipForge <span>AI</span></div>
  <div class="muted">MVP de cortes automáticos</div>
</header>

<main>
  <div class="grid">
    <section class="card">
      <h1>Transforme um vídeo em cortes</h1>
      <p class="muted">
        Envie um vídeo autorizado, escolha duração e quantidade.
        A IA tenta encontrar os melhores momentos.
      </p>

      <form id="form">
        <label>Vídeo</label>
        <input id="video" type="file" accept="video/*" required>

        <label>Quantidade de cortes</label>
        <input id="amount" type="number" min="1" max="100" value="5">

        <label>Duração aproximada</label>
        <select id="duration">
          <option value="30">30 segundos</option>
          <option value="45">45 segundos</option>
          <option value="60" selected>60 segundos</option>
          <option value="90">90 segundos</option>
          <option value="120">120 segundos</option>
        </select>

        <button id="submit">GERAR CORTES</button>
      </form>

      <div class="notice">
        Use somente vídeos que você tenha autorização para editar e publicar.
      </div>
    </section>

    <section class="card">
      <h2>Status</h2>
      <div id="status" class="status muted">Aguardando vídeo...</div>
      <div class="progress"><div id="bar" class="bar"></div></div>
      <div id="meta" class="status"></div>
    </section>
  </div>

  <section class="card" style="margin-top:20px">
    <h2>Cortes gerados</h2>
    <div id="cuts" class="cuts"></div>
  </section>
</main>

<script>
const form=document.getElementById("form");
const submit=document.getElementById("submit");
const statusEl=document.getElementById("status");
const bar=document.getElementById("bar");
const meta=document.getElementById("meta");
const cuts=document.getElementById("cuts");

form.addEventListener("submit", async (e)=>{
  e.preventDefault();

  const file=document.getElementById("video").files[0];
  if(!file) return;

  const data=new FormData();
  data.append("video",file);
  data.append("amount",document.getElementById("amount").value);
  data.append("target_duration",document.getElementById("duration").value);

  submit.disabled=true;
  statusEl.textContent="Enviando vídeo...";
  cuts.innerHTML="";
  bar.style.width="2%";

  try{
    const res=await fetch("/api/projects",{method:"POST",body:data});
    const json=await res.json();
    if(!res.ok) throw new Error(json.detail||"Erro ao criar projeto.");
    await poll(json.job_id);
  }catch(err){
    statusEl.textContent="Erro: "+err.message;
    submit.disabled=false;
  }
});

async function poll(id){
  const timer=setInterval(async()=>{
    try{
      const res=await fetch("/api/projects/"+id);
      const data=await res.json();

      bar.style.width=(data.progress||0)+"%";
      statusEl.textContent=data.message||data.status;
      meta.textContent=
        "Status: "+data.status+
        (data.duration ? " | Vídeo: "+Math.round(data.duration)+"s":"");

      if(data.outputs) renderCuts(data.outputs);

      if(data.status==="concluido" || data.status==="erro"){
        clearInterval(timer);
        submit.disabled=false;
      }
    }catch(err){
      clearInterval(timer);
      statusEl.textContent="Erro consultando projeto: "+err.message;
      submit.disabled=false;
    }
  },1000);
}

function renderCuts(outputs){
  cuts.innerHTML=outputs.map(c=>`
    <div class="cut">
      <video controls playsinline src="${c.file}"></video>
      <div class="badge">Corte ${String(c.index).padStart(2,"0")}</div>
      <div class="badge">${Number(c.duration).toFixed(1)}s</div>
      <div class="badge">Nota ${Number(c.score).toFixed(0)}/100</div>
      <p class="muted">${escapeHtml(c.reason||"Candidato selecionado pela análise.")}</p>
      <a href="${c.file}" download>Baixar vídeo</a><br>
      <a href="${c.subtitle}" download>Baixar legenda SRT</a>
    </div>
  `).join("");
}

function escapeHtml(s){
  return String(s).replace(/[&<>"']/g,m=>({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"
  }[m]));
}
</script>
</body>
</html>
"""


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
