# DealBot Dashboard 🎯

Web dashboard para el bot de rastreo de precios en Amazon via WhatsApp.

## Stack

- **Backend:** FastAPI + Jinja2
- **Frontend:** Tailwind CSS (CDN) + HTMX
- **Charts:** Chart.js
- **DB:** SQLite (compartida con deal-tracker)

## Estructura

```
dealbot-dashboard/
├── app/
│   ├── main.py              # FastAPI app + rutas
│   ├── templates/
│   │   ├── base.html        # Layout base (navbar, footer)
│   │   ├── landing.html     # Página de inicio con CTA
│   │   ├── dashboard.html   # Lista de productos por usuario
│   │   └── product.html     # Detalle + historial de precios
│   └── static/
│       └── style.css        # Estilos custom
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Instalación

```bash
cd dealbot-dashboard

# Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Edita .env si necesitas cambiar el path de la DB
```

## Correrlo

```bash
# Desarrollo (con auto-reload)
uvicorn app.main:app --reload --port 8080

# Producción
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Abre: http://localhost:8080

## Variables de entorno

| Variable              | Default                                | Descripción                        |
|-----------------------|----------------------------------------|------------------------------------|
| `DEAL_TRACKER_DB`     | `~/.openclaw/workspace/deal-tracker/deal_tracker.db` | Path a la base de datos SQLite |
| `WHATSAPP_NUMBER`     | `+14155238886`                         | Número de WhatsApp del bot         |
| `WHATSAPP_SANDBOX_JOIN` | `join lucky-spoke`                   | Código sandbox de Twilio           |

## Páginas

| Ruta                     | Descripción                              |
|--------------------------|------------------------------------------|
| `/`                      | Landing page con CTA y explicación       |
| `/dashboard?phone=+1...` | Dashboard del usuario (por número)       |
| `/product/{id}`          | Detalle del producto + historial gráfico |

## API (HTMX)

| Método | Ruta                           | Descripción              |
|--------|--------------------------------|--------------------------|
| `POST` | `/product/{id}/delete`         | Eliminar producto (soft) |
| `POST` | `/product/{id}/target`         | Actualizar precio objetivo|
| `GET`  | `/partials/product-row/{id}`   | Fila de producto (HTMX)  |
