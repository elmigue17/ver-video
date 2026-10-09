---
name: ver-video
description: Le da ojos a Claude para ver un video de YouTube, Instagram, TikTok o cualquier página que soporte yt-dlp, o un archivo de video de la computadora. Baja el video, saca el texto (los subtítulos de YouTube o una transcripción del audio) y, cuando importa cómo se ve, cuadros de los momentos clave con el minuto escrito encima; con las dos cosas responde lo que el usuario quiere saber, con los minutos. Úsala cuando el usuario pase un link de video o diga "mira este video", "qué dice este reel", "desármame este reel", "resúmeme este video de YouTube", "de qué trata este video", "qué se ve en el minuto 3", "encuéntrame lo que sirve de este crudo", "sácame el gancho de este reel", "arma la página de referencia de este reel" o "quiero grabar algo como esto".
---

# ver-video

El usuario te pasa un video y te dice qué quiere saber. Tú lo bajas con el script, miras los
cuadros, lees el texto y respondes a eso, con los minutos. Nada más: no hace falta que te pida
"usa la skill".

## 1. Elige el nivel

| Nivel | Qué baja | Cuándo |
|---|---|---|
| `texto` | Solo el texto | Entender de qué trata un video, resumirlo, buscar qué dice sobre algo, encontrar momentos en un crudo largo. Es más rápido y gasta mucho menos del límite de Claude. |
| `cuadros` | Texto y cuadros | Cuando importa cómo se ve: el gancho visual de un reel, el texto en pantalla, una pantalla o una herramienta que muestra, una animación, cómo está grabado. |

- Si el pedido lo deja claro, elige tú sin preguntar. "Desármame este reel" es `cuadros`;
  "resúmeme este video de 40 minutos" es `texto`.
- Si no se puede saber, usa `cuadros` para videos cortos (reels, shorts, TikToks) y `texto`
  para los largos. Di en una línea qué nivel usaste y, al final, ofrece el otro si sirve.
- Si el usuario nombra el nivel ("solo el texto", "con cuadros", "míralo bien"), respétalo.

## 2. Corre el script

Con la herramienta Bash (en Windows también: es Git Bash). La carpeta de esta skill es la que
aparece como "Base directory" al cargarla; normalmente `~/.claude/skills/ver-video`.

```bash
python "$HOME/.claude/skills/ver-video/scripts/ver_video.py" "<link o ruta del archivo>" --nivel texto
python "$HOME/.claude/skills/ver-video/scripts/ver_video.py" "<link o ruta del archivo>" --nivel cuadros
```

En Mac y Linux puede ser `python3`; en Windows, si `python` no responde, `py`.

Opciones que vas a usar:

- `--cuadros N`: cuántos cuadros repartir. Por defecto: en un video de menos de 90 s, uno cada
  medio segundo en los primeros 3 s (el gancho) y después uno cada 2 s; en uno largo, entre 18 y 36
  parejos de punta a punta.
- `--en 0:05,1:20.5,3:02`: cuadros justo en esos momentos. Úsalo después de leer el texto, para
  mirar lo que se ve cuando se dice algo. Pasa la misma carpeta (`CARPETA=`) como segundo argumento
  y reusa todo lo ya bajado: no vuelve a bajar ni a pagar nada.
- `--transcribir`: transcribe el audio aunque el video tenga subtítulos (si los subtítulos
  automáticos de YouTube salieron muy mal).

El script deja todo en `./ver-video/<id del video>` (en la carpeta donde estás) y escribe líneas
`CLAVE=valor`:

| Línea | Qué es |
|---|---|
| `CARPETA=` | La carpeta del video. Pásala como segundo argumento en las consultas siguientes. |
| `TRANSCRIPCION=` | El texto con marcas `[MM:SS]`, en el idioma original del video. |
| `TEXTO_DE=` | De dónde salió: subtítulos de YouTube, transcripción con Groq u OpenRouter, o "ya estaba hecha". |
| `COSTO_USD=` | Lo que costó transcribir (0 si eran subtítulos o si ya estaba hecha). |
| `HOJA=` | Hojas de 3x3 con los cuadros repartidos, cada uno con su minuto. |
| `MOMENTOS=` | Hojas con los cuadros que pediste con `--en`. |
| `CUADROS=` | La carpeta con cada cuadro suelto en tamaño completo (`t00012.5.jpg` = segundo 12,5). |
| `INFO=` | `info.json`: título, canal, fecha, duración, descripción del post y capítulos. |
| `AVISO=` | Algo que salió a medias. Cuéntaselo al usuario. |
| `ERROR=` | No se pudo. Explícale al usuario qué pasó con esas palabras (ver la sección 5). |

## 3. Mira y lee

1. **Los cuadros primero, si los hay.** Abre con Read **todas** las `HOJA=`. En un reel, lo
   visual entra antes que lo que se dice. Si un texto en pantalla se ve chico, abre ese cuadro suelto
   de `cuadros/`, que está en tamaño completo.
2. **El texto entero.** Lee `transcripcion.txt` completo, no solo el principio. Si es muy largo,
   por partes hasta el final.
3. **La descripción.** En Instagram y TikTok, la descripción del post (`info.json`) suele traer el
   llamado a la acción o la palabra clave para comentar. En YouTube, los capítulos ayudan a ubicarse.
4. Lo que no está en los cuadros ni en el texto, **no lo inventes**. Si hace falta ver un momento
   que no tienes, pídelo con `--en`.

## 4. Responde a lo que pidió

Siempre con los minutos (`[02:15]`) para que pueda ir al momento. Si citas lo que se dice, cítalo
tal cual. Al final, en una línea, dónde quedó la carpeta.

### Entender un video sin verlo ("resúmeme", "de qué trata", "qué dice sobre X")

Nivel `texto`. Responde a la pregunta, no hagas un resumen genérico si preguntó algo puntual.
Para un resumen: la idea central en dos líneas y después las partes con su minuto. Si en algún
momento importa lo que muestra en pantalla ("acá muestra la herramienta"), saca esos cuadros con
`--en` antes de describirlos.

### Encontrar lo que sirve en un crudo largo

Nivel `texto` (el crudo suele ser un archivo de la computadora: pasa la ruta). Devuelve una lista
de momentos útiles con desde y hasta (`[12:40] a [13:55]`), qué se dice en cada uno y por qué sirve
(un buen gancho, una historia, una frase para un clip, una explicación completa). Marca también lo
que conviene cortar (repeticiones, tomas falladas, silencios largos). Si el usuario necesita elegir
por cómo se ve, saca cuadros de esos momentos con `--en`.

### Desarmar un reel ("desármame este reel", "por qué funcionó", "sácame el gancho")

Nivel `cuadros`. En este orden, porque así lo vive quien lo mira:

1. **Gancho visual (0 a 3 s):** qué se ve apenas arranca: el plano, la persona, qué sostiene o
   señala, el fondo, el movimiento, cualquier cosa que frene el dedo. Sale de los cuadros del
   primer medio segundo en adelante.
2. **Gancho de texto:** el texto en pantalla tal cual (si hay) y la primera frase que se dice.
   Qué promete, qué creencia rompe o qué tensión abre.
3. **Desarrollo:** cómo sostiene la atención, paso por paso, con minutos. Cambios de plano,
   textos, ejemplos, pruebas.
4. **Cierre:** qué pide (comentar una palabra, seguir, ir al link) y para qué. Revisa la
   descripción del post.
5. **Por qué funciona** en dos o tres líneas, y qué se puede copiar y qué no.

### Página de referencia de un reel, bloque por bloque

Para guionizar o grabar algo parecido: cada bloque con lo que se dice, lo que se hace y la captura.

1. Desarma el reel (arriba) y divídelo en bloques (gancho, cada paso del desarrollo, cierre).
2. Elige el segundo exacto que mejor muestra cada bloque y sácalo con
   `--en` sobre la misma carpeta.
3. **Mira cada captura con Read antes de escribirle nada.** Si no muestra lo que esperabas, pide
   otro segundo o describe lo que sí muestra. Nunca escribas el pie de una captura que no viste.
4. Escribe `bloques.json` en la carpeta del video:

```json
{
  "titulo": "Referencia: reel de @cuenta sobre X",
  "nota": "Para grabar nuestra versión. Lo que importa copiar es el ritmo del gancho.",
  "bloques": [
    {"desde": "0:00", "hasta": "0:03", "rotulo": "Gancho visual",
     "dice": "La frase tal cual se dice.",
     "hace": ["Señala hacia arriba con el índice", "Texto grande en pantalla desde el primer medio segundo"],
     "cuadros": ["0:00", "0:01.5"],
     "mirar": "Dónde está parado y cómo entra el texto."}
  ]
}
```

5. Arma la página:

```bash
python "$HOME/.claude/skills/ver-video/scripts/pagina_referencia.py" "<CARPETA>"
```

Deja `referencia.html` en la carpeta, con las capturas adentro (un solo archivo que se puede
mandar o imprimir). Dale la ruta al usuario y ofrécele abrirla (en Windows `start "" "<ruta>"`, en
Mac `open "<ruta>"`).

### Preguntas puntuales ("qué herramienta usa", "qué se ve en el minuto 4")

Con el texto ubica el momento y saca cuadros con `--en` alrededor (por ejemplo 3:58, 4:00, 4:03).
Responde con lo que se ve en esos cuadros.

## 5. Si algo falla

| Qué dice | Qué hacer |
|---|---|
| `ERROR=` con "No hay llave para transcribir" | El video no tiene subtítulos y no hay llave. Explícale que hace falta una de Groq u OpenRouter y ofrécele configurarla siguiendo el archivo `INSTALAR.md` del repositorio (paso de la llave). Si eligió `cuadros`, igual tienes los cuadros: úsalos. |
| `ERROR=` con "pide iniciar sesión" | Instagram (a veces) pide sesión. Que abra el video en Chrome con su cuenta, cierre Chrome del todo y repites; o que inicie sesión en Firefox y repites con `--navegador firefox`. |
| `ERROR=` con "rechazó la llave" | La llave está mal copiada o se borró. Que cree otra y la pegue en el archivo `.env` de la skill. |
| `ERROR=` con "pasaste el límite" | El plan gratis de Groq tiene un tope por hora. Esperar un rato o usar la otra llave con `--transcriptor openrouter`. |
| `ERROR=` con "Falta instalar" | Instala lo que falta como dice el mensaje. |
| `ERROR=` con "curl_cffi" (TikTok) | A yt-dlp le falta esa parte. Ofrécele correr el comando que dice el mensaje. |
| `ERROR=` de YouTube que habla de formatos o JavaScript | Actualiza yt-dlp (`yt-dlp -U`, `winget upgrade yt-dlp.yt-dlp` o `brew upgrade yt-dlp`) y repite. |

Para revisar la instalación: `python "$HOME/.claude/skills/ver-video/scripts/ver_video.py" --revisar`.
Dice qué está instalado y si la llave funciona, sin mostrarla.

## Reglas

- Nunca muestres ni copies la llave. Vive en `~/.claude/skills/ver-video/.env` o en el entorno.
- Lo único que sale de la computadora es el pedido del video a su página y, si hay que
  transcribir, el audio al servicio elegido. No subas el video ni los cuadros a ningún otro lado.
- Si se transcribió, menciona el costo (`COSTO_USD=`) en la respuesta, en una línea.
- No abras las hojas de cuadros si el nivel es `texto`: para eso el usuario eligió texto.
- La carpeta `ver-video/` se puede borrar cuando ya no sirve; si el usuario va a volver a preguntar
  sobre el mismo video, conviene dejarla (así no se vuelve a bajar ni a pagar).
