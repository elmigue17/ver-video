#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Arma una página de referencia de un video, bloque por bloque: lo que se dice,
lo que se hace y la captura de ese momento. Sirve para guionizar o grabar algo
parecido a un reel que funcionó.

Uso:
  python pagina_referencia.py <carpeta del video> [bloques.json]

La carpeta es la que dejó ver_video.py (la línea CARPETA=). El archivo de bloques
(por defecto <carpeta>/bloques.json) lo escribe Claude con esta forma:

{
  "titulo": "Desarme del reel",                 (opcional: si no, el título del video)
  "nota": "Para qué sirve esta página.",        (opcional)
  "bloques": [
    {"desde": "0:00", "hasta": "0:03", "rotulo": "Gancho visual",
     "dice": "Lo que se dice, tal cual.",
     "hace": ["Lo que se hace o se ve en pantalla", "Otra acción"],
     "cuadros": ["0:00.5", "0:02"],
     "mirar": "Qué mirar en la captura."}
  ]
}

Las capturas salen de cuadros/ si ya están; si no, se sacan del video de la
carpeta. Todo queda dentro de un solo archivo: <carpeta>/referencia.html.
"""
import base64
import html
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ver_video as vv  # noqa: E402


def a_seg(valor):
    return float(valor) if isinstance(valor, (int, float)) else vv.a_segundos(str(valor))


def texto_html(valor):
    if isinstance(valor, list):
        items = "".join(f"<li>{html.escape(str(x))}</li>" for x in valor if str(x).strip())
        return f"<ul>{items}</ul>" if items else ""
    valor = str(valor or "").strip()
    return "".join(f"<p>{html.escape(p)}</p>" for p in valor.split("\n") if p.strip())


CSS = """
:root{--fondo:#f6f5f2;--tarjeta:#fff;--tinta:#1d1d1f;--suave:#6b6b70;--linea:#e4e2dc;--acento:#c2410c}
*{box-sizing:border-box}body{margin:0;background:var(--fondo);color:var(--tinta);
font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.envoltura{max-width:1100px;margin:0 auto;padding:32px 20px 64px}
header h1{font-size:28px;line-height:1.2;margin:0 0 6px}header .datos{color:var(--suave);font-size:14px}
header .datos a{color:var(--acento)}header .nota{margin:14px 0 0;padding:12px 16px;background:#fff7ed;
border-left:3px solid var(--acento);border-radius:6px}
.bloque{display:grid;grid-template-columns:150px 1fr 1fr;gap:20px;background:var(--tarjeta);
border:1px solid var(--linea);border-radius:14px;padding:20px;margin-top:20px}
.riel .num{font-size:26px;font-weight:700;color:var(--acento)}.riel .tc{display:block;font-size:14px;
color:var(--suave);font-variant-numeric:tabular-nums}.riel .rotulo{display:block;margin-top:8px;font-weight:600}
.et{display:block;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--suave);margin-bottom:6px}
.dice p{margin:0 0 8px;font-size:17px}.dice p:first-of-type::before{content:"\\201C"}
.dice p:last-of-type::after{content:"\\201D"}.hace ul{margin:0;padding-left:18px}.hace p{margin:0 0 8px}
.capturas{grid-column:1/-1;display:flex;flex-wrap:wrap;gap:14px}
figure{margin:0;flex:0 1 auto}figure img{display:block;max-height:420px;max-width:100%;border-radius:10px;
border:1px solid var(--linea)}figcaption{font-size:13px;color:var(--suave);margin-top:6px;max-width:320px}
.mirar{grid-column:1/-1;margin:0;font-size:14px}.mirar b{color:var(--acento)}
footer{margin-top:40px;color:var(--suave);font-size:13px}
@media (max-width:800px){.bloque{grid-template-columns:1fr}}
@media print{body{background:#fff}.bloque{break-inside:avoid}}
"""


def main(argv):
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    if not argv:
        print(__doc__)
        return 2
    carpeta = Path(argv[0]).expanduser().resolve()
    archivo = Path(argv[1]).expanduser() if len(argv) > 1 else carpeta / "bloques.json"
    try:
        spec = json.loads(archivo.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        vv.dato("ERROR", f"No pude leer {archivo}: {e}")
        return 1
    info = vv.leer_json(carpeta / "info.json")
    bloques = spec.get("bloques") or []
    if not bloques:
        vv.dato("ERROR", "El archivo de bloques no tiene bloques.")
        return 1

    video = vv.archivo_bajado(carpeta, "video")
    if not video and info.get("video") and Path(info["video"]).is_file():
        video = Path(info["video"])
    h = None
    dur = float(info.get("duracion_seg") or 0)
    horas = dur >= 3600
    carpeta_cuadros = carpeta / "cuadros"
    carpeta_cuadros.mkdir(exist_ok=True)
    faltan = []

    def imagen(seg):
        nonlocal h
        ruta = carpeta_cuadros / vv.nombre_cuadro(seg)
        if not ruta.is_file():
            if not video:
                faltan.append(vv.reloj(seg, horas, True))
                return None
            if h is None:
                h = vv.Herramientas(necesita_ytdlp=False)
            vinfo = vv.sondear(h, video)
            vv.sacar_cuadro(h, video, seg, ruta, vinfo, horas, vv.fuente_de_letra())
        if not ruta.is_file():
            faltan.append(vv.reloj(seg, horas, True))
            return None
        return "data:image/jpeg;base64," + base64.b64encode(ruta.read_bytes()).decode("ascii")

    partes = []
    for n, b in enumerate(bloques, 1):
        tiempos = b.get("cuadros") or ([b["cuadro"]] if b.get("cuadro") is not None else [])
        figuras = []
        for t in tiempos:
            try:
                seg = a_seg(t)
            except ValueError:
                vv.dato("ERROR", f"No entendí el momento '{t}' del bloque {n}.")
                return 1
            src = imagen(seg)
            if src:
                figuras.append(f'<figure><img src="{src}" alt="Cuadro en {vv.reloj(seg, horas, True)}">'
                               f'<figcaption>{vv.reloj(seg, horas, True)}</figcaption></figure>')
        rango = " a ".join(str(x) for x in (b.get("desde"), b.get("hasta")) if x not in (None, ""))
        partes.append(
            '<section class="bloque">'
            f'<div class="riel"><span class="num">{n:02d}</span><span class="tc">{html.escape(rango)}</span>'
            f'<span class="rotulo">{html.escape(str(b.get("rotulo") or ""))}</span></div>'
            f'<div class="dice"><span class="et">Lo que se dice</span>{texto_html(b.get("dice")) or "<p>(nada)</p>"}</div>'
            f'<div class="hace"><span class="et">Lo que se hace</span>{texto_html(b.get("hace"))}</div>'
            + (f'<div class="capturas">{"".join(figuras)}</div>' if figuras else "")
            + (f'<p class="mirar"><b>Qué mirar:</b> {html.escape(str(b["mirar"]))}</p>' if b.get("mirar") else "")
            + "</section>")

    titulo = spec.get("titulo") or info.get("titulo") or "Referencia del video"
    datos = []
    if info.get("canal"):
        datos.append(html.escape(str(info["canal"])))
    if info.get("plataforma"):
        datos.append(html.escape(str(info["plataforma"])))
    if dur:
        datos.append(vv.reloj(dur))
    url = info.get("url") or info.get("link")
    if url and str(url).startswith("http"):
        datos.append(f'<a href="{html.escape(str(url))}">ver el original</a>')
    nota = f'<p class="nota">{html.escape(str(spec["nota"]))}</p>' if spec.get("nota") else ""
    pagina = (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(str(titulo))}</title><style>{CSS}</style></head><body>"
        f'<div class="envoltura"><header><h1>{html.escape(str(titulo))}</h1>'
        f'<div class="datos">{" · ".join(datos)}</div>{nota}</header>'
        + "".join(partes)
        + f'<footer>Armada con ver-video el {time.strftime("%d/%m/%Y")}.</footer></div></body></html>')
    destino = carpeta / "referencia.html"
    destino.write_text(pagina, encoding="utf-8")
    vv.dato("PAGINA", destino)
    vv.dato("BLOQUES", len(bloques))
    if faltan:
        vv.dato("AVISO", "No pude sacar estos cuadros (no hay video en la carpeta): " + ", ".join(faltan)
                + ". Corre ver_video.py con --en para bajarlos.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
