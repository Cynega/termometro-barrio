# Termómetro del Barrio · CABA

Visualización de reclamos ciudadanos por barrio en la Ciudad de Buenos Aires,
usando datos abiertos del SUACI (Sistema Único de Atención Ciudadana / BA 147).

**Demo en vivo:** https://[tu-sitio].netlify.app

---

## Estructura del proyecto

```
termometro-barrio/
├── index.html        ← La app (toda la UI)
├── data.js           ← Datos de los 48 barrios (generado por pipeline.py)
├── pipeline.py       ← Descarga y procesa datos reales del SUACI
├── README.md
└── .gitignore
```

---

## Opción A: Abrir directamente (sin datos reales)

Abrí `index.html` en tu navegador. Ya funciona con datos de ejemplo para
los 48 barrios. Verás un aviso amarillo hasta que conectes datos reales.

---

## Opción B: Datos reales del SUACI (recomendado)

### Paso 1 — Instalar dependencias Python

```bash
pip install pandas requests duckdb tqdm
```

Si querés también clasificar conceptos con IA (opcional):
```bash
pip install anthropic
```

### Paso 2 — Correr el pipeline

```bash
# Procesa los años 2023 y 2024 (más rápido, ~5 min)
python pipeline.py --export

# Para procesar el historial completo 2018-2024 (~15 min)
python pipeline.py --full --export
```

Esto descarga los CSV de data.buenosaires.gob.ar, los procesa y
sobreescribe `data.js` con datos reales de los 48 barrios.

### Paso 3 — Verificar

Abrí `index.html`. El aviso amarillo debería desaparecer.

### Paso 4 — Actualizar datos (cuándo hacerlo)

El SUACI se actualiza continuamente. Para mantener la app actualizada
podés correr el pipeline mensual o trimestralmente y hacer un nuevo commit.

---

## Opción C: Publicar en Netlify (gratis, sin servidor)

### Paso 1 — Subir a GitHub

```bash
git init
git add .
git commit -m "primera versión"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/termometro-barrio.git
git push -u origin main
```

### Paso 2 — Conectar con Netlify

1. Entrá a https://netlify.com y creá una cuenta gratuita (podés usar GitHub)
2. Hacé clic en **"Add new site" → "Import an existing project"**
3. Conectá tu cuenta de GitHub y elegí el repositorio `termometro-barrio`
4. Configuración de build:
   - Build command: (dejarlo vacío)
   - Publish directory: `.` (punto, significa la raíz)
5. Hacé clic en **"Deploy site"**

En 30 segundos tenés una URL tipo `https://nombre-aleatorio.netlify.app`.
Podés cambiarla en Site Settings → Domain Management → Change site name.

### Paso 3 — Actualizar la app en el futuro

Cada vez que hagas `git push`, Netlify re-despliega automáticamente.
Es decir: corrés el pipeline → hacés commit → push → la web se actualiza sola.

```bash
# Flujo de actualización mensual
python pipeline.py --export
git add data.js
git commit -m "datos actualizados $(date +%Y-%m)"
git push
```

---

## Agregar tu dominio personalizado (opcional)

En Netlify → Site Settings → Domain Management → Add custom domain.
Si tenés un dominio (ej. `termometroba.com.ar`), podés apuntarlo ahí.
Netlify da HTTPS gratis automáticamente.

---

## Preguntas frecuentes

**¿Necesito un servidor o backend?**
No. Todo funciona como archivos estáticos. No hay base de datos online,
no hay costos de infraestructura. El pipeline corre en tu computadora
y genera un archivo `data.js` estático que la app lee directamente.

**¿Puedo compartir links por barrio?**
Sí. La app actualiza la URL al cambiar de barrio: `?b=palermo`, `?b=boedo`, etc.
Podés compartir `https://tu-sitio.netlify.app?b=villa_lugano` directamente.

**¿Por qué los datos dicen "ejemplo"?**
Porque `pipeline.py` aún no corrió. Los datos reales requieren descargar
los CSV del SUACI desde data.buenosaires.gob.ar, que pesa varios MB.

**¿Cuánto cuesta?**
Nada. Netlify Free incluye 100GB de tráfico por mes, más que suficiente.
GitHub también es gratuito para repositorios públicos.

---

## Fuente de datos

- **SUACI / BA 147:** https://data.buenosaires.gob.ar/dataset/sistema-unico-atencion-ciudadana
- **Licencia:** CC-BY-2.5-AR (podés usarlos, modificarlos y compartirlos con atribución)
- **Responsable:** Secretaría de Atención y Gestión Ciudadana · GCBA

---

## Próximas ideas

- [ ] Tarjeta compartible para redes sociales por barrio
- [ ] Comparación entre dos barrios en paralelo
- [ ] Mapa de calor de CABA con temperatura de los 48 barrios
- [ ] Alertas de nuevos picos (newsletter semanal)
- [ ] Clasificación con IA para reagrupar conceptos similares
