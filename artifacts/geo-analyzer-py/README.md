# GeoAnalyzer — Portable Windows .exe

Ventana flotante siempre encima para analizar tu pantalla con OpenAI Vision.  
Un solo `.exe`. No necesita Node, Python ni nada instalado.

## Cómo obtener el .exe

### Opción A — Build desde Windows (recomendado)

Necesitas Python 3.10+ instalado **una sola vez** para compilar:

```cmd
# En Windows, dentro de esta carpeta:
build.bat
```

O con PowerShell:
```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

El exe final queda en `dist\GeoAnalyzer.exe`.  
Cópialo donde quieras. No necesita nada más.

### Opción B — Build desde GitHub Actions (sin instalar Python)

Sube el código a un repo de GitHub y usa el workflow `.github/workflows/build.yml`  
(incluido) para que GitHub Actions compile el exe automáticamente.

---

## Uso

1. **Abre** `GeoAnalyzer.exe` → aparece ventana flotante siempre encima
2. **⚙ Settings** → pega tu OpenAI API key (`sk-...`) → **Save**
3. **🔲 Select Region** → la pantalla se oscurece, arrastra para encuadrar tu Street View
4. **▶ Start** → captura y analiza automáticamente cada 5 segundos
5. Los resultados aparecen en **📍 Predict** con:
   - País y ciudad probable
   - Lugar exacto (si reconocible)
   - Coordenadas aproximadas
   - Confianza (HIGH / MEDIUM / LOW)
   - Pistas detectadas
6. **📋 Logs** → historial del día en formato JSONL
7. **⏹ Stop** para parar

---

## Dónde guarda los logs

```
C:\Users\TuNombre\AppData\Roaming\GeoAnalyzer\prediction-logs\
  predictions-2026-06-17.jsonl
  predictions-2026-06-18.jsonl
  ...
```

Cada línea es un JSON:
```json
{
  "timestamp": "2026-06-17T14:32:01.123456",
  "prediction": {
    "country": "Japan",
    "city": "Tokyo",
    "exact_location": "Shibuya Crossing",
    "coordinates": { "lat": 35.6595, "lng": 139.7004 },
    "confidence": "high",
    "clues": ["Japanese kanji", "right-hand traffic", "dense urban grid"]
  },
  "region": { "x": 120, "y": 80, "width": 1200, "height": 700 }
}
```

---

## Dependencias del exe (embebidas)

| Librería | Uso |
|---|---|
| `customtkinter` | UI moderna dark |
| `mss` | Captura de pantalla ultra-rápida |
| `Pillow` | Recorte y compresión de imagen |
| `openai` | Llamadas a GPT-4o Vision |

---

## Configuración

| Parámetro | Valor |
|---|---|
| Modelo | `gpt-4o` |
| Detail | `low` (más rápido, suficiente para geo) |
| Intervalo | 5 segundos |
| Calidad imagen | JPEG 85% |
| Max tokens | 400 |

---

## Troubleshooting

**Ventana no aparece encima** → Minimiza otras apps. En Windows 11, algunas apps de pantalla completa bloquean esto.

**Error de captura de pantalla** → Ve a Configuración → Privacidad → Captura de pantalla y permite la app.

**Parse error en predicción** → El raw se guarda en el log. Es raro con gpt-4o.

**Antivirus bloquea el exe** → Normal con PyInstaller. Añade excepción en Windows Defender.
