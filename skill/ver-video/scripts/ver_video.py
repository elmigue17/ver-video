#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ver-video: le da ojos a Claude Code para ver un video.

Baja un video de YouTube, Instagram, TikTok o cualquier página que soporte
yt-dlp (o toma un archivo de video de tu computadora), saca el texto y, si se
pide, cuadros con el minuto escrito encima, armados en hojas de 3x3.

Uso:
  python ver_video.py <link o archivo> [carpeta] [opciones]

  --nivel texto       solo el texto: más rápido y gasta menos del límite de Claude
  --nivel cuadros     texto y cuadros: cuando importa cómo se ve
                      (sin --nivel: cuadros si dura hasta 3 minutos, texto si dura más)
  --cuadros N         cuántos cuadros repartir a lo largo del video
  --en 0:05,1:20.5    sacar cuadros justo en esos momentos
  --transcribir       transcribir el audio aunque el video tenga subtítulos
  --transcriptor X    groq u openrouter, si tienes las dos llaves (por defecto, groq)
  --navegador X       de qué navegador tomar la sesión si la página pide iniciar sesión
  --revisar           revisa que esté todo instalado y que la llave funcione

La carpeta por defecto es ./ver-video/<id del video>. Queda así:
  transcripcion.txt   el texto con marcas [MM:SS], en el idioma original del video
  info.json           título, canal, duración, descripción, capítulos y de dónde salió el texto
  video.*             el video a 720p como mucho (solo si se pidieron cuadros)
  cuadros/            cada cuadro suelto con el minuto encima (t00012.5.jpg = segundo 12,5)
  hoja_1.jpg, ...     los cuadros repartidos, de a 9 por hoja
  momentos_1.jpg, ... los cuadros pedidos con --en

En la salida estándar deja líneas CLAVE=valor (CARPETA=, TRANSCRIPCION=, HOJA=,
COSTO_USD=...). Los avisos de avance van a la salida de errores.

Solo usa la biblioteca estándar de Python, más yt-dlp y ffmpeg instalados aparte.
Lo único que sale de tu computadora: el pedido del video a la página de origen
y, si hace falta transcribir, el audio al servicio que elegiste (Groq u OpenRouter).
"""
import argparse
import base64
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

VERSION = "1.0"
CARPETA_SKILL = Path(__file__).resolve().parent.parent
ARCHIVO_ENV = CARPETA_SKILL / ".env"
AGENTE = f"ver-video/{VERSION}"

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_URL_MODELOS = "https://api.groq.com/openai/v1/models"
GROQ_MODELO = "whisper-large-v3-turbo"
GROQ_USD_POR_HORA = 0.04       # tarifa publicada por Groq (octubre de 2026)
GROQ_MINIMO_SEG = 10           # Groq cobra como mínimo 10 s por pedido
GROQ_TRAMO_SEG = 600           # 10 min por pedido: unos 5 MB, lejos del tope de 25 MB

OPENROUTER_URL = "https://openrouter.ai/api/v1/audio/transcriptions"
OPENROUTER_URL_LLAVE = "https://openrouter.ai/api/v1/key"
OPENROUTER_MODELO = "openai/whisper-large-v3-turbo"
OPENROUTER_USD_POR_SEG = 0.00000333  # lista de modelos de OpenRouter (octubre de 2026)
OPENROUTER_TRAMO_SEG = 300     # 5 min: OpenRouter corta cada pedido a los 60 s de proceso

CORTO_SEG = 90           # menos que esto es un reel o un short: más cuadros en el arranque
AUTO_CUADROS_SEG = 180   # sin --nivel: hasta 3 min, texto y cuadros; más largo, solo texto
MAX_CUADROS = 60
LADO_HOJA = 512          # lado largo de cada cuadro dentro de una hoja de 3x3


class Falla(Exception):
    """Un error que se le explica al usuario tal cual."""


# ----------------------------------------------------------------- utilidades

def aviso(texto):
    print(texto, file=sys.stderr, flush=True)


def dato(clave, valor):
    print(f"{clave}={valor}", flush=True)


def correr(cmd, timeout=None):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", "se pasó del tiempo de espera")
    except OSError as e:
        return subprocess.CompletedProcess(cmd, 127, "", f"no pude ejecutar {cmd[0]}: {e}")


def reloj(seg, horas=False, decimas=False):
    """1:05, 1:02:05 o, con decimas, 0:01.5."""
    seg = round(max(0.0, float(seg)), 1)
    ent = int(seg)
    h, m, s = ent // 3600, (ent % 3600) // 60, ent % 60
    txt = f"{h}:{m:02d}:{s:02d}" if (h or horas) else f"{m}:{s:02d}"
    d = int(round((seg - ent) * 10)) % 10
    return txt + (f".{d}" if decimas and d else "")


def marca(seg, horas):
    ent = int(seg)
    h, m, s = ent // 3600, (ent % 3600) // 60, ent % 60
    return f"[{h}:{m:02d}:{s:02d}]" if horas else f"[{m:02d}:{s:02d}]"


def a_segundos(txt):
    """'1:20.5' -> 80.5 ; '75' -> 75.0 ; '1:02:03' -> 3723.0"""
    total = 0.0
    for parte in txt.strip().split(":"):
        total = total * 60 + float(parte)
    return total


def limpiar_id(txt):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(txt)).strip("_")[:60] or "video"


def leer_json(ruta):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


# ------------------------------------------------------------- herramientas

def buscar_programa(nombre):
    """Busca un programa en el PATH y, si no está, donde lo dejan winget y brew
    (sirve cuando se acaba de instalar y la terminal todavía no lo ve)."""
    ruta = shutil.which(nombre)
    if ruta:
        return ruta
    candidatos = []
    if os.name == "nt":
        local = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        winget = local / "Microsoft" / "WinGet"
        candidatos.append(winget / "Links" / f"{nombre}.exe")
        paquetes = winget / "Packages"
        if paquetes.is_dir():
            for patron in (f"*/{nombre}.exe", f"*/bin/{nombre}.exe", f"*/*/bin/{nombre}.exe"):
                candidatos += sorted(paquetes.glob(patron), reverse=True)
        candidatos.append(Path.home() / ".deno" / "bin" / f"{nombre}.exe")
    else:
        for carpeta in ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin",
                        str(Path.home() / ".local" / "bin"), str(Path.home() / ".deno" / "bin")):
            candidatos.append(Path(carpeta) / nombre)
    for c in candidatos:
        if c.is_file():
            return str(c)
    return None


def comando_ytdlp():
    ruta = buscar_programa("yt-dlp")
    if ruta:
        return [ruta]
    import importlib.util
    if importlib.util.find_spec("yt_dlp"):
        return [sys.executable, "-m", "yt_dlp"]
    return None


class Herramientas:
    def __init__(self, necesita_ytdlp=True):
        self.ffmpeg = buscar_programa("ffmpeg")
        self.ffprobe = buscar_programa("ffprobe")
        self.ytdlp = comando_ytdlp()
        self.deno = buscar_programa("deno")
        faltan = [n for n, v in (("ffmpeg", self.ffmpeg), ("ffprobe", self.ffprobe)) if not v]
        if necesita_ytdlp and not self.ytdlp:
            faltan.insert(0, "yt-dlp")
        if faltan:
            raise Falla("Falta instalar " + " y ".join(faltan) + ". En Windows: winget install "
                        "yt-dlp.yt-dlp (trae ffmpeg); en Mac: brew install yt-dlp ffmpeg. "
                        "Después abre una terminal nueva.")


def sondear(h, ruta):
    """Duración, tamaño y si tiene audio, con ffprobe."""
    r = correr([h.ffprobe, "-v", "error", "-show_entries",
                "format=duration:stream=codec_type,width,height", "-of", "json", str(ruta)], 120)
    try:
        d = json.loads(r.stdout or "{}")
    except ValueError:
        d = {}
    info = {"duracion": 0.0, "ancho": 0, "alto": 0, "audio": False, "video": False}
    try:
        info["duracion"] = float((d.get("format") or {}).get("duration") or 0)
    except ValueError:
        pass
    for s in d.get("streams") or []:
        if s.get("codec_type") == "video" and not info["video"]:
            info.update(video=True, ancho=int(s.get("width") or 0), alto=int(s.get("height") or 0))
        elif s.get("codec_type") == "audio":
            info["audio"] = True
    return info


# -------------------------------------------------------------------- llaves

def leer_archivo_env():
    valores = {}
    if ARCHIVO_ENV.is_file():
        for linea in ARCHIVO_ENV.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            clave = clave.strip()
            if clave.startswith("export "):
                clave = clave[7:].strip()
            valores[clave] = valor.strip().strip('"').strip("'")
    return valores


def llaves():
    """{nombre: (valor, de dónde salió)}. Primero el entorno, después el .env de la skill."""
    archivo = leer_archivo_env()
    res = {}
    for nombre in ("GROQ_API_KEY", "OPENROUTER_API_KEY"):
        if (os.environ.get(nombre) or "").strip():
            res[nombre] = (os.environ[nombre].strip(), "variable de entorno")
        elif archivo.get(nombre, "").strip():
            res[nombre] = (archivo[nombre].strip(), "archivo .env de la skill")
    return res


def elegir_transcriptor(preferido, disponibles):
    orden = [preferido] if preferido else ["groq", "openrouter"]
    for p in orden:
        if ("GROQ_API_KEY" if p == "groq" else "OPENROUTER_API_KEY") in disponibles:
            return p
    return None


# --------------------------------------------------------------------- HTTP

def pedir(url, cuerpo=None, cabeceras=None, intentos=4, espera_max=90):
    """(estado, texto). Reintenta si el servicio está saturado o se cortó la conexión."""
    cab = {"User-Agent": AGENTE}
    cab.update(cabeceras or {})
    ultimo = (0, "")
    for n in range(intentos):
        req = urllib.request.Request(url, data=cuerpo, headers=cab,
                                     method="POST" if cuerpo is not None else "GET")
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            ultimo = (e.code, e.read().decode("utf-8", "replace"))
            if e.code in (408, 429, 500, 502, 503, 504) and n < intentos - 1:
                try:
                    espera = float(e.headers.get("Retry-After") or 0)
                except ValueError:
                    espera = 0
                espera = espera or 5 * (2 ** n)
                if espera > espera_max:
                    return ultimo
                aviso(f"  El servicio respondió {e.code}; reintento en {espera:.0f} s...")
                time.sleep(espera)
                continue
            return ultimo
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            ultimo = (0, str(getattr(e, "reason", e)))
            if n < intentos - 1:
                time.sleep(5 * (2 ** n))
                continue
    return ultimo


def multipart(campos, ruta, tipo):
    limite = "----vervideo" + uuid.uuid4().hex
    partes = []
    for clave, valor in campos.items():
        partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="{clave}"'
                      f'\r\n\r\n{valor}\r\n'.encode("utf-8"))
    partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="file"; '
                  f'filename="{ruta.name}"\r\nContent-Type: {tipo}\r\n\r\n'.encode("utf-8"))
    partes.append(ruta.read_bytes())
    partes.append(f"\r\n--{limite}--\r\n".encode("utf-8"))
    return b"".join(partes), f"multipart/form-data; boundary={limite}"


def explicar_error_api(proveedor, estado, texto, origen="archivo .env de la skill"):
    nombre = "Groq" if proveedor == "groq" else "OpenRouter"
    if estado == 401:
        donde = ARCHIVO_ENV if "archivo" in origen else "la variable de entorno"
        return f"{nombre} rechazó la llave (401). Revísala en {donde} o crea una nueva."
    if estado == 402:
        return f"La cuenta de {nombre} no tiene saldo (402). Carga saldo y vuelve a probar."
    if estado == 403:
        return f"{nombre} no deja usar esa llave (403): puede tener un tope de gasto o estar desactivada."
    if estado == 413:
        return f"{nombre} dice que el audio es muy grande (413)."
    if estado == 429:
        return (f"{nombre} dice que pasaste el límite de uso por ahora (429). "
                "Espera un rato y vuelve a probar.")
    if estado == 0:
        return f"No pude conectarme con {nombre}: {texto[:200]}. Revisa tu conexión a internet."
    return f"{nombre} respondió {estado}: {texto[:300]}"


def probar_llave(proveedor, valor):
    url = GROQ_URL_MODELOS if proveedor == "groq" else OPENROUTER_URL_LLAVE
    estado, _ = pedir(url, cabeceras={"Authorization": f"Bearer {valor}"}, intentos=2)
    if estado == 200:
        return "funciona"
    if estado in (401, 403):
        return f"NO funciona ({estado}): revisa que la hayas copiado entera"
    return f"no pude comprobarla (respuesta {estado})"


# ------------------------------------------------------------------- yt-dlp

class Bajador:
    """Corre yt-dlp. Si la página pide iniciar sesión (Instagram, a veces),
    reintenta con la sesión del navegador y la recuerda para lo que sigue."""

    PIDE_SESION = re.compile(r"login|log in|sign in|cookie|rate.?limit|private|authenticat|"
                             r"not a bot|empty media|restricted|registered users|inicia", re.I)

    def __init__(self, h, navegador=None):
        self.base = list(h.ytdlp) + ["--no-playlist", "--no-progress"]
        if h.ffmpeg and not shutil.which("ffmpeg"):
            self.base += ["--ffmpeg-location", str(Path(h.ffmpeg).parent)]
        if h.deno and not shutil.which("deno"):
            self.base += ["--js-runtimes", f"deno:{h.deno}"]
        self.navegadores = [navegador] if navegador else ["chrome", "firefox"]
        self.sesion = []

    def correr(self, args, timeout):
        r = correr(self.base + self.sesion + args, timeout)
        if r.returncode == 0 or self.sesion or not self.PIDE_SESION.search(r.stderr or ""):
            return r
        for nav in self.navegadores:
            aviso(f"La página pide iniciar sesión. Pruebo con tu sesión de {nav}...")
            r2 = correr(self.base + ["--cookies-from-browser", nav] + args, timeout)
            if r2.returncode == 0:
                self.sesion = ["--cookies-from-browser", nav]
                return r2
        r.stderr = (r.stderr or "") + "\nPIDE_SESION"
        return r


def explicar_error_ytdlp(stderr, link):
    err = (stderr or "").strip()
    ultima = [l for l in err.splitlines() if l.startswith("ERROR")][-1:] or err.splitlines()[-1:]
    detalle = ultima[0][:300] if ultima else "sin detalle"
    if "PIDE_SESION" in err:
        return ("La página pide iniciar sesión para ver este video y no pude usar la sesión de tu "
                "navegador. Abre el video en Chrome con tu cuenta, cierra Chrome del todo y vuelve a "
                "probar; o inicia sesión en Firefox y usa --navegador firefox. "
                f"(yt-dlp dijo: {detalle})")
    if re.search(r"unsupported url", err, re.I):
        return f"yt-dlp no reconoce ese link como un video: {link}"
    if re.search(r"no impersonate target is available", err, re.I):
        return ("Esta página (TikTok, por ejemplo) necesita una parte de yt-dlp que no está "
                "instalada (curl_cffi). Instala yt-dlp con winget (Windows) o brew (Mac), que ya la "
                "traen, o corre: python -m pip install -U \"yt-dlp[default,curl-cffi]\". "
                f"(yt-dlp dijo: {detalle})")
    if re.search(r"getaddrinfo|network is unreachable|timed out|connection", err, re.I):
        return f"No pude conectarme a la página del video. Revisa tu conexión. ({detalle})"
    return (f"No pude bajar el video. {detalle}. Si es de YouTube y dice algo de JavaScript o de "
            "formatos, actualiza yt-dlp (yt-dlp -U, o winget upgrade yt-dlp.yt-dlp, o brew upgrade yt-dlp).")


def datos_del_video(m, link):
    fecha = m.get("upload_date") or ""
    if len(fecha) == 8:
        fecha = f"{fecha[:4]}-{fecha[4:6]}-{fecha[6:]}"
    capitulos = [{"inicio": reloj(c.get("start_time") or 0), "titulo": c.get("title")}
                 for c in (m.get("chapters") or [])]
    desc = (m.get("description") or "").strip()
    return {
        "link": link, "url": m.get("webpage_url") or link, "id": m.get("id"),
        "plataforma": m.get("extractor_key") or m.get("extractor"),
        "titulo": m.get("title"),
        "canal": m.get("channel") or m.get("uploader") or m.get("uploader_id"),
        "fecha": fecha or None, "duracion_seg": m.get("duration"), "idioma": m.get("language"),
        "vistas": m.get("view_count"), "me_gusta": m.get("like_count"),
        "comentarios": m.get("comment_count"),
        "descripcion": desc[:5000] or None, "capitulos": capitulos or None,
    }


def archivo_bajado(carpeta, prefijo):
    for p in sorted(carpeta.glob(prefijo + ".*")):
        if p.suffix.lower() not in (".part", ".ytdl", ".json", ".vtt", ".jpg", ".webp") and p.stat().st_size > 0:
            return p
    return None


# -------------------------------------------------------------------- texto

def elegir_pistas(meta):
    """Pistas de subtítulos de YouTube en el IDIOMA ORIGINAL del video, de la mejor a la peor.
    Los videos con doblaje automático traen varias pistas "-orig" (en-orig, de-DE-orig...):
    se elige la del idioma que YouTube dice que tiene el video (`language`)."""
    autos = list((meta.get("automatic_captions") or {}).keys())
    manuales = [k for k in (meta.get("subtitles") or {}).keys() if k != "live_chat"]
    if not autos and not manuales:
        return []
    base = (meta.get("language") or "").split("-")[0].lower()
    origs = [k for k in autos if k.endswith("-orig")]
    if not base and len(origs) == 1:
        base = origs[0].split("-")[0].lower()
    orden = []
    for idioma in ([base] if base else ["en", "es"]):
        orden += [k for k in manuales if k.split("-")[0].lower() == idioma]
        orden += [k for k in origs if k.split("-")[0].lower() == idioma]
        orden += [k for k in autos if k.split("-")[0].lower() == idioma and not k.endswith("-orig")]
    if not orden:
        orden = origs[:1] or manuales[:1]
    vistos = []
    for k in orden:
        if k not in vistos:
            vistos.append(k)
    return vistos[:3]


def vtt_a_lineas(crudo):
    """VTT a [(segundo, texto)]. Los subtítulos automáticos repiten la línea
    anterior para simular el desplazamiento: se saca lo repetido."""
    lineas, ultima = [], ""
    for bloque in re.split(r"\n\s*\n", crudo.replace("\r\n", "\n")):
        m = re.search(r"(?:(\d+):)?(\d{2}):(\d{2})[.,](\d{3})\s*-->", bloque)
        if not m:
            continue
        seg = int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 1000
        partes = bloque.split("-->", 1)[1].split("\n", 1)
        for linea in (partes[1] if len(partes) > 1 else "").splitlines():
            txt = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", linea))).strip()
            if not txt or txt == ultima:
                continue
            lineas.append((seg, txt))
            ultima = txt
    return lineas


def agrupar(items, cada, horas):
    """Junta las líneas en párrafos de `cada` segundos, cada uno con su marca [MM:SS]."""
    salida, buf, desde, ultimo = [], [], None, None
    for seg, txt in sorted(items, key=lambda x: x[0]):
        if txt == ultimo:
            continue
        ultimo = txt
        if desde is None:
            desde = seg
        if buf and seg - desde >= cada:
            salida.append(f"{marca(desde, horas)} {' '.join(buf)}")
            buf, desde = [], seg
        buf.append(txt)
    if buf:
        salida.append(f"{marca(desde, horas)} {' '.join(buf)}")
    return "\n".join(salida) + ("\n" if salida else "")


def lineas_de_respuesta(resp, inicio, largo):
    """Segmentos de Whisper con el tiempo corrido al inicio del tramo. Si el servicio
    no devolvió segmentos, reparte las frases a lo largo del tramo (marcas aproximadas)."""
    segmentos = resp.get("segments") or []
    salida = []
    for s in segmentos:
        txt = (s.get("text") or "").strip()
        if txt:
            salida.append((inicio + float(s.get("start") or 0), txt))
    if segmentos:
        return salida, True
    texto = (resp.get("text") or "").strip()
    frases = [f.strip() for f in re.split(r"(?<=[.!?…])\s+", texto) if f.strip()]
    total, pos = sum(len(f) for f in frases) or 1, 0
    for f in frases:
        salida.append((inicio + largo * pos / total, f))
        pos += len(f)
    return salida, False


def cortar_audio(h, fuente, dur, tramo, tmp):
    """Pasa el audio a mono 16 kHz (lo que usa Whisper) en tramos que no pasen los topes."""
    tramos = []
    n = max(1, math.ceil(dur / tramo)) if dur > 0 else 1
    for i in range(n):
        ini = i * tramo
        largo = min(tramo, dur - ini) if dur > 0 else 0
        if dur > 0 and largo < 0.3:
            break
        corte = (["-ss", f"{ini:.3f}", "-t", f"{largo:.3f}"] if dur > 0 else [])
        destino = tmp / f"tramo_{i:03d}.mp3"
        r = correr([h.ffmpeg, "-loglevel", "error", "-y"] + corte + ["-i", str(fuente), "-vn",
                    "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "64k", str(destino)], 900)
        formato = "mp3"
        if r.returncode != 0 or not destino.is_file() or destino.stat().st_size == 0:
            destino = destino.with_suffix(".wav")
            formato = "wav"
            r = correr([h.ffmpeg, "-loglevel", "error", "-y"] + corte + ["-i", str(fuente), "-vn",
                        "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(destino)], 900)
        if r.returncode != 0 or not destino.is_file():
            raise Falla("No pude preparar el audio para transcribir: " + (r.stderr or "")[-300:])
        tramos.append((ini, largo or dur, destino, formato))
    return tramos


def transcribir(h, fuente, dur, proveedor, llave, tmp, origen):
    """Devuelve (líneas, costo en USD, si el costo es real o estimado, si hay marcas exactas)."""
    tramo = GROQ_TRAMO_SEG if proveedor == "groq" else OPENROUTER_TRAMO_SEG
    tramos = cortar_audio(h, fuente, dur, tramo, tmp)
    lineas, costo, costo_real, exactas = [], 0.0, proveedor == "openrouter", True
    for i, (ini, largo, ruta, formato) in enumerate(tramos, 1):
        if len(tramos) > 1:
            aviso(f"  Tramo {i} de {len(tramos)} ({reloj(ini)} a {reloj(ini + largo)})...")
        if proveedor == "groq":
            cuerpo, tipo = multipart({"model": GROQ_MODELO, "response_format": "verbose_json",
                                      "temperature": "0"}, ruta,
                                     "audio/mpeg" if formato == "mp3" else "audio/wav")
            estado, texto = pedir(GROQ_URL, cuerpo, {"Authorization": f"Bearer {llave}",
                                                     "Content-Type": tipo})
        else:
            pedido = {"model": OPENROUTER_MODELO, "temperature": 0, "response_format": "verbose_json",
                      "input_audio": {"data": base64.b64encode(ruta.read_bytes()).decode("ascii"),
                                      "format": formato}}
            cab = {"Authorization": f"Bearer {llave}", "Content-Type": "application/json"}
            estado, texto = pedir(OPENROUTER_URL, json.dumps(pedido).encode("utf-8"), cab)
            if estado == 400 and re.search(r"verbose|response_format", texto, re.I):
                pedido.pop("response_format")
                estado, texto = pedir(OPENROUTER_URL, json.dumps(pedido).encode("utf-8"), cab)
        if estado != 200:
            raise Falla(explicar_error_api(proveedor, estado, texto, origen))
        try:
            resp = json.loads(texto)
        except ValueError:
            raise Falla(f"La respuesta del servicio de transcripción no se entiende: {texto[:200]}")
        nuevas, con_marcas = lineas_de_respuesta(resp, ini, largo)
        lineas += nuevas
        exactas = exactas and con_marcas
        if proveedor == "groq":
            costo += max(GROQ_MINIMO_SEG, largo) * GROQ_USD_POR_HORA / 3600
        else:
            uso = (resp.get("usage") or {}).get("cost")
            if isinstance(uso, (int, float)):
                costo += float(uso)
            else:
                costo += largo * OPENROUTER_USD_POR_SEG
                costo_real = False
    return lineas, costo, costo_real, exactas


# ------------------------------------------------------------------ cuadros

def fuente_de_letra():
    if os.name == "nt":
        fuentes = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        candidatos = [fuentes / "arialbd.ttf", fuentes / "arial.ttf", fuentes / "segoeui.ttf"]
    elif sys.platform == "darwin":
        candidatos = [Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
                      Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
                      Path("/Library/Fonts/Arial.ttf")]
    else:
        candidatos = [Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
                      Path("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
                      Path("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf")]
    for c in candidatos:
        if c.is_file():
            return c.as_posix()
    return None


def tiempos_repartidos(dur, n=None):
    """Dónde sacar los cuadros. En un video corto (reel, short), uno cada medio segundo
    en los primeros 3 s (el gancho visual) y después uno cada 2 s hasta el final.
    En uno largo, n parejos de punta a punta."""
    fin = max(0.0, dur - 0.3)
    if dur <= 0:
        return [0.0]
    if dur < CORTO_SEG:
        gancho = [x * 0.5 for x in range(7) if x * 0.5 <= fin]
        resto = []
        if fin > 3.5 and n:
            k = max(1, min(n - len(gancho), MAX_CUADROS - len(gancho)))
            resto = [round((3.0 + (fin - 3.0) * i / k) * 2) / 2 for i in range(1, k + 1)]
        elif fin > 3.5:
            resto = [3.0 + 2 * i for i in range(1, int((fin - 3.0) // 2) + 1) if 3.0 + 2 * i < fin - 0.9]
            resto.append(round(fin, 1))   # el último cuadro, para ver el cierre
        return sorted(set(gancho + resto[:MAX_CUADROS - len(gancho)]))
    if not n:
        n = int(math.ceil(min(36, max(18, dur / 30)) / 9) * 9)
    n = max(2, min(n, MAX_CUADROS))
    primero = min(3.0, fin)
    tiempos = [primero] + [float(round(primero + (fin - 1.0 - primero) * i / (n - 1)))
                           for i in range(1, n)]
    return sorted(set(tiempos))


def nombre_cuadro(seg):
    return f"t{seg:07.1f}.jpg"


def sacar_cuadro(h, video, seg, destino, info, horas, letra):
    """Un cuadro en el segundo `seg`, con el minuto escrito arriba a la izquierda."""
    if destino.is_file() and destino.stat().st_size > 0:
        return True
    etiqueta = reloj(seg, horas, decimas=True).replace(":", "\\:")
    tam = max(18, round(min(info["ancho"] or 720, info["alto"] or 720) / 14))
    texto = (f"drawtext=text='{etiqueta}':x=12:y=12:fontsize={tam}:fontcolor=yellow:"
             f"box=1:boxcolor=black@0.65:boxborderw=8")
    if letra:
        texto += ":fontfile='" + letra.replace(":", "\\:") + "'"
    for filtro in (texto, None):
        cmd = [h.ffmpeg, "-loglevel", "error", "-y", "-ss", f"{seg:.2f}", "-i", str(video),
               "-frames:v", "1", "-q:v", "3"]
        cmd += (["-vf", filtro] if filtro else []) + [str(destino)]
        correr(cmd, 120)
        if destino.is_file() and destino.stat().st_size > 0:
            return filtro is not None or "sin_etiqueta"
    return False


def armar_hojas(h, cuadros, prefijo, carpeta, info, tmp):
    """Junta los cuadros de a 9 en hojas de 3x3 para mirarlas con Read."""
    for vieja in carpeta.glob(f"{prefijo}_*.jpg"):
        vieja.unlink()
    ancho, alto = info["ancho"] or 1280, info["alto"] or 720
    if ancho >= alto:
        tw, th = LADO_HOJA, int(round(LADO_HOJA * alto / ancho / 2)) * 2
    else:
        th, tw = LADO_HOJA, int(round(LADO_HOJA * ancho / alto / 2)) * 2
    hojas = []
    for n, i in enumerate(range(0, len(cuadros), 9), 1):
        grupo = cuadros[i:i + 9]
        temp = tmp / f"{prefijo}_{n}"
        temp.mkdir(parents=True, exist_ok=True)
        for j, (_, ruta) in enumerate(grupo, 1):
            shutil.copyfile(ruta, temp / f"{j:02d}.jpg")
        columnas = min(3, len(grupo))
        filas = math.ceil(len(grupo) / 3)
        destino = carpeta / f"{prefijo}_{n}.jpg"
        correr([h.ffmpeg, "-loglevel", "error", "-y", "-i", str(temp / "%02d.jpg"), "-frames:v", "1",
                "-vf", f"scale={tw}:{th},tile={columnas}x{filas}:padding=6:color=white",
                "-q:v", "3", str(destino)], 120)
        if destino.is_file():
            hojas.append((destino, grupo[0][0], grupo[-1][0]))
    return hojas


# ------------------------------------------------------------------ revisar

def revisar():
    listo = True
    dato("PYTHON", sys.version.split()[0])
    y = comando_ytdlp()
    if y:
        dato("YT_DLP", f"{correr(y + ['--version'], 60).stdout.strip()} ({' '.join(y)})")
        objetivos = correr(y + ["--list-impersonate-targets"], 60).stdout or ""
        filas = [l for l in objetivos.splitlines() if "curl_cffi" in l]
        if any("unavailable" not in l for l in filas):
            dato("TIKTOK", "listo")
        else:
            dato("TIKTOK", "falta curl_cffi: TikTok no va a andar. Instala yt-dlp con winget o brew, "
                           "o corre: python -m pip install -U \"yt-dlp[default,curl-cffi]\"")
    else:
        dato("YT_DLP", "FALTA")
        listo = False
    for nombre in ("ffmpeg", "ffprobe"):
        ruta = buscar_programa(nombre)
        if ruta:
            primera = (correr([ruta, "-version"], 60).stdout or "").splitlines()[:1]
            dato(nombre.upper(), f"{primera[0] if primera else 'ok'} ({ruta})")
        else:
            dato(nombre.upper(), "FALTA")
            listo = False
    deno = buscar_programa("deno")
    dato("DENO", deno or "no está (yt-dlp lo usa con YouTube; si YouTube falla, instálalo)")
    disponibles = llaves()
    for nombre, prov in (("GROQ_API_KEY", "groq"), ("OPENROUTER_API_KEY", "openrouter")):
        if nombre in disponibles:
            valor, origen = disponibles[nombre]
            dato(nombre, f"configurada ({origen}), {probar_llave(prov, valor)}")
        else:
            dato(nombre, "no configurada")
    elegido = elegir_transcriptor(None, disponibles)
    dato("TRANSCRIPTOR", elegido or "ninguno: solo vas a poder usar videos de YouTube con subtítulos")
    dato("ARCHIVO_LLAVES", ARCHIVO_ENV)
    dato("LISTO", 1 if listo else 0)
    return 0 if listo else 1


# --------------------------------------------------------------------- main

def paso_texto(a, h, carpeta, tmp, meta, origen, es_local, fuente_local, video, previo, datos):
    """Deja transcripcion.txt. Devuelve la parte "texto" de info.json."""
    destino = carpeta / "transcripcion.txt"
    horas = (datos.get("duracion_seg") or 0) >= 3600
    corto = 0 < (datos.get("duracion_seg") or 0) < CORTO_SEG
    if destino.is_file() and destino.stat().st_size > 0 and not a.transcribir:
        anterior = previo.get("texto") or {}
        return dict(anterior, reusada=True)

    es_youtube = bool(meta) and str(datos.get("plataforma") or "").lower().startswith("youtube")
    if es_youtube and not a.transcribir:
        pistas = elegir_pistas(meta)
        if pistas:
            aviso(f"Bajando los subtítulos (pistas {', '.join(pistas)})...")
            bajador = a._bajador
            bajador.correr(["--skip-download", "--write-subs", "--write-auto-subs", "--sub-langs",
                            ",".join(pistas), "--sub-format", "vtt", "-o", str(tmp / "s.%(ext)s")]
                           + origen, 300)
            for pista in pistas:
                vtt = tmp / f"s.{pista}.vtt"
                if vtt.is_file():
                    lineas = vtt_a_lineas(vtt.read_text(encoding="utf-8", errors="replace"))
                    if lineas:
                        destino.write_text(agrupar(lineas, 0 if corto else 20, horas), encoding="utf-8")
                        return {"fuente": f"subtítulos de YouTube (pista {pista})", "costo_usd": 0.0,
                                "costo": "gratis", "marcas": "exactas"}
            aviso("No pude bajar los subtítulos; paso a transcribir el audio.")

    disponibles = llaves()
    proveedor = elegir_transcriptor(a.transcriptor, disponibles)
    if not proveedor:
        falta = ("No hay llave de " + a.transcriptor) if a.transcriptor else \
            "No hay llave para transcribir (GROQ_API_KEY u OPENROUTER_API_KEY)"
        return {"fuente": None, "error": f"{falta}. Guárdala en {ARCHIVO_ENV} (mira .env.example)."}
    llave, origen_llave = disponibles["GROQ_API_KEY" if proveedor == "groq" else "OPENROUTER_API_KEY"]

    # El audio: del archivo local, del video ya bajado si trae audio, o se baja solo el audio.
    if es_local:
        fuente = fuente_local
    elif video is not None and sondear(h, video)["audio"]:
        fuente = video
    else:
        aviso("Bajando el audio...")
        r = a._bajador.correr(["-f", "ba/b", "-S", "lang,abr:96", "--no-part",
                               "-o", str(tmp / "audio.%(ext)s")] + origen, 1800)
        fuente = archivo_bajado(tmp, "audio")
        if not fuente:
            raise Falla(explicar_error_ytdlp(r.stderr, a.link))
    sonda = sondear(h, fuente)
    if not sonda["audio"]:
        destino.write_text("(el video no tiene audio)\n", encoding="utf-8")
        return {"fuente": "el video no tiene audio", "costo_usd": 0.0, "costo": "gratis"}
    dur = sonda["duracion"] or float(datos.get("duracion_seg") or 0)
    if not datos.get("duracion_seg") and dur:
        datos["duracion_seg"] = round(dur, 1)
        horas, corto = dur >= 3600, dur < CORTO_SEG
    nombre = "Groq" if proveedor == "groq" else "OpenRouter"
    modelo = GROQ_MODELO if proveedor == "groq" else OPENROUTER_MODELO
    aviso(f"Transcribiendo {reloj(dur)} de audio con {nombre}...")
    lineas, costo, real, exactas = transcribir(h, fuente, dur, proveedor, llave, tmp, origen_llave)
    destino.write_text(agrupar(lineas, 0 if corto else 20, horas) or "(no se entendió nada hablado)\n",
                       encoding="utf-8")
    tarifa = ("costo real informado por OpenRouter" if real else
              "estimado con la tarifa publicada de " + nombre +
              (" (0,04 USD por hora, mínimo 10 s por pedido)" if proveedor == "groq" else ""))
    return {"fuente": f"transcripción con {nombre} ({modelo})", "costo_usd": round(costo, 6),
            "costo": tarifa, "segundos_de_audio": round(dur, 1),
            "marcas": "exactas" if exactas else "aproximadas"}


def ver(a, inicio):
    local = Path(a.link).expanduser()
    es_local = local.is_file()
    h = Herramientas(necesita_ytdlp=not es_local)
    momentos = []
    if a.en:
        try:
            momentos = [a_segundos(x) for x in a.en.split(",") if x.strip()]
        except ValueError:
            raise Falla("No entendí los momentos de --en. Escríbelos así: 0:05,1:20.5,75")

    meta = None
    if not es_local and not re.match(r"^[a-z]+://", a.link, re.I):
        a.link = "https://" + a.link
    # Si es una consulta de seguimiento sobre una carpeta que ya tiene todo, no se vuelve
    # a consultar la página (Instagram corta si se le pide lo mismo muchas veces).
    ya_bajado = {}
    if not es_local and a.carpeta and not a.transcribir:
        c = Path(a.carpeta).expanduser().resolve()
        anterior = leer_json(c / "info.json")
        pide_video = a.nivel == "cuadros" or bool(a.cuadros) or bool(momentos)
        if (anterior.get("link") == a.link and (c / "transcripcion.txt").is_file()
                and (not pide_video or archivo_bajado(c, "video"))):
            ya_bajado = {k: v for k, v in anterior.items() if k not in ("nivel", "texto", "cuadros", "video")}
    if es_local:
        sonda_local = sondear(h, local)
        datos = {"link": str(local.resolve()), "url": None, "id": limpiar_id(local.stem),
                 "plataforma": "archivo local", "titulo": local.name,
                 "duracion_seg": round(sonda_local["duracion"], 1) or None}
    elif ya_bajado:
        a._bajador = Bajador(h, a.navegador)
        datos = ya_bajado
    else:
        a._bajador = Bajador(h, a.navegador)
        aviso("Leyendo la información del video...")
        r = a._bajador.correr(["-J", "--skip-download", a.link], 180)
        if r.returncode != 0:
            raise Falla(explicar_error_ytdlp(r.stderr, a.link))
        try:
            meta = json.loads(r.stdout)
        except ValueError:
            raise Falla("yt-dlp no devolvió la información del video.")
        if meta.get("_type") in ("playlist", "multi_video"):
            entradas = [e for e in (meta.get("entries") or []) if e]
            if not entradas:
                raise Falla("El link es una lista o un perfil, no un video. Pásame el link de un video.")
            if len(entradas) > 1:
                aviso(f"El link tiene {len(entradas)} videos; tomo el primero.")
            meta = entradas[0]
        datos = datos_del_video(meta, a.link)

    carpeta = (Path(a.carpeta).expanduser() if a.carpeta
               else Path.cwd() / "ver-video" / limpiar_id(datos.get("id") or "video")).resolve()
    carpeta.mkdir(parents=True, exist_ok=True)
    previo = leer_json(carpeta / "info.json")
    tmp = carpeta / "_tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    # yt-dlp trabaja con la información ya leída (un solo pedido a la página) o, en una
    # consulta de seguimiento, con el link.
    origen = [] if es_local else [a.link]
    if meta is not None:
        (tmp / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        origen = ["--load-info-json", str(tmp / "meta.json")]

    # El nivel: el que se pidió; si no se pidió, cuadros si el video es corto.
    # Con solo --en se sacan esos momentos y nada más.
    dur = float(datos.get("duracion_seg") or 0)
    if a.nivel:
        nivel = a.nivel
    elif a.cuadros:
        nivel = "cuadros"
    elif momentos:
        nivel = None
    else:
        nivel = "cuadros" if (dur == 0 or dur <= AUTO_CUADROS_SEG) else "texto"
    repartidos = nivel == "cuadros"
    avisos = []

    try:
        # 1. El video, solo si hacen falta cuadros. Liviano: 720p como mucho y,
        #    si se puede, sin audio (en un video doblado podría traer otro idioma).
        video, vinfo = None, None
        if repartidos or momentos:
            if es_local:
                video = local
            else:
                video = archivo_bajado(carpeta, "video")
                if not video:
                    aviso("Bajando el video (720p como mucho)...")
                    r = a._bajador.correr(["-f", "bv/b", "-S", "res:720,vcodec:h264", "--no-part",
                                           "-o", str(carpeta / "video.%(ext)s")] + origen, 3600)
                    video = archivo_bajado(carpeta, "video")
                    if not video:
                        raise Falla(explicar_error_ytdlp(r.stderr, a.link))
            vinfo = sondear(h, video)
            if vinfo["duracion"]:
                datos["duracion_seg"] = round(vinfo["duracion"], 1)

        # 2. El texto.
        texto = paso_texto(a, h, carpeta, tmp, meta, origen, es_local, local, video, previo, datos)
        if texto.get("error"):
            avisos.append(texto.pop("error"))
            if nivel == "texto":
                raise Falla(avisos[-1])

        # 3. Los cuadros.
        dur = float(datos.get("duracion_seg") or 0)
        horas, corto = dur >= 3600, 0 < dur < CORTO_SEG
        letra = fuente_de_letra()
        carpeta_cuadros = carpeta / "cuadros"
        hojas, hojas_momentos, lista_cuadros, sin_etiqueta = [], [], [], False
        tandas = []
        if repartidos:
            tandas.append(("hoja", tiempos_repartidos(dur, a.cuadros)))
        if momentos:
            tandas.append(("momentos", [min(max(0.0, t), max(0.0, dur - 0.3)) if dur else t
                                        for t in momentos]))
        for prefijo, tiempos in tandas:
            carpeta_cuadros.mkdir(exist_ok=True)
            aviso(f"Sacando {len(tiempos)} cuadros...")
            hechos = []
            for t in tiempos:
                ruta = carpeta_cuadros / nombre_cuadro(t)
                ok = sacar_cuadro(h, video, t, ruta, vinfo, horas, letra)
                if ok:
                    hechos.append((t, ruta))
                    sin_etiqueta = sin_etiqueta or ok == "sin_etiqueta"
            if not hechos:
                raise Falla("No pude sacar cuadros del video (ffmpeg no pudo leerlo).")
            lista_cuadros += [{"seg": round(t, 1), "minuto": reloj(t, horas, decimas=True),
                               "archivo": str(ruta)} for t, ruta in hechos]
            armadas = armar_hojas(h, hechos, prefijo, carpeta, vinfo, tmp)
            (hojas if prefijo == "hoja" else hojas_momentos).extend(armadas)
        if sin_etiqueta:
            avisos.append("ffmpeg no pudo escribir el minuto sobre algunos cuadros; "
                          "el nombre del archivo dice el segundo (t00012.5.jpg = 0:12.5).")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        if not any(carpeta.iterdir()):
            carpeta.rmdir()   # falló antes de dejar nada: no queda una carpeta vacía

    # 4. info.json y el resumen para Claude.
    datos["nivel"] = nivel or previo.get("nivel") or "texto"
    datos["texto"] = texto
    if lista_cuadros:
        anteriores = {c["archivo"]: c for c in (previo.get("cuadros") or [])}
        anteriores.update({c["archivo"]: c for c in lista_cuadros})
        datos["cuadros"] = sorted(anteriores.values(), key=lambda c: c["seg"])
    elif previo.get("cuadros"):
        datos["cuadros"] = previo["cuadros"]
    if video is not None:
        datos["video"] = str(video)
    elif previo.get("video"):
        datos["video"] = previo["video"]
    (carpeta / "info.json").write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")

    dato("CARPETA", carpeta)
    dato("TITULO", (datos.get("titulo") or "").replace("\n", " "))
    if datos.get("canal"):
        dato("CANAL", datos["canal"])
    dato("PLATAFORMA", datos.get("plataforma"))
    dur = float(datos.get("duracion_seg") or 0)
    dato("DURACION", f"{reloj(round(dur))} ({dur:.0f} s)" if dur else "desconocida")
    dato("NIVEL", (nivel + (" + momentos" if momentos else "")) if nivel else "solo los momentos pedidos")
    transcripcion = carpeta / "transcripcion.txt"
    dato("TRANSCRIPCION", transcripcion if transcripcion.is_file() else "")
    if texto.get("fuente"):
        dato("TEXTO_DE", texto["fuente"] + (" (ya estaba hecha, no se volvió a pagar)"
                                            if texto.get("reusada") else ""))
    if texto.get("costo_usd") is not None and not texto.get("reusada"):
        dato("COSTO_USD", f"{texto['costo_usd']:.4f} ({texto.get('costo')})")
    if datos.get("capitulos"):
        dato("CAPITULOS", len(datos["capitulos"]))
    if video is not None:
        dato("VIDEO", video)
    if lista_cuadros:
        dato("CUADROS", f"{carpeta_cuadros} ({len(lista_cuadros)} cuadros)")
    for ruta, desde, hasta in hojas:
        dato("HOJA", f"{ruta} (de {reloj(desde, horas, corto)} a {reloj(hasta, horas, corto)})")
    for ruta, desde, hasta in hojas_momentos:
        dato("MOMENTOS", f"{ruta} (de {reloj(desde, horas, True)} a {reloj(hasta, horas, True)})")
    dato("INFO", carpeta / "info.json")
    for texto_aviso in avisos:
        dato("AVISO", texto_aviso)
    dato("TIEMPO", f"{time.time() - inicio:.1f} s")
    return 0


def main(argv=None):
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(
        prog="ver_video.py", description="Baja un video y saca su texto y sus cuadros para Claude.",
        epilog="Ejemplo: python ver_video.py https://www.youtube.com/watch?v=... --nivel texto")
    p.add_argument("link", nargs="?", help="link del video o ruta de un archivo de video")
    p.add_argument("carpeta", nargs="?", help="dónde dejar todo (por defecto ./ver-video/<id>)")
    p.add_argument("--nivel", choices=["texto", "cuadros"],
                   help="texto: solo el texto. cuadros: texto y cuadros.")
    p.add_argument("--cuadros", type=int, metavar="N", help="cuántos cuadros repartir en el video")
    p.add_argument("--en", metavar="MOMENTOS", help="cuadros en momentos exactos: 0:05,1:20.5")
    p.add_argument("--transcribir", action="store_true",
                   help="transcribir el audio aunque haya subtítulos")
    p.add_argument("--transcriptor", choices=["groq", "openrouter"],
                   help="qué servicio usar si tienes las dos llaves")
    p.add_argument("--navegador", help="navegador con tu sesión iniciada (chrome, firefox, edge, safari)")
    p.add_argument("--revisar", action="store_true",
                   help="revisa que esté todo instalado y que la llave funcione")
    a = p.parse_args(argv)
    if a.revisar:
        return revisar()
    if not a.link:
        p.print_help()
        return 2
    if a.cuadros is not None and a.cuadros < 1:
        p.error("--cuadros tiene que ser 1 o más")
    try:
        return ver(a, time.time())
    except Falla as e:
        dato("ERROR", e)
        return 1
    except KeyboardInterrupt:
        dato("ERROR", "cancelado")
        return 130


if __name__ == "__main__":
    sys.exit(main())
