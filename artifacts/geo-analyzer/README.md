# GeoAnalyzer — Street View AI Analyzer

Ventana flotante para Windows que analiza tu pantalla en tiempo real usando OpenAI Vision y devuelve predicciones de ubicación GeoGuessr.

## ¿Cómo funciona?

```
Tu pantalla (Street View)
  → desktopCapturer (Electron)
  → recorte de región seleccionada
  → compresión JPEG 85%
  → OpenAI gpt-4o Vision (low detail)
  → JSON estructurado
  → ventana flotante siempre visible
  → log JSONL diario en AppData
```

## Requisitos

- **Node.js 18+** (recomendado 20 LTS)
- **pnpm** (`npm install -g pnpm`)
- **Cuenta OpenAI** con acceso a `gpt-4o`

## Instalación y ejecución (desarrollo)

```bash
# Clonar / descargar el proyecto
cd geo-analyzer

# Instalar dependencias
pnpm install

# Ejecutar en modo desarrollo
pnpm dev
```

La app se abre automáticamente como ventana flotante.

## Compilar instalador para Windows

```bash
# Build + crear instalador NSIS para Windows
pnpm dist:win
```

El instalador `.exe` aparece en `release/`.

> Si compilas desde Linux/Mac, instala `wine` y `mono` para cross-compile:
> ```bash
> # Ubuntu/Debian
> sudo apt install wine64 mono-complete
> ```

## Uso de la app

### 1. Configurar API Key
- Abre la pestaña **⚙ Settings**
- Pega tu OpenAI API key (`sk-...`)
- Pulsa **Save API Key** (se guarda localmente, nunca sale de tu máquina)

### 2. Seleccionar región
- Pulsa **🔲 Select Region** 
- Aparece una overlay transparente sobre toda la pantalla
- Haz click y arrastra para encuadrar el área de Street View
- Suelta el mouse para confirmar
- La región se guarda para futuras sesiones

### 3. Analizar
- Pulsa **▶ Start**
- La app captura la región cada **5 segundos** y la manda a OpenAI
- Las predicciones aparecen en la pestaña **📍 Predict**:
  - País y ciudad probables
  - Lugar exacto (si reconocible)
  - Coordenadas aproximadas con link a Google Maps
  - Nivel de confianza (high / medium / low)
  - Pistas detectadas (señales, vegetación, arquitectura, etc.)
- Pulsa **⏹ Stop** para parar

### 4. Logs
- Pestaña **📋 Logs** — últimas 50 predicciones del día
- **📁 Open Folder** — abre la carpeta de logs (`AppData\Roaming\GeoAnalyzer\`)
- Formato: `predictions-YYYY-MM-DD.jsonl` (un JSON por línea)
- Útil para detectar fallos en tu página o analizar patrones de predicción

## Estructura de logs

Cada entrada del log:
```json
{
  "timestamp": "2026-06-17T14:32:01.123Z",
  "prediction": {
    "country": "Japan",
    "city": "Tokyo",
    "exact_location": "Shibuya Crossing",
    "coordinates": { "lat": 35.6595, "lng": 139.7004 },
    "confidence": "high",
    "clues": ["Japanese kanji signs", "right-hand traffic", "dense urban grid", "Yamanote line overpass"]
  },
  "region": { "x": 120, "y": 80, "width": 1200, "height": 700 }
}
```

## Configuración actual

| Parámetro | Valor |
|---|---|
| Modelo | `gpt-4o` |
| Detail level | `low` (más rápido, suficiente para geo) |
| Intervalo de captura | 5 segundos |
| Calidad imagen | JPEG 85% |
| Max tokens respuesta | 400 |
| Logs | `%APPDATA%\GeoAnalyzer\prediction-logs\` |

## Optimización de velocidad

- `detail: "low"` en la API → latencia ~1-3s en lugar de ~5-10s
- JPEG 85% reduce el tamaño sin perder las pistas visuales clave
- Max tokens 400 evita respuestas largas innecesarias
- El intervalo real es 5s por defecto (el análisis tarda ~2-4s)

## Troubleshooting

**"No region selected"** → Usa Select Region antes de Start

**"Failed to capture screen region"** → En Windows, da permisos de captura de pantalla a la app en Configuración → Privacidad → Captura de pantalla

**"Parse error"** → OpenAI devolvió formato inesperado. El log guarda el raw para debug.

**La overlay de selección no desaparece** → Pulsa ESC o el botón Cancel

**La ventana no está siempre encima** → En Windows 11, algunas apps de pantalla completa bloquean esto; minimízalas primero
