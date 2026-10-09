# ver-video · Ojos para Claude Code

Una skill para Claude Code que le permite **ver cualquier video**. Le pasas el link, le dices qué
quieres saber y listo.

Claude baja el video y saca el texto: si es de YouTube y tiene subtítulos, usa esos; si no, lo
transcribe. Si hace falta, saca cuadros de los momentos clave para **ver** lo que pasa en pantalla.
Con las dos cosas te responde, con los minutos.

Funciona con YouTube, Instagram, TikTok y más de mil páginas de video (todas las que soporta
[yt-dlp](https://github.com/yt-dlp/yt-dlp)), y también con videos que tengas en tu computadora.

## Qué puedes pedirle

- **Entender un video de YouTube sin verlo.** *"Resúmeme este video y dime qué recomienda sobre
  precios: <link>"*.
- **Encontrar lo que sirve en un crudo largo.** *"En esta grabación de 40 minutos, encuéntrame los
  mejores momentos para clips: <ruta del archivo>"*.
- **Desarmar un reel viral.** *"Desármame este reel: <link>"*. Te dice el gancho visual, el gancho
  de texto, cómo se desarrolla y cómo cierra.
- **Armar una página de referencia de un reel.** Bloque por bloque: lo que se dice, lo que se hace
  y la captura de ese momento, en una página que puedes abrir, mandar o imprimir para guionizar o
  grabar el tuyo.

## Dos niveles, eliges en cada pedido

| Solo texto | Texto y cuadros |
|---|---|
| Para entender de qué trata un video largo. Más rápido y gasta menos del límite de Claude. | Cuando importa cómo se ve: el gancho visual de un reel, una pantalla, una animación. |

Si no lo dices, Claude elige según lo que pediste.

## Cómo se instala

Abre Claude Code y escríbele:

> Instala esta skill siguiendo el archivo INSTALAR.md: https://github.com/elmigue17/ver-video

Claude revisa lo que te falta, lo instala, te ayuda a crear la llave para transcribir y prueba con un
video corto. Si quieres, antes te revisa el código.

## Qué necesitas

- [Claude Code](https://claude.com/claude-code), en Windows, Mac o Linux.
- Python 3, yt-dlp y ffmpeg. Si te faltan, Claude los instala.
- Una llave para transcribir, de [Groq](https://console.groq.com) o de
  [OpenRouter](https://openrouter.ai). Solo se usa cuando el video no tiene subtítulos.

No hace falta n8n, ni un servidor, ni ninguna otra cuenta.

## Cuánto cuesta

- **Bajar el video y sacar los cuadros:** gratis. Pasa todo en tu computadora.
- **Un video de YouTube con subtítulos:** nada.
- **Transcribir** (Instagram, TikTok, videos sin subtítulos, archivos tuyos): centavos de dólar.
  Con las tarifas publicadas en octubre de 2026, un reel de 1 minuto sale menos de 0,001 USD y un
  video de 10 minutos, menos de 0,01 USD. Groq además tiene un plan gratis con un tope por hora.
- **Claude** usa el límite de tu plan, como cualquier otra tarea. Los cuadros son imágenes y gastan
  más que el texto: por eso existe el nivel "solo texto".

## Privacidad

- El video se baja a tu computadora y ahí se queda.
- Lo único que sale es el audio, al servicio de transcripción que elegiste, y solo cuando el video
  no tiene subtítulos.
- Tu llave queda en `~/.claude/skills/ver-video/.env`, en tu computadora. Ese archivo no se sube a
  ningún lado. El código no tiene llaves escondidas ni manda nada a otro lado: puedes pedirle a
  Claude que lo revise antes de instalar.
- Si Instagram pide iniciar sesión, yt-dlp usa la sesión de tu navegador solo para pedirle el video
  a Instagram.

Úsalo con videos que tengas derecho a ver y respetando las reglas de cada plataforma.

## Qué hay en este repositorio

```
skill/ver-video/
  SKILL.md                     lo que lee Claude: cuándo usar la skill y cómo responder
  scripts/ver_video.py         baja el video, saca el texto y los cuadros
  scripts/pagina_referencia.py arma la página de referencia bloque por bloque
  .env.example                 dónde va la llave (el .env de verdad no se sube)
INSTALAR.md                    las instrucciones que sigue Claude Code para instalarla
```

## Licencia

MIT. Úsalo, cámbialo y compártelo.

---

Hecho por **Miguel Pozo** · Zolvinta ([zolvinta.com](https://zolvinta.com))

¿Prefieres que te lo deje funcionando en tu negocio? Escríbeme por WhatsApp:
https://wa.me/51918324015
