# INSTALAR.md · Instrucciones para Claude Code

> **Si eres una persona:** no tienes que seguir esto a mano. Abre Claude Code y escríbele:
> *"Instala esta skill siguiendo el archivo INSTALAR.md: https://github.com/elmigue17/ver-video"*.
>
> **Si eres Claude Code:** este archivo es tu guion. Síguelo en orden, paso por paso, sin saltarte
> ninguno y sin adelantarte. Al final de cada paso hay un **Listo cuando**: no pases al siguiente
> hasta que se cumpla.

## Reglas para toda la instalación

1. **Una pregunta por vez.** Haz una pregunta, espera la respuesta y recién ahí la siguiente.
2. **Habla simple.** Español neutro, tuteo, frases cortas. Si usas una palabra técnica (terminal,
   llave de API, variable de entorno), explícala en una línea la primera vez.
3. **La llave no se muestra nunca.** No la repitas en el chat, no la escribas en ningún archivo que
   no sea `~/.claude/skills/ver-video/.env` y no muestres ese archivo en pantalla (nada de `cat`,
   `type` ni `Get-Content` sobre él). Para comprobarla usa `--revisar`, que no la imprime.
4. **Nada sale de su computadora sin preguntar.** No crees repositorios, no publiques, no subas
   archivos.
5. **Antes de cada comando que cambia algo** (instalar, copiar, crear un archivo), di en una línea qué
   va a hacer. Al terminar cada paso, di en una línea qué quedó hecho.
6. **Si algo falla:** explica qué pasó en palabras simples, busca la solución en
   [Si algo falla](#si-algo-falla) y no sigas hasta resolverlo.
7. **Comandos:** usa la herramienta Bash (en Windows es Git Bash, viene con Claude Code). Si un
   comando de Windows necesita PowerShell, está indicado.

---

## Paso 0 · Antes de tocar nada

Cuéntale a la persona, en un mensaje corto:

- Qué vas a hacer: bajar este repositorio, revisar que tenga Python, yt-dlp y ffmpeg (e
  instalarlos si faltan), copiar la skill a su carpeta de skills de Claude Code, ayudarle a crear
  una llave para transcribir y probar con un video corto. Entre 10 y 15 minutos.
- Qué es cada cosa: **yt-dlp** baja videos de YouTube, Instagram, TikTok y más de mil páginas;
  **ffmpeg** saca los cuadros y prepara el audio; **Python** corre el script de la skill.
- Que todo pasa en su computadora. Lo único que sale es el pedido del video a la página de origen y,
  cuando el video no tiene subtítulos, el audio al servicio de transcripción que elija (Groq u
  OpenRouter). Su llave queda guardada en su computadora, en un archivo que no se sube a ningún lado.

Después pregunta: **"Antes de instalar, ¿quieres que revise el código para confirmar que no manda
tus datos a ningún lado y que no tiene llaves escondidas?"**

Si dice que sí (cuando el repositorio ya esté bajado, en el paso 1), revísalo de verdad y cuéntale
lo que encontraste, con las rutas de los archivos:

- Busca toda dirección web en `skill/ver-video/scripts/` (`http://`, `https://`, `urlopen`,
  `Request(`). Lo esperable: solo `api.groq.com` y `openrouter.ai`, para transcribir el audio y para
  comprobar que la llave funciona. El video lo pide yt-dlp a la página del link.
- Busca llaves o tokens escritos en el código (`key`, `token`, `secret`, `Bearer`). No tiene que
  haber ninguno: la llave se lee del entorno o de `~/.claude/skills/ver-video/.env`, y `.env` está en
  `.gitignore`.
- Mira los `import` de los dos scripts: solo la biblioteca estándar de Python. Nada de analítica
  ni de rastreo.
- Cuéntale qué guarda en disco: una carpeta `ver-video/<id del video>` donde esté trabajando, con
  el texto, los cuadros y (si pidió cuadros) el video a 720p. La puede borrar cuando quiera.

**Listo cuando:** la persona sabe qué va a pasar y, si lo pidió, tiene el resultado de la revisión.

## Paso 1 · Bajar el repositorio

1. Bájalo a una carpeta temporal:
   `git clone https://github.com/elmigue17/ver-video.git "$HOME/ver-video-instalador"`.
   Si no hay git, baja el ZIP desde el botón **Code > Download ZIP** del repositorio y
   descomprímelo en esa carpeta.
2. Si en el paso 0 pidió la revisión del código, hazla ahora.

**Listo cuando:** existe `$HOME/ver-video-instalador/skill/ver-video/SKILL.md`.

## Paso 2 · Python, yt-dlp y ffmpeg

1. Comprueba qué hay, sin instalar nada todavía:
   `python --version` (o `python3 --version`, o `py --version`), `yt-dlp --version`,
   `ffmpeg -version` y `ffprobe -version`.
2. Dile qué falta y, con su OK, instálalo:
   - **Windows:** `winget install -e --id yt-dlp.yt-dlp` instala yt-dlp y, junto con él, ffmpeg y
     Deno (Deno es un programa que yt-dlp usa con YouTube). Si falta Python:
     `winget install -e --id Python.Python.3.12`.
   - **Mac:** `brew install python yt-dlp ffmpeg` (brew trae Deno con yt-dlp). Si no tiene
     Homebrew, pregúntale antes de instalarlo desde https://brew.sh.
   - **Linux (Debian o Ubuntu):** `sudo apt install python3 ffmpeg pipx` y
     `pipx install "yt-dlp[default,curl-cffi]"`.
   - Si ya tenía yt-dlp instalado con `pip`, puede que le falte la parte que usa TikTok
     (`curl_cffi`). Lo vas a ver en el paso 3 con `--revisar`.
3. En Windows, los programas recién instalados a veces no aparecen hasta abrir una terminal nueva.
   El script los busca igual donde los deja winget, así que sigue con el paso 3 y revisa ahí.

**Listo cuando:** hay Python 3.8 o más nuevo y los comandos de yt-dlp y ffmpeg responden (o los
instalaste y vas a comprobarlos con `--revisar` en el paso siguiente).

## Paso 3 · Copiar la skill

1. Mira si ya existe `~/.claude/skills/ver-video`. Si existe, pregunta si quiere reemplazarla por
   esta versión. Al reemplazar, **conserva su archivo `.env`** (ahí está su llave).
2. Copia la skill:

   ```bash
   mkdir -p "$HOME/.claude/skills/ver-video"
   cp -r "$HOME/ver-video-instalador/skill/ver-video/." "$HOME/.claude/skills/ver-video/"
   ```

3. Revisa la instalación: `python "$HOME/.claude/skills/ver-video/scripts/ver_video.py" --revisar`
   (con `python3` o `py` si así se llama en su computadora). Tiene que decir que están yt-dlp,
   ffmpeg y ffprobe. Las llaves todavía van a decir "no configurada".
4. Si la línea `TIKTOK=` dice que falta `curl_cffi`, explícale que sin eso no va a poder ver videos
   de TikTok y, con su OK, corre el comando que indica esa línea.

**Listo cuando:** `--revisar` muestra `LISTO=1`. Si dice `FALTA` en algo que acabas de instalar,
mira [Si algo falla](#si-algo-falla).

## Paso 4 · La llave para transcribir

Explícale en pocas líneas:

- Si el video es de YouTube y tiene subtítulos, la skill usa esos: no hace falta llave ni cuesta nada.
- Para Instagram, TikTok, videos sin subtítulos y videos de su computadora, el audio se manda a un
  servicio que lo pasa a texto. Cuesta centavos de dólar por video, y para eso hace falta una llave
  (una contraseña que le da el servicio para usarlo desde la computadora).
- Hay dos opciones:
  - **Groq** (la más simple para empezar): tiene un plan gratis, sin tarjeta, con un tope de audio
    por hora que alcanza para el uso normal. Si algún día lo pasa, el plan pago cuesta 0,04 USD por
    hora de audio.
  - **OpenRouter**: conviene si ya tiene cuenta y saldo ahí. Funciona con saldo prepago (se carga
    con tarjeta, con un monto mínimo y una comisión) y transcribir cuesta alrededor de 0,01 USD por
    hora de audio.

Pregunta: **"¿Cuál prefieres: Groq u OpenRouter?"**

Guíalo **de a una acción por mensaje** y espera su "listo" en cada una.

### Si elige Groq

1. Que entre a https://console.groq.com y cree una cuenta (con Google, GitHub o su email).
2. Que vaya a https://console.groq.com/keys y toque **Create API Key**. Nombre: `ver-video`. Que
   la confirme.
3. Groq muestra la llave **una sola vez**: que la copie y no cierre la ventana todavía.

### Si elige OpenRouter

1. Que entre a https://openrouter.ai y cree una cuenta (**Sign in**).
2. Que cargue saldo en https://openrouter.ai/settings/credits (**Add credits**). Con el monto
   mínimo le alcanza para muchísimas horas de audio.
3. Que vaya a https://openrouter.ai/settings/keys y toque **Create**. Nombre: `ver-video`. Si
   quiere, que le ponga un límite de gasto (por ejemplo 2 USD), así esa llave nunca gasta más.
4. OpenRouter muestra la llave **una sola vez**: que la copie.

### Guardar la llave

1. Crea el archivo de la llave a partir del ejemplo:
   `cp "$HOME/.claude/skills/ver-video/.env.example" "$HOME/.claude/skills/ver-video/.env"`
2. Ábrelo para que la persona pegue la llave ella misma (así la llave no pasa por el chat):
   - Windows (PowerShell): `notepad "$env:USERPROFILE\.claude\skills\ver-video\.env"`
   - Mac: `open -e "$HOME/.claude/skills/ver-video/.env"`
   - Linux: `xdg-open "$HOME/.claude/skills/ver-video/.env"`
3. Dile: *"Pega la llave justo después de `GROQ_API_KEY=` (o de `OPENROUTER_API_KEY=`), sin
   espacios ni comillas. Guarda (Ctrl+S o Cmd+S), cierra y avísame."*
4. Si prefiere pegártela en el chat, guárdala tú en ese archivo con una sola edición y no la
   repitas en tus mensajes. Cuéntale que, como quedó en la conversación, si algún día quiere puede
   borrarla en Groq u OpenRouter y crear otra.
5. Comprueba: `python "$HOME/.claude/skills/ver-video/scripts/ver_video.py" --revisar`. Tiene que
   decir `configurada (archivo .env de la skill), funciona`.

**Listo cuando:** `--revisar` dice que la llave funciona.

## Paso 5 · Probar con un video corto

1. Prueba en una carpeta temporal con el primer video que se subió a YouTube (19 segundos). La
   opción `--transcribir` obliga a usar la llave aunque el video tenga subtítulos, para probarla de
   verdad:

   ```bash
   mkdir -p "$HOME/ver-video-prueba" && cd "$HOME/ver-video-prueba"
   python "$HOME/.claude/skills/ver-video/scripts/ver_video.py" "https://www.youtube.com/watch?v=jNQXAC9IVRw" --nivel cuadros --transcribir
   ```

2. Mira la hoja de cuadros (`HOJA=`) con Read y lee la transcripción (`TRANSCRIPCION=`).
3. Cuéntale en dos o tres líneas qué se ve y qué se dice, con el minuto, y cuánto costó
   (`COSTO_USD=`, menos de un décimo de centavo). Así ve lo que va a pasar cada vez que te pase un
   video.
4. Borra la carpeta de prueba: `rm -rf "$HOME/ver-video-prueba"`.

**Listo cuando:** la prueba terminó sin `ERROR=` y la persona vio el resultado.

## Paso 6 · Cerrar

1. Pregúntale si quiere borrar la carpeta del instalador (`$HOME/ver-video-instalador`). La skill
   ya quedó copiada; esa carpeta no hace falta.
2. Dile que **cierre Claude Code y abra una sesión nueva**: recién ahí Claude ve la skill.
3. Dale ejemplos de lo que puede pedir, en un solo mensaje:
   - *"Resúmeme este video de YouTube: <link>"* (solo texto, rápido).
   - *"Desármame este reel: <link>. Quiero entender el gancho."* (texto y cuadros).
   - *"En este crudo, encuéntrame los mejores momentos para clips: <ruta del archivo>"*.
   - *"Arma la página de referencia de este reel, bloque por bloque, para grabar el nuestro."*
4. Cuéntale que puede elegir el nivel en cada pedido: "solo el texto" o "con cuadros". Solo texto
   es más rápido y gasta menos del límite de Claude; con cuadros, Claude ve lo que pasa en pantalla.

**Listo cuando:** la persona sabe que tiene que abrir una sesión nueva y qué puede pedir.

---

## Si algo falla

| Qué pasa | Qué hacer |
|---|---|
| `python` no responde o abre la Microsoft Store | Instala Python con `winget install -e --id Python.Python.3.12`. Si igual abre la Store, que desactive los alias en **Configuración > Aplicaciones > Configuración avanzada de aplicaciones > Alias de ejecución de aplicaciones** (apagar `python.exe` y `python3.exe`), o usa `py` en lugar de `python`. |
| `winget` no se reconoce | Que instale o actualice **Instalador de aplicación** desde la Microsoft Store y abra una terminal nueva. |
| `--revisar` dice `FALTA` justo después de instalar | La terminal todavía no ve los programas nuevos. Que cierre Claude Code, lo abra de nuevo y repite `--revisar`. |
| Mac: error de certificados (`CERTIFICATE_VERIFY_FAILED`) | El Python bajado de python.org necesita sus certificados: que abra **Aplicaciones > Python 3.x > Install Certificates.command**. O usa el Python de brew. |
| La llave dice `NO funciona (401)` | Se copió incompleta o con espacios. Que la vuelva a pegar en el `.env` (o cree otra). |
| `ERROR=` con "pasaste el límite" (429) | En Groq, el plan gratis tiene un tope por hora. Esperar un rato. |
| `ERROR=` con "no tiene saldo" (402) | En OpenRouter, cargar saldo. |
| `ERROR=` con "pide iniciar sesión" (Instagram) | Que abra el video en Chrome con su cuenta, cierre Chrome del todo y repite. O que inicie sesión en Firefox y repite con `--navegador firefox`. |
| TikTok falla con "Unexpected response" o pide `curl_cffi` | A yt-dlp le falta `curl_cffi`. Instálalo con winget o brew, o corre `python -m pip install -U "yt-dlp[default,curl-cffi]"`. |
| YouTube falla con un error de formatos o de JavaScript | Actualiza yt-dlp (`winget upgrade yt-dlp.yt-dlp`, `brew upgrade yt-dlp` o `yt-dlp -U`). En Windows, si falta Deno: `winget install -e --id DenoLand.Deno`. |
