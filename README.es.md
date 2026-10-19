<p align="center">
  <img src="assets/readme/hero.svg" width="100%" alt="Argo: búsqueda unificada y verificación de evidencia para agentes de IA">
</p>

<p align="center">
  <a href="README.md">中文</a> ·
  <a href="README.en.md">English</a> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ko.md">한국어</a> ·
  <strong>Español</strong>
</p>

<p align="center">
  <a href="#qué-es">Intro</a> ·
  <a href="#por-qué-supera-a-la-búsqueda-del-modelo-la-búsqueda-ia-y-el-metasearch">Comparar</a> ·
  <a href="#enrutamiento-según-la-consulta">Prueba</a> ·
  <a href="#cómo-funciona">Mecanismo</a> ·
  <a href="#inicio-rápido">Inicio rápido</a> ·
  <a href="#capacidades">Capacidades</a> ·
  <a href="#instalación-y-configuración">Config</a> ·
  <a href="#actualizaciones-recientes">Actualizaciones</a>
</p>

<p align="center">
  <img alt="license" src="https://img.shields.io/badge/license-Apache_2.0-blue">
  <img alt="python" src="https://img.shields.io/badge/python-3.9+-green">
  <img alt="version" src="https://img.shields.io/badge/version-2.9.7-informational">
  <img alt="engines" src="https://img.shields.io/badge/engines-266-orange">
  <img alt="mcp" src="https://img.shields.io/badge/MCP-19%20tools-purple">
</p>

> **Este repositorio es parte del conjunto de plugins DeepSeek Harness de taxueseek** ([dsh-files](https://github.com/taxueseek/dsh-files) 39★). Serie de habilidades del mismo autor: [session-digger](https://github.com/taxueseek/session-digger) 29★ · [taxue-invest](https://github.com/taxueseek/taxue-invest) 21★ · [taxueskills](https://github.com/taxueseek/taxueskills) 23★ · [taxue-creative-style](https://github.com/taxueseek/taxue-creative-style) 12★

## Por qué supera a la búsqueda del modelo, la búsqueda IA y el metasearch

> En corto: las tres primeras ayudan a **personas** a encontrar información. Argo ayuda a **agentes** a buscar y verificar en un mismo pipeline. La diferencia no es la interfaz, es el entregable: página de resumen o lista de enlaces para humanos frente a evidencia ordenable, re-verificable y que no hincha el contexto.

<p align="center">
  <img src="assets/readme/why-better.svg" width="100%" alt="Izquierda: tres búsquedas por defecto hechas para humanos; derecha: JSON de evidencia absorbible de Argo para agentes">
</p>

| Dimensión | Búsqueda del modelo | Búsqueda IA (resúmenes) | Metasearch / motores | **Argo** |
|-----------|---------------------|-------------------------|----------------------|----------|
| Forma del resultado | Texto largo cosido | Página de resumen humana | Lista de enlaces SERP | **JSON compacto: candidatos de evidencia + desglose de credibilidad** |
| Preguntas verticales (cotizaciones / fórmulas) | Web genérica | Web genérica y luego resumen | Web genérica | **Fuentes verticales directas, en forma de respuesta** |
| Credibilidad de evidencia | Sin puntuación | Sin puntuación estructurada | Sin puntuación | **selection · absorption · freshness · consenso** |
| Consultas repetidas | Red cada vez | Red cada vez | Caché de página | **Caché de dos capas (memoria + SQLite); consultas calientes ~10 ms** |
| Control de coste | Incontrolable | Caro por llamada | Gratis pero trabajoso | **Modos de presupuesto; gratis primero; claves todas opcionales** |
| Multilingüe | Sigue al modelo | Sigue al modelo | Sigue al motor | **Detección de idioma + params de locale + enrutamiento multilingüe** |

> Mecánicamente, Argo trata la búsqueda como un **pipeline de evidencia**: detectar idioma → enrutar dominio → recall multi-motor → fusionar RRF → ojeada de evidencia. El agente puede ordenar, `fetch` para verificar y mantener el material dentro del contexto.

---

## Qué está cambiando en la búsqueda en 2026

1. **De enlaces a evidencia.** Los agentes necesitan material estructurado, verificable y compacto — Argo devuelve JSON con desglose de credibilidad.
2. **El contexto es el primer coste.** Argo perfil agente: ~3,7KB por llamada, con presupuestos de bytes fijados por gates.
3. **Los sitios preparan contenido para IA.** llms.txt y `.md` se extienden — la cadena de fetch los sondea en el nivel 0, con lector r.jina.ai como respaldo.
4. **El ecosistema libre basta.** APIs abiertas de gobiernos/academia/estándares/seguridad + motores sin clave cubren la mayoría de dominios (221 sin clave).
5. **Calidad medible.** Pisos golden de ranking, gates de ablación de fusión y controles negativos de enrutamiento.

> v2.9.3 lo implementa todo: 264 fuentes, 94 dominios, 229 sin clave.

---

## Qué es

**Argo es infraestructura de búsqueda multilingüe para agentes de IA.**

La recuperación real nunca es «un idioma + un cuadro de búsqueda»: alguien pregunta por cotizaciones de acciones A, alguien más por el Mundial, alguien busca anime en japonés, alguien quiere el director de una película en IMDb. La premisa de Argo es simple: **enrutar por dominio, idioma e intención** hacia las fuentes adecuadas, en lugar de siempre raspado genérico de títulos web. La búsqueda en la red y la de archivos locales funcionan juntas.

> Fase actual (desde v2.9.7): el proyecto pasó de la optimización de rendimiento puntual a la optimización de arquitectura — cierre de contratos, contratos de estado unificados, puertas y cadenas de evidencia — y sobre esa base mantiene actualizaciones incrementales: cada versión es recomputable y reversible.

> El resultado no es una «lista de enlaces», sino **candidatos de evidencia + desglose de credibilidad**. Un buen enrutamiento es lo que hace que la evidencia se sostenga.

### frente a «envolver otra API de búsqueda»

| Enfoque habitual | Argo |
|-----------------|------|
| Atado a un motor y una clave | Multi-motor con enrutamiento automático; gratis primero, con presupuesto |
| Toda consulta es búsqueda web genérica | **Fuentes verticales primero**: mercados, cine, deportes, macro, química… resultados en forma de respuesta |
| Optimizado solo para chino/inglés | **Detección de idioma + parámetros de locale + fallback interlingüístico** |
| Resumir snippets y listo | Selección × densidad de evidencia × frescura × consenso multi-fuente |
| Un motor caído tumba la cadena | Cortacircuitos, caché negativa, recuperación por etapas (sin contaminación vertical) |
| Red en cada consulta | Caché de dos capas (memoria + SQLite); consultas calientes ~10 ms |
| Misma ruta lenta para diario e investigación | **Menos motores en el día a día; más abiertos en investigación profunda** |
| JSON largo agota el contexto del agente | Respuestas MCP compactas; snippets controlables |

---

## Enrutamiento según la consulta

<p align="center">
  <img src="assets/readme/proof-routes.svg" width="100%" alt="Cuatro rutas reales: finanzas, cine, multilingüe, geo">
</p>

| Preguntas así | Lo que suele ocurrir |
|---------|----------------------|
| python asyncio error handling | Dominio de QA de programación → API oficial de StackOverflow/StackExchange, con puntuación y respuesta aceptada |
| AAPL / US pre-market | Dominio de acciones EE. UU., separado de A-shares |
| 肖申克的救赎 主演 / Inception director | Dominio cine → IMDb etc. |
| 梅西 俱乐部 / 库里 球队 | Dominio deportes → TheSportsDB etc. |
| 埃菲尔铁塔在哪 / where is Eiffel Tower | Entidad geo → OpenStreetMap etc. |
| NASA founding year / 国务院职能 | Entidad org → Wikidata etc. |
| 周杰伦 专辑 / Taylor Swift album | Dominio media → iTunes etc. |
| アニメ おすすめ / 한국 영화 추천 | Detecta JA/KO → fuentes amigables al idioma; evita sitios solo en chino |
| US CPI, inflación de Japón | Dominio macro; separa por país (fuentes nacionales primero) |
| log4j CVSS / nodejs 22 end of life | Seguridad → NVD oficial; ciclo de vida → endoflife.date |
| attention is all you need | Académico → metadatos de arXiv/OpenAlex/CrossRef con DOI |
| 阿司匹林 分子式 | Química → respuestas tipo PubChem |
| TSMC valuation debate (deep research) | Subpreguntas + fuentes en paralelo; verticales reforzados |

---

## Cómo funciona

<p align="center">
  <img src="assets/readme/workflow.svg" width="100%" alt="Consulta → idioma y dominio → recall multi-motor → RRF → evidencia → JSON unificado">
</p>

```
query
  ├─ intent clarify (optional)
  ├─ query rewrite (optional; routing still sees original intent)
  ├─ language detect + language preference
  ├─ route (domain rules + TF-IDF + budget + lang supplements + hot-path cache)
  ├─ multi-engine recall (circuit breaker / negative cache / parallel)
  ├─ staged empty-result recovery (widen → same family/general → cross-lang; anti-pollution)
  ├─ RRF fusion + optional re-rank
  ├─ evidence skim (authority · density · freshness · consensus)
  └─ unified JSON (incl. engine_outcomes / recovery)
```

### Puntuación de evidencia (resumen)

```
selection  ≈ domain authority; SERP / redirect shells ranked very low
absorption ≈ density of numbers / definitions / comparisons / disclosures
freshness  ≈ publish time (ignores historical comparison years like “since 2015”)
composite  ≈ 0.40·selection + 0.35·absorption + 0.15·freshness + 0.10·engine score
```

Los resultados incluyen `selection`, `absorption`, `credibility_fast`, `evidence_flags`, etc. para que el agente ordene directamente.

### Disciplina del agente (recomendada)

1. **Preguntas de alto riesgo** (posiciones, seguridad, «¿es cierto?»): buscar → leer puntuaciones rápidas → `fetch` de los top → luego concluir  
2. **Números**: declarar el计算方式 (definición/alcance); si las fuentes chocan, listarlas—no forzar fusión  
3. **Páginas SERP / redirección**: nunca como fuente primaria  
4. **Posts sociales**: sentimiento y narrativa, no verdad de fondo  
5. **Fact-check**: preferir pocas consultas estratificadas (fuente / comparación / sujeto)

---

## Inicio rápido

Elige cualquier camino. **GitHub es la única fuente de verdad de instalación** (`npx github:taxueseek/argo` o `install.sh`); recomendación actual **v2.9.7**. **No uses `npm install argo-search`** — la copia del registro npm es un **v1.0.1 no oficial y obsoleto** (no es este repo, incompleto, no se actualiza). Este paquete pone `private: true` para no publicarse en npm por error.

**Funciona sin configuración**: sin claves API corren motores gratis + `local_*` locales; los que requieren clave se omiten si faltan (y suelen mejorar cuando están).

### Opción 1: Script de instalación (mejor para uso local a largo plazo)

```bash
curl -fsSL https://raw.githubusercontent.com/taxueseek/argo/main/scripts/install.sh | bash
```

Home personalizado + enlace de Skill:

```bash
curl -fsSL https://raw.githubusercontent.com/taxueseek/argo/main/scripts/install.sh \
  | bash -s -- --home "$HOME/.local/share/argo" --link "$HOME/.claude/skills/argo"
```

Verificar:

```bash
python3 ~/.local/share/argo/scripts/search.py "python asyncio error handling" --json
python3 ~/.local/share/argo/scripts/search.py --list-engines
```

### Opción 2: MCP desde GitHub (enganche rápido del agente)

Necesita **Node.js 18+** y **Python 3.9+**. Una vez:

```bash
pip3 install pyyaml
```

```bash
npx -y github:taxueseek/argo
```

Config del cliente (Claude Code / Cursor / Kimi, etc.):

```json
{
  "mcpServers": {
    "argo": {
      "command": "npx",
      "args": ["-y", "github:taxueseek/argo"]
    }
  }
}
```

Más estable, sin Node: instala con la opción 1 y apunta a Python local:

```json
{
  "mcpServers": {
    "argo": {
      "command": "python3",
      "args": ["/path/to/argo/scripts/mcp_server.py"]
    }
  }
}
```

Ruta de Python inusual: `export ARGO_PYTHON=/path/to/python3` (solo lo lee la entrada npx).

### Plugin de una línea para DeepSeek Harness

Dos caminos dentro de DeepSeek Harness:

```bash
# A: 19 herramientas mcp__argo__* (bundle del paquete principal, igual que el MCP completo)
dsh plugin --profile web add "github:taxueseek/argo"

# B: herramientas de búsqueda + orquestación wide_research (subpaquete)
dsh plugin --profile web add "github:taxueseek/argo#main&path:packages/dsh-plugin"
```

Reinicia `dsh web` tras instalar. Ver `packages/dsh-plugin/`.

### Opción 3: Tarball de release

Abre [Releases](https://github.com/taxueseek/argo/releases) y descarga el tarball más reciente, **`argo-x.y.z.tar.gz`** (sustituye `x.y.z` por el número de la última versión):

```bash
tar -xzf argo-x.y.z.tar.gz
cd argo-x.y.z
pip3 install pyyaml
python3 scripts/search.py "Python asyncio" --json
python3 scripts/mcp_server.py
```

### Opción 4: git clone (dev / parchear fuente)

```bash
git clone https://github.com/taxueseek/argo.git
cd argo
pip3 install pyyaml
bash scripts/install.sh --link ~/.claude/skills/argo   # optional
python3 scripts/search.py --list-engines
```

### Opción 5: Directorio Skill (symlink, una sola fuente de verdad)

```bash
python3 scripts/link_source.py --to ~/.claude/skills/argo
python3 scripts/link_source.py --to ~/.agents/skills/argo

cp installs.local.yaml.example installs.local.yaml
python3 scripts/link_source.py
python3 scripts/link_source.py --check
```

### Opción 6: Biblioteca Python

```python
import sys
sys.path.insert(0, "/path/to/argo/scripts")
from search import super_search

result = super_search("Python asyncio", n=5, mode="fast")
for item in result["results"]:
    print(item["title"], item.get("credibility_fast"), item["url"])
```

```bash
# if bin/argo is on PATH
argo search "Python asyncio"
argo research "2026 mutual fund holdings structure"
argo evidence "a claim to verify"
```

---

## Plataformas

| Plataforma | Integración | Notas |
|----------|-------------|-------|
| **Claude Code** | MCP / enlace Skill | `npx` o `mcp_server.py`; `link_source.py` ok |
| **Kimi / Grok Build** | MCP Server | igual |
| **Cursor / Cline / Continue** | MCP | cualquier plugin IDE con MCP |
| **CLI** | `search.py` / `bin/argo` | scripts, cron, debug manual |
| **Proyectos Python** | `from search import super_search` | llamada de librería |

### Comprobación post-instalación

```bash
python3 --version          # 3.9+
python3 -c "import yaml; print('PyYAML OK')"
python3 -m pytest tests/test_unit.py -q   # optional
python3 scripts/search.py --list-engines
```

---

## Capacidades

| Capacidad | Qué hace | Entrada |
|------------|--------------|-------|
| Búsqueda unificada | route → recall → fuse → skim score | `search.py` / `argo_search` |
| Búsqueda de archivos locales | código/notas/memoria en disco (offline) | `argo_local_search` |
| Vista previa de texto local | preview en dirs en whitelist (fail-closed) | `argo_local_read` |
| Recompute | recálculo numérico en sandbox (niega por defecto) | `argo_recompute` |
| Investigación profunda | subpreguntas, multi-fuente, pistas de huecos | `research.py` / `argo_research` |
| Credibilidad | autoridad / densidad / frescura / cruce | `evidence.py` / `argo_evidence` |
| Aclarar intención | polisemia, colisiones de marca, pistas de estrategia | `clarify.py` / `argo_clarify` |
| Fetch de página | HTTP primero, navegador si hace falta | `argo_fetch` (`mode=extract` para estructura) |
| Captura / PDF | capturas de página, extracto PDF estructurado | `argo_screenshot` / `argo_pdf` |
| Crawl de sitio | crawl por lotes de páginas de listado | `argo_crawl` |
| Operadores de consulta | `site:` / `-site:` / `-término` / `-"frase"` / `"frase"` / `lang:` / `after:` / `before:` extraídos de ruta y recuperación (detalles en references/usage.md) | se escriben directo en la consulta |
| Señales de confianza | `authority_level` grado discreto (0-4, >=3 muy autoritativo) + `summary` resumen para Agent (se rellena tras verificar) | campos del resultado, visibles con `--fields agent` |
| Social / sentimiento | Weibo / Xiaohongshu / Bilibili / Reddit / X … | `argo_social_search` |

### Modos de presupuesto

| Modo | Mejor para | Comportamiento |
|------|----------|----------|
| `fast` | Q simple, necesita velocidad | motores gratis primero; omite re-rank de pago |
| `auto` | default diario | equilibrio calidad/gasto con conciencia de coste |
| `deep` | investigación, sondeos | calidad primero; más motores |
| `budget` | cuota justa | control de cuota; degrada al agotarse |

### Conjunto aproximado de capacidades (v2.9.3)

- **Motor DeepSeek Search + capa de contrato de operadores de consulta + agrupación de conexiones de transporte + puerta de instantáneas de enrutado (nuevo en v2.9.6)**: motor oficial `deepseek_search` activo por defecto (se omite solo sin `DEEPSEEK_API_KEY`, las otras 265 fuentes no se afectan; latencia 445-510ms, el único de tres motores con cobertura completa de nivel authority / rerank_score / hora de publicación, a la par de anysearch en ja/ko/es, el único donde `--since/--until` realmente surte efecto; pago por uso, fuera de los combos de dominio, `--engine deepseek_search` explícito es la vía principal; los hosts DSH comparten la misma key por el seam nativo de credenciales); `site:` / `-site:` / `-término` / `lang:` / `after:` / `before:` convergen en una capa de contrato de operadores (`query_operators.py`; enrutado y caché solo ven el clean_query sin instrucciones; `site:` pasa de solo-parseo a posfiltrado real y entra en la clave de caché); POST reutiliza conexiones agrupadas (ahorra 320ms anysearch / 561ms octen por petición) + preconexión MCP; octen entra en el fallback general y el slot de cobertura (p90 3273→1614ms, máx 6266→1928ms, errores 9→0, `ARGO_GENERAL_FALLBACK_LEGACY=1` para volver atrás); corrige la decadencia de rango del aislamiento RRF por calibre (resultados del mismo motor con la misma puntuación) y el caparazón de redirección ck/a de Bing (40.2% de resultados vacíos antes); nueva puerta pre-commit (~12s, seis comprobaciones) y puerta de instantáneas de decisión de enrutado (trata los 13 fix(route) en 90 días); el plugin DSH se adapta al doble stack 0.2.1-rc.2 (entrada `startActivation` + tool guard absorbiendo el `toolFilter` eliminado), rama de compatibilidad 0.2.1-alpha.1 cubierta por unit tests
- **Dominio dedicado de tipo de cambio + deduplicación de dos capas + corrección de falsa penalización (nuevo en v2.9.5)**: `fx_query` responde consultas de tipo/paridad con tipo en vivo + noticia diaria en 675ms (antes entradas de enciclopedia a 1411ms); dedup gana normalización de sufijo (cero dependencias) + revisión difusa rapidfuzz (opcional, `ARGO_DEDUP_FUZZY`, con vuelta atrás); corrige el ×0.6 por separadores en rerank degradado (docs oficiales de vuelta arriba); negación gana "no-X"; nombres de daemon acotados por checkout
- **Atribución explícita de dominio de motor + cortador de cadena de recuperación + sincronización de puertas (nuevo en v2.9.4)**: `--engine X` complementa `match_domains` corrigiendo TTL de caché general; motor único sin alternativa omite ejecución vacía L1; reglas `config.yaml` mejoradas; exportación de variables de entorno `mcp_launch.sh` reducida; capa de registro de motores local cerrada y calidad mejorada; sincronización de puertas (module_size_gate / ENGINE_CATALOG)
- **Empaquetado completo de posts de X, `argo tweet` (nuevo en v2.9.3)**: un comando empaqueta el texto completo, hilo/citas/retweets e interacciones de un post dado; por defecto solo texto, `--out` escribe el paquete de 4 archivos (post.md/raw.json/manifest.json/CHECKLIST.md), `--media` descarga imágenes/vídeos bajo demanda; los motivos de fallo quedan visibles en los artefactos
- **Carril de estado de sesión del navegador, `argo auth` (nuevo en v2.9.3)**: `argo auth login/status/logout` mantiene un perfil de navegador persistente por sitio — escanea el QR una vez y las páginas que exigen sesión se vuelven accesibles; las cookies solo viven en el almacenamiento cifrado del propio Chrome, los resultados con sesión se marcan `login_state_used` y quedan excluidos de la caché compartida (activar con `ARGO_AUTH_FETCH`)
- **Calidad + velocidad de la cadena local china (nuevo en v2.9.3)**: las shells de redirección de Sogou/Baidu se resuelven en URLs reales sin sesión, elevando los resultados conservados de 1 a 5; gracia de consenso adaptativa (el primer motor que entrega suficiente libera la espera), despacho en inglés ~3.0s→2.2-2.5s
- **Consultas ferroviarias con transbordo/escala (nuevo en v2.9.3)**: las búsquedas en 12306 cubren transbordos e itinerarios con escala, con el embudo de candidatos corregido de compresión 10→1 a un fiel 10→10; la búsqueda académica gana el modo multi-fuente `--academic-deep` con una sola bandera
- **Expansión de enrutamiento y corrección de la puerta de intención (nuevo en v2.9.3)**: 43 motores sin referencia de dominio conectados a sus dominios, 3 nuevas fuentes financieras sin clave; las consultas tipo "tutorial" ya no quedan bloqueadas en un solo motor por la puerta de intención
- **Aceleraciones locales (nuevo en v2.9.3)**: coincidencia de huellas de imagen local 158ms→3.9ms sobre 77k imágenes (apagada por defecto, `ARGO_LOCAL_IMAGE=1` para activar); adelgazamiento automático del consumo por agentes, overhead fijo por llamada MCP −32%
- **Fusión de datos locales (nuevo en v2.8.4)**: work packages de investigación con `file_inputs` (datos locales de primera mano; se registra sha256/linaje) + `recompute` (recálculo en sandbox); el dossier emite `local_sources`
- **Inyección MCP de un comando (nuevo en v2.8.4)**: `argo mcp inject` para Claude Code / Cursor / Windsurf / Codex / OpenCode / Cline (escritura atómica + backup + deshacer; fuente `mcp/clients.yaml`)
- **Mejoras de búsqueda estructurada (nuevo en v2.8.4)**: normalización + variantes + puerta de complejidad; sintaxis social primero; TF-IDF sigue mirando tras descartar un motor chino; `--include-local`
- **Keenable (nuevo en v2.8.4)**: motor web general extra (HTTP declarativo L1, prueba gratis, `ARGO_KEENABLE_API_KEY`)
- **266 fuentes, 95 dominios** (229 sin clave): web general + finanzas / macro / cine / deportes / geo / orgs / media / química / academia / código (fuente de verdad: `config.yaml`)
- **19 herramientas MCP** (alineadas con la superficie CLI): search, research, evidence, clarify, fetch, screenshot, PDF, social, archivos locales, crawl, preview local, recompute, texto completo de artículos WeChat, agregación de empleo, extracción estructurada, preflight de URLs por lotes, respuesta directa, observación de cambios web, entradas de cita DOI
- **Búsqueda multilingüe**: chino, inglés, japonés, coreano, cirílico, tailandés, árabe, hebreo, griego, devanagari, …; el enrutamiento y los params de motor siguen el idioma; consultas no chinas evitan fuentes solo en chino (Zhihu / Sogou WeChat / snapshots A-share, etc.)
- **Compuertas de recuperación vertical**: la recuperación de vacío no «filtra» pypi / npm / flash news a cine o deportes
- **Más rápido en el día a día, más completo en investigación**: tiers `engine_policy`—combo diario apretado, long-tail abierto para deep / research

---

## Motores y enrutamiento

La config tiene ahora unos **259** fuentes y **93** dominios (ver `config.yaml` y `--list-engines`).

### Directos y verticales (extracto)

| Motor | Escenario | Sesgo de coste |
|--------|----------|-----------|
| anysearch / duckduckgo | general / tech | free |
| sina_quote / tencent_quote / eastmoney | cotizaciones A-share / flujos | free |
| finviz / seeking_alpha | finanzas EE. UU. y exterior | depends |
| imdb / itunes / thesportsdb | cine / música / deportes | mostly free |
| local_openstreetmap / wikidata / wikipedia | geo / org / enciclopedia | free |
| arxiv / semantic_scholar / openalex | académico | mostly free |
| pubchem / gbif / rfc_editor | química / especies / estándares | free |
| github / stackoverflow / pypi / npm | código y paquetes | depends |
| byted / bocha / metaso / octen | web china / búsqueda IA | API / low cost |
| zhihu / wechat_sogou | opinión china / WeChat | API / free |
| tavily / felo / exa | internacional / semántica | paid or quota |
| twitter / reddit / xiaohongshu / bilibili / weibo | social UGC | free (some need login) |

### Capa local de coste cero (`local_*`)

No hace falta un servicio SearXNG aparte. La ruta principal usa parseo in-process de HTML / RSS / JSON (`local_bing`, `local_sogou`, `local_google`, `local_arxiv`, …). En **consultas multilingües**, el enrutamiento reescribe params de idioma del motor (p. ej. Bing `setlang`) y fusiona con RRF.

---

## Ejemplos

### Finanzas

```bash
python3 scripts/search.py "python asyncio error handling" --explain
# typical: stock_query → quote snapshot sources
```

### Académico

```bash
python3 scripts/search.py "transformer attention mechanism paper" --json
# domain often academic; combo includes arxiv etc.
```

### Investigar y verificar

```bash
python3 scripts/research.py "2026 mutual fund Q2 holdings structure" --depth deep --json

python3 scripts/search.py "same query" --json | \
  python3 scripts/evidence.py "same query" --stdin --json
```

### Herramientas MCP (12)

| Herramienta | Propósito |
|------|---------|
| `argo_search` | búsqueda unificada |
| `argo_local_search` | archivos locales (offline) |
| `argo_local_read` | preview de texto local en whitelist (fail-closed) |
| `argo_recompute` | recálculo en sandbox (niega por defecto; hace falta auth) |
| `argo_research` | investigación profunda (incl. modo sentimiento social) |
| `argo_evidence` | puntuación de credibilidad |
| `argo_clarify` | desambiguación de intención |
| `argo_fetch` | fetch inteligente (`mode=extract` extracto estructurado) |
| `argo_crawl` | crawl de sitio |
| `argo_screenshot` | captura de página |
| `argo_pdf` | extracto PDF |
| `argo_social_search` | social multi-plataforma (`mode=sentiment`) |

---

## Instalación y configuración

### Requisitos

| Ítem | Requisito |
|------|-------------|
| Python | 3.9+ (CLI + núcleo MCP) |
| Deps | `pip install pyyaml` (única dependencia dura) |
| Node.js | **solo** para entrada `npx`, 18+ |
| SearXNG | no requerido (motores locales integrados) |

### Claves API (todas opcionales)

Sin clave se omite ese motor; los gratis sostienen. **Usa variables de entorno**—nunca commits de claves reales ni pegarlas en issues.

```bash
# recommended (better quality)
export TAVILY_API_KEY="your_key"
export BOCHA_API_KEY="your_key"
export METASO_API_KEY="your_key"
export ZHIHU_ACCESS_SECRET="your_key"

# optional
export BRAVE_API_KEY="your_key"
export FELO_API_KEY="your_key"
export GITHUB_TOKEN="your_key"
export WEB_SEARCH_API_KEY="your_key"
export ANYSEARCH_API_KEY="your_key"
export OCTEN_API_KEY="your_key"
export ARGO_KEENABLE_API_KEY="your_key"   # opcional; prueba gratis de Keenable
```

`config.yaml` solo guarda placeholders `{ENV_NAME}`—sin secretos en claro en git.

### Caché

La ruta SQLite por defecto es `cache.db_path` en `config.yaml` (suele ser `~/.cache/unified-search/cache.db`).

| Tipo | TTL aprox. |
|------|-------------|
| Finance | ~5 min |
| News / realtime | ~10–15 min |
| General | ~1 hour |
| Research / evergreen | ~2–24 hours |
| Empty results | very short (avoid freezing “no hits”) |

### FAQ

**¿Funciona sin claves API?**  
Sí. Muchos motores locales gratis y APIs gratis; la ruta sin clave es automática.

**¿Script de instalación vs npx?**  
Script: instalación local fija, config, enlace Skill. npx: enganchar MCP rápido. Mismo núcleo Python.

**¿Cómo ver los motores?**  
`python3 scripts/search.py --list-engines`, o añade `--explain`.

**¿Varias copias de código en el repo?**  
No. Prefiere una fuente + symlinks con `link_source.py`, no clones rsync.

---

## Flags CLI

```
python3 scripts/search.py [options] query

  --engine, -e       engine, default auto
  --max-results, -n  count, default 5
  --depth, -d        fast | balanced | deep
  --mode             fast | auto | deep | budget
  --no-cache         skip cache
  --explain          print routing explanation
  --json             JSON output
  --timeout, -t      timeout seconds
  --list-engines     list engines
```

---

## Compromisos de diseño

1. **Absorción del agente primero, cantidad de enlaces segundo.**  
2. **Gratis y local primero; de pago es elevación opcional.**  
3. **Los fallos son observables**: empty / timeout / breaker van etiquetados—sin tragar en silencio.  
4. **Motores guiados por config**; `config.yaml` es la única fuente de verdad.  
5. **Instalación de fuente única**: enlaza entradas, no rsync de copias.  
6. **Lo social no es una biblioteca de verdad**; sirve para expansión y sentimiento, no como única base factual.

---

## Buenos encajes

- Backend de búsqueda para agentes Claude Code / Grok Build / Codex / Kimi  
- Q&A **multilingüe y multi-dominio**: CJK + EN + finanzas / cine / deportes / academia / código  
- Scripts y pipelines que necesitan recuperación **reproducible y cacheable**  
- Fact-check y comparación multi-fuente de datos públicos de finanzas / entidades  

No es gran solución única para: ranking nativo de engagement de plataforma, o agregadores max-recall de larga vida (los motores locales embebidos reemplazan SearXNG externo como vía principal).

---

## Árbol (resumen)

```
argo/
├── README.md                # Chinese (default)
├── README.en.md             # English
├── README.ja.md             # Japanese
├── README.ko.md             # Korean
├── README.es.md             # Spanish
├── SKILL.md
├── package.json             # npx entry
├── bin/argo.js              # Node MCP launcher
├── bin/argo                 # Python CLI
├── config.yaml              # engines & domains (source of truth)
├── assets/readme/           # README visuals
├── backends/
├── mcp/                     # fuente de inyección MCP multi-cliente (clients.yaml)
├── scripts/                 # search / research / mcp / install …
├── sub-skills/local-search/
├── sub-skills/ego-search/      # búsqueda profesional con sesión (off por defecto)
├── tests/
└── docs/
```

---

## Actualizaciones recientes

### v2.9.7: Consolidación de arquitectura — seam web_fetch DSH + contrato explicit_only + contratos de estado unificados (License: Apache-2.0)

- **Cambio de licencia**: MIT → Apache License 2.0 (concesión de patentes explícita, más seguro para uso comercial); nada más cambia
- **Seam web_fetch del plugin DSH**: el web_fetch del huésped antes esquivaba argo por completo como ruta predeterminada de «lee esta URL»; ahora registra un proveedor de fetch en la cadena argo_fetch (HTTP primero, ascenso automático a navegador anti-detección ante Cloudflare / páginas renderizadas con JS); ejecución de doble vía isomorfa con el proveedor de búsqueda — piscina MCP residente primero, CLI de un solo disparo solo ante fallo de transporte, errores de herramienta y timeouts no se reenvían (esas ya significan que la llamada terminó; reenviar duplica llamadas de motor y cuota); fallos clasificados en cinco clases (timeout / bloqueado / vacío / genérico / cancelado) con mensajes accionables; nueva configuración `fetchProviderEnabled` / `fetchProviderId` / `fetchTimeoutMs` (25000) / `fetchMaxChars` (50000), toda activa por defecto con salidas de emergencia; medido: redirecciones de origen cruzado (enlaces cortos, ascensos de protocolo, caparazones de redirección) y páginas de desafío JS pasan de fallos estructurales del huésped a éxitos de argo, las páginas estáticas no cambian
- **Cierre del contrato explicit_only**: `config._routable_filter` filtraba listas negras/blancas de entorno, cles y bloqueos, pero no explicit_only, así que 18 motores de solo-uso-explícito (incluido el único `deepseek_search` de pago) yacían en el pool de candidados habilitados donde seis rutas de enrutado (inyección TF-IDF, catch-all, backfill, reserva, etc.) podían elegirlos — nunca disparó solo porque el corpus no tenía ninguna entrada; una entrada habría disparado motores de pago en modo auto; ahora se filtra en el único productor, fijado por `tests/test_explicit_only_gate.py`
- **Contratos de estado unificados**: cortocircuito en memoria del cortacircuitos cuando está sano y cerrado con conteo cero (sin bloqueo de fichero, sin reescritura de disco) con conciencia cross-process vía `(st_mtime_ns, st_size)`; la contabilidad adaptativa pliega `MAX(created_at)` en un solo SQL agregado más un gestor de contexto `batch()` para confirmaciones multi-motor en una transacción; el agotamiento de cuota registra la huella de credencial vigente y se desbloquea solo al rotar la clave; la caché de ruta se invalida cuando un motor del combo se agota o se recupera; `is_engine_routable` se convierte en el predicado de admisión único tras backfill / tfidf / breaker_filter
- **Despacho y transporte**: auto / deep también descartan motores agotados por duro (reserva fail-open); ventana de espera de cobertura estrechada, el early-stop de Wave-1 ahora acepta suficiencia acumulada cross-engine; agrupación de conexiones POST (ahorra ~320ms anysearch / ~561ms octen por petición) + preconexión MCP; el dominio de clima gana `early_stop_min_results: 1`
- **Resta de rutas calientes en sub-skills**: js-run reemplaza SIGALRM por el timeout nativo de MiniRacer, arreglando el crash `ValueError: signal only works in main thread` al invocarse desde hilos de trabajo de crawl / research / mcp; el rerank de local-seek elimina las lecturas de disco O(N) por consulta; local-search reutiliza el registro (sin doble parseo YAML); ego-search corta en corto la detección bajo auto
- **Validación**: 71 pruebas unitarias del plugin; suite completa 4264 passed / 28 skipped; siete puertas pre-commit 123 passed; la comparativa de la cadena de fetch no regresa páginas estáticas y convierte fallos en éxitos en redirecciones / desafíos JS

### v2.9.6: Motor DeepSeek Search + contrato de operadores de consulta + agrupación de conexiones + puerta de instantáneas de enrutado

- Nuevo motor `deepseek_search` (`api.deepseek.com/v1/tools/search` oficial) activo por defecto: se omite solo sin `DEEPSEEK_API_KEY`, las otras 265 fuentes no se afectan; medido 445-510ms (anysearch 1.7-4.5s / exa 3.7s), el único de los tres con cobertura completa de nivel authority / rerank_score / hora de publicación, a la par de anysearch en ja/ko/es; pago por uso, fuera de los combos de dominio, `--engine deepseek_search` explícito es la vía principal; los hosts DSH comparten la misma key con el backend oficial por el seam nativo de credenciales (rotar la key en la página Models surte efecto en el siguiente salto, nunca se persiste ni se registra)
- Corrección: `--since/--until` silenciosamente ineficaz para deepseek_search (añadido a TIME_CAPABLE_ENGINES)
- Nueva `query_operators.py`, capa de contrato de operadores de consulta: `site:` / `-site:` / `-término` / `-"frase"` / `lang:` / `after:` / `before:` convergen de cinco formas dispersas en operadores estructurados; enrutado, caché y comprensión de consulta solo ven el clean_query sin instrucciones; `site:` / `-site:` posfiltran de verdad (coincidencia de subdominio, OR multi-sitio, conteo en `site_filtered`), los operadores entran en la clave de caché de resultados para evitar contaminación cruzada
- `evidence.py`: nuevo campo de resumen de doble capa para Agent `summary` (semántica de resumen de DeepSeek Search)
- Transporte sin pagar dos veces: POST reutiliza conexiones agrupadas (medido: la segunda petición en la misma conexión ahorra 320ms anysearch / 561ms octen), con reintento por fallo de préstamo y lectura del cuerpo antes de devolver; preconexión MCP; cierre de agotamiento de cuota y caché negativa muerta
- Enrutado: octen entra en el segundo slot de la cadena de fallback general y el slot de cobertura TF-IDF (ventana de jitter de anysearch p90 3273→1614ms, máx 6266→1928ms, errores 9→0; sin diferencia de mediana en ventana sana, posicionado como seguro de cola), escapatoria `ARGO_GENERAL_FALLBACK_LEGACY=1`
- Corrección de la decadencia de rango del aislamiento RRF por calibre: todos los resultados de un motor con la misma puntuación (medido: 5 resultados de anysearch todos 0.017213), la salida degeneraba en concatenación por peso de motor; nuevo test bloquea "puntuaciones estrictamente decrecientes dentro del mismo motor"
- Corrección del caparazón de redirección ck/a de Bing no restaurado, que hacía que la capa de agregación filtrara lotes enteros (40.2% de resultados vacíos en los últimos 7 días): decodificación base64url offline recupera los enlaces reales, cero red
- Corrección del combo líder TF-IDF que producía `['anysearch','anysearch']` ejecutándose dos veces en paralelo (doble cuota con wasted_ms registrado en 0): 200 consultas reales reproducidas, combos duplicados 1→0
- Mejoras de búsqueda: caché negativa de fallos, conmutación por error de Nitter, aislamiento por calibre, extracción de X Article, guardián de eco de consulta (rechazo por parada temprana + cambio de motor en la cadena de recuperación)
- Ingeniería: nueva puerta `scripts/pre-commit` (static_lint / module_size_gate / usage_doc / consistency / routing_snapshot / context_budget + engine_catalog, ~12s medido); la puerta de instantáneas de decisión de enrutado convierte los volteos de enrutado en golden diffable (unión de tres conjuntos de anotación, 115 consultas, solo se comparan domain y kind para que el ruido de entorno no dé falsos rojos); test de sincronía del registro de calibres bloquea "los nombres de motor de la tabla deben estar realmente registrados"
- El plugin DSH se adapta a DSH 0.2.1-rc.2: entrada de runtime de doble stack (`startActivation({provider, label, request, signal, delivery})` nuevo / `start(provider, request)` heredado), el tool guard dentro del plugin evita llamadas anidadas de workers a `wide_research` tras eliminar rc.2 `toolFilter`; verificado extremo a extremo en rc.2 (`wide_research` planner → 2 workers → synthesis, passed=true / 14 sources) y `argo_search` nativo (count=3); rama de compatibilidad 0.2.1-alpha.1 cubierta por unit tests; unit tests del plugin 46→50
- Versiones de entorno DSH: **DSH 0.2.1-rc.2 (actual, en ejecución, verificado extremo a extremo) + DSH 0.2.1-alpha.1 (compatible, rama start heredada cubierta por unit tests)**; tabla de compatibilidad en `packages/dsh-plugin/README.md`

### v2.9.5: Dominio dedicado de tipo de cambio + deduplicación de dos capas + corrección de falsa penalización + aislamiento de daemon por checkout

- `config.yaml`: nuevo dominio `fx_query` — las consultas de "tipo de cambio RMB/USD, paridad central, offshore" ya no caen en callejones macro vacíos ni en entradas de enciclopedia; ahora tipo en vivo + noticia de paridad diaria (675ms medidos; antes 1411ms y desencaminado)
- `search_rank.py`: deduplicación de dos capas — normalización de sufijo de sitio en título ( cero dependencias) + revisión difusa rapidfuzz (solo dentro de la banda de casi-acierto; `ARGO_DEDUP_FUZZY=0` desactiva, sin instalar vuelve a minhash puro)
- Corrección: falsa penalización por separadores de título en rerank degradado — títulos con `|` / `_` / `——` recibían ×0.6 uniforme, hundiendo documentación oficial 40%; afectaba cada consulta auto/deep sin clave Bocha (criterio convergido a la implementación única de rank_signals)
- `query_understanding.py`: la negación gana "no-X" (la interrogativa "si es o no" no se lee como negación)
- `daemon.py`: nombres en disco (socket/pid/puntero/log) acotados por checkout — trabajo multi-worktree/clone peleándose el daemon, matar procesos ajenos y "los cambios no surten efecto", todos erradicados
- Nueva dependencia opcional rapidfuzz (`pip install rapidfuzz`; la instala install.sh, el núcleo no se afecta si falta)

### v2.9.4: Atribución explícita de dominio de motor + cortador de cadena de recuperación + sincronización de puertas

- `route.py`: `--engine X` complementa `match_domains`, corrigiendo TTL de caché general
- `recovery.py`: motor único sin alternativa omite ejecución vacía L1
- `config.yaml`: `org_entity` añade términos de diligencia; `fund_query` añade términos de regulación
- `mcp_launch.sh`: `set -a` reducido a `. "$ENV_FILE"` línea única
- `sub-skills/local-search/`: capa de registro cerrada y calidad mejorada
- Sincronización de puertas: module_size_gate / ENGINE_CATALOG alineados

### v2.9.3: empaquetado completo de posts de X + carril de estado de sesión del navegador + calidad/velocidad de la cadena local

- **Nuevo**: `argo tweet` — un comando empaqueta el texto completo, hilo/citas/retweets e interacciones de un post de X; por defecto solo texto, `--out` escribe el paquete de 4 archivos (post.md/raw.json/manifest.json/CHECKLIST.md), `--media` descarga imágenes/vídeos bajo demanda; los motivos de fallo quedan visibles en los artefactos
- **Nuevo**: carril de estado de sesión del navegador `argo auth` — `login/status/logout` gestiona un perfil de navegador persistente por sitio; escanea el QR una vez y las páginas que exigen sesión se vuelven accesibles; las cookies solo viven en el almacenamiento cifrado del propio Chrome (argo no las lee ni las exporta), los resultados con sesión se marcan `login_state_used` y quedan excluidos de la caché compartida (activar con `ARGO_AUTH_FETCH`)
- **Más preciso**: la cadena local china resuelve las shells de redirección de Sogou/Baidu en URLs reales sin sesión (resultados conservados 1→5); corregido el bloqueo falso de la puerta de intención (las consultas tipo "tutorial" ya no quedan fijadas a un solo motor); URLs de identidad de fila ferroviaria corrigen la compresión del embudo de candidatos (10→1 → fiel 10→10)
- **Más rápido**: gracia de consenso adaptativa (el primer motor que entrega suficiente libera la espera; despacho en inglés ~3.0s→2.2-2.5s); parada temprana de cola larga local; huellas de imagen local vía producto matricial mmap (77k imágenes 158ms→3.9ms, apagado por defecto con `ARGO_LOCAL_IMAGE=1`); adelgazamiento automático del consumo por agentes + negociación de contenido markdown, overhead fijo por llamada MCP −32%
- **Más fuentes**: 43 motores sin referencia de dominio conectados a sus dominios; route_lang de enrutamiento por idioma; 3 nuevas fuentes financieras sin clave; `--academic-deep` multi-fuente académica con una bandera; consultas ferroviarias con transbordo/escala
- **Más robusto**: js-run integrado como primer carril de la cadena de fetch (reintentos con huella Chrome); fugas de sesión jsrun y presupuesto de backoff corregidos; timeouts ajustados (redskill 60→15s) con la política de declaración dividida en tres grupos

### v2.9.2: compatibilidad verificada con DSH 0.2.1-alpha.1 + correcciones de enrutamiento/guardas + sub-skill js-run

- **Más compatible**: el plugin de DSH está verificado en el último DSH 0.2.1-alpha.1 — herramientas nativas de primera clase / web_search seam / wide_research funcionan en las tres formas; `argo mcp inject` añade WorkBuddy, cubriendo el 7.º host
- **Más preciso**: degradación de evidencia débil TF-IDF a fuentes auxiliares, piso de fuentes muertas + relleno de slots del breaker, aislamiento de motores con cuota agotada, corrección de falsos positivos de serp_guard
- **Más rápido y robusto**: importaciones diferidas de engines/evidence (volumen de import −50%), cortocircuito del conjunto de existencia en admisión (open 261 → 99), guardas de entrada/argumentos numéricos de MCP; nueva sub-skill `sub-skills/js-run` (ejecuta JS web sin navegador, P50 ≈ 1ms)

### v2.9.1: optimización de calidad de contenido + resistencia a granjas de contenido + compatibilidad con el último entorno

- **Más limpio**: evaluación de calidad de contenido mejorada y mayor resistencia a granjas de contenido — el contenido de baja calidad o generado en masa se identifica y filtra con más eficacia
- **Más compatible**: adaptado a la última versión para colaborar sin fisuras con el entorno actual
- **Más estable**: la búsqueda local añade una guarda sobre su propio árbol de instalación, evitando que los resultados se contaminen con el código fuente del propio argo

### v2.9.0: optimización de fuentes + paridad plugin/CLI + lenguas minoritarias

- **Más amplio**: fuentes 237 → 253 (sin clave 198 → 219); se añaden 14 fuentes de noticias locales en lenguas minoritarias, la fuente de texto completo de acceso abierto CORE, TinEye de búsqueda inversa de imágenes, una salida estable de Bing RSS y más; se revivieron Baidu y Sogou, dos fuentes perennes
- **Más alineado**: 18 comandos CLI corresponden uno a uno con 19 herramientas MCP — por primera vez plugin y CLI quedan totalmente a la par en búsqueda
- **Más idiomas**: 14 fuentes en lenguas minoritarias (tailandés/árabe/hebreo/griego/hindi/vietnamita/turco/indonesio, etc.), asignadas automáticamente según el idioma de la consulta
- **Más rápido**: cadena de importación −79%, rerank con n=200 de 33ms → 1.5ms, aciertos de caché de ~60% a casi sin fallos
- **Más fiable**: corrección de seguridad entre procesos en la ruta de escritura de cuotas, los resultados de parada temprana ya no se etiquetan erróneamente como timeout, y `argo stats` da a la calidad de búsqueda su propio libro contable

### v2.8.9: salida más ligera + recuperación más rica y rápida + 5 fuentes internacionales y de verificación

- **Más ligero**: salida por defecto −66% (los mismos resultados ya no se escriben tres veces); consultas repetidas −30% (caché de decisiones de enrutado); esperas con red lenta −36% (una fuente de respaldo se dispara automáticamente si la principal supera 0.8s)
- **Más rico**: recall +35%, latencia de fetch −30%; fidelidad estructural del cuerpo 0/6 → 6/6 (títulos, listas y tablas ya no se aplanan); el contenido en chino ya no se puntúa sistemáticamente como de baja calidad
- **Nuevo**: fuentes 232 → 237 (sin clave 194 → 198, todas gratis — The Guardian, France 24, DW, más los verificadores FactCheck.org / Full Fact para afirmaciones de EE. UU. y Reino Unido); fuente muerta gdelt retirada
- **Más fiable**: corregidos seis defectos de contabilidad donde los números se contradecían entre sí; un embudo de seis etapas localiza dónde colapsa una búsqueda sin resultados; una herramienta de repetición sin conexión permite verificar los cambios el mismo día. Ver [notas de la versión](docs/RELEASE_NOTES_v2.8.9.md)

### v2.8.8: correcciones reportadas por usuarios reales + aceleración general + 232 fuentes

- **Correcciones**: motores que devolvían cero resultados en silencio al configurar claves con los nombres recomendados (#12); cadena de fetch que ignoraba el proxy y hacía fallar siempre sitios como GitHub (#13) — ahora funcionan `ARGO_PROXY`, las reglas por dominio del config y las variables de proxy estándar, respetando `NO_PROXY`
- **Más rápido**: arranque en frío del comando 2.1s → 0.55s; caché de configuración entre procesos 50–82ms → 16–18ms; cada búsqueda informa tiempos por etapa y consumo de presupuesto, sin adivinar dónde está la lentitud (`--no-timing` para desactivar)
- **Nuevo**: fuentes 218 → 232 (listas para usar sin configuración 184 → 194, todas sin clave: tendencias de China, avisos de seguridad, académico de acceso abierto, directorios de skills, búsqueda para agentes), `argo answer` (respuestas directas con citas), `argo watch` (observación de cambios web), superficies de herramientas CLI/MCP alineadas
- **Más robusto**: rutas convencionales en los tres sistemas (nueva introspección `argo paths`), soporte de Python 3.9, degradaciones silenciosas ahora registradas; ver [notas de la versión](docs/RELEASE_NOTES_v2.8.8.md)

### v2.8.7: fuentes ampliadas a 218 + una tanda de correcciones

- **Ampliación de fuentes**: 168 → 218 fuentes, 72 → 89 dominios (nuevas fuentes oficiales: StackExchange Q&A, metadatos DOI, inteligencia de vulnerabilidades, ciclos de vida), más tres canales directos de obtención de contenido
- **Una tanda de correcciones**: enrutamiento multi-motor, fallback de resultados vacíos, redirecciones con chino, degradación de búsqueda local, etc.; ver [notas de la versión](docs/RELEASE_NOTES_v2.8.7.md)

### v2.8.6: búsqueda más rápida + reparto multi-fuente

- Carrera de motores, reparto en tres vías de Zhihu, distribución idiomática/académica ampliada, puerta de fuentes muertas

### v2.8.5: herramientas nativas del plugin DSH + MCP apagado por defecto + compatibilidad con Windows

- **Herramientas nativas del plugin**: `argo_search` / `argo_fetch` se registran como herramientas nativas de primera clase, disponibles por defecto sin conexión MCP; los esquemas se generan desde la única fuente de verdad (`mcp_tools.py`), sin deriva; las 18 herramientas (salvo `argo_research`) se activan a demanda vía `nativeTools`
- **MCP apagado por defecto**: tres formas de conexión (MCP a demanda / herramientas nativas como entrada por defecto / web_search seam); coste de token residente cero, y un profile patch abre la superficie completa de 19 herramientas
- **Compatibilidad con Windows** (PR #11 de la comunidad): rutas temporales del sistema, arreglo de codificación GBK, resolución de intérprete en runtime (`python3`/`python`), symlink recurre a junction sin permisos, nuevo instalador PowerShell `install.ps1`
- **Autocuración de cuotas**: el agotamiento de cuota remota oculto en HTTP 200 se detecta; el enrutamiento excluye ese motor y pasa a fuentes de respaldo, y vuelve automáticamente en el siguiente periodo
- **Deadline global de fetch**: `ARGO_FETCH_DEADLINE_S` (60s por defecto) acota la cadena de respaldo; respeta señales de parada 429/503; renderizado tinyfish + sondas de variante `.md`

### v2.8.4: fusión de datos locales + MCP en un comando

- **La investigación profunda puede comer tus datos locales**: los work packages admiten `file_inputs` (CSV / XLSX / literatura de primera mano; se registra el hash, no el contenido) + `recompute` (recalc en sandbox; los desajustes se marcan)
- **El MCP ya no se edita a mano**: `argo mcp inject` escribe Claude Code / Cursor / Windsurf / Codex / OpenCode / Cline (escritura atómica + backup + deshacer)
- **Las consultas simples se quedan baratas**: normalización + puerta de complejidad + sintaxis social/plataforma primero + si se descarta un motor chino, se siguen mirando candidatos
- **Keenable** como fuente web en prueba gratis
- **Seguridad**: recompute bloquea subprocesos de salida a red; las rutas de host son conscientes de la instalación

> Detalle: la tabla siguiente y las [notas de release](docs/) por versión.

---

## Historial de cambios

| Versión | Notas |
|---------|-------|
| **v2.9.7** | **Consolidación de arquitectura + seam web_fetch DSH + License a Apache-2.0**: MIT → Apache License 2.0; el web_fetch del huésped ahora fluye por la cadena argo_fetch (HTTP primero, ascenso a navegador ante desafíos JS, ejecución de doble vía, sin reenvío en errores de herramienta, fallos en cinco clases); 18 motores explicit_only fuera del pool de candidatos de enrutado (cierra el agujero de facturación accidental de motores de pago en auto); cortocircuito de salud del breaker, contabilidad adaptativa de una transacción, desbloqueo automático de cuota al rotar clave, invalidación de caché de ruta por agotamiento; auto/deep descartan motores agotados + early-stop más amplio + agrupación de conexiones POST; js-run arregla el crash fuera del hilo principal. |
| **v2.9.6** | **Motor DeepSeek Search + contrato de operadores de consulta + agrupación de conexiones + puerta de instantáneas de enrutado**: nuevo motor `deepseek_search` activo por defecto (se omite sin key; 445-510ms, el único con cobertura completa authority/rerank_score/hora, ventanas de tiempo realmente efectivas; DSH comparte la key por el seam nativo de credenciales); `site:`/`-site:`/`-término`/`lang:`/`after:`/`before:` convergen en una capa de contrato con posfiltrado real + entrada en clave de caché; agrupación de conexiones POST (ahorra 320-561ms por petición) + preconexión MCP; octen entra en fallback y cobertura (p90 3273→1614ms, escapatoria `ARGO_GENERAL_FALLBACK_LEGACY=1`); corrige decadencia de rango RRF y caparazón de redirección Bing (40.2% de vacíos); nuevas puertas pre-commit y de instantáneas de enrutado; plugin DSH se adapta al doble stack 0.2.1-rc.2 + cobertura unit de alpha.1. |
| **v2.9.5** | **Dominio dedicado de tipo de cambio + deduplicación de dos capas + corrección de falsa penalización + aislamiento de daemon por checkout**: nuevo dominio `fx_query` (tipo/paridad: en vivo + noticia diaria en 675ms vs enciclopedia antes); dedup gana normalización de sufijo (cero dependencias) + revisión difusa rapidfuzz (opcional, `ARGO_DEDUP_FUZZY`, con vuelta atrás); corrige ×0.6 por separadores (docs oficiales de vuelta arriba); negación gana "no-X"; nombres de daemon acotados por checkout. |
| **v2.9.4** | **Atribución explícita de dominio de motor + cortador de cadena de recuperación + sincronización de puertas**: `--engine X` complementa `match_domains` corrigiendo TTL de caché general; motor único sin alternativa omite ejecución vacía L1; reglas `config.yaml` mejoradas; exportación `mcp_launch.sh` reducida; capa de registro local cerrada y calidad mejorada; sincronización de puertas. |
| **v2.9.3** | **Empaquetado completo de posts de X + carril de estado de sesión del navegador + calidad/velocidad de la cadena local**: nuevo `argo tweet` (texto completo/hilo/citas/retweets/medios empaquetados bajo demanda, paquete de 4 archivos con `--out`); nuevo carril de sesión de navegador `argo auth` (perfil persistente por sitio, cookies solo en el almacenamiento cifrado de Chrome, resultados con sesión excluidos de la caché compartida); la cadena local china resuelve shells de Sogou/Baidu sin sesión (conservados 1→5) + gracia de consenso adaptativa (despacho en inglés ~3.0s→2.2-2.5s); js-run como primer carril de la cadena de fetch (reintentos con huella Chrome); consultas ferroviarias con transbordo/escala (embudo 10→1 corregido a un fiel 10→10); `--academic-deep` búsqueda académica profunda con una bandera; 43 motores conectados a dominios + 3 fuentes financieras sin clave + corrección del bloqueo falso de intención; huellas de imagen local 158ms→3.9ms; adelgazamiento del consumo por agentes (overhead fijo MCP −32%). |
| **v2.9.2** | **Compatibilidad verificada con DSH 0.2.1-alpha.1 + tanda de correcciones de enrutamiento/guardas + sub-skill js-run**: las tres formas del plugin DSH verificadas en el último DSH 0.2.1-alpha.1; `argo mcp inject` añade WorkBuddy, cubriendo el 7.º host; degradación de evidencia débil TF-IDF a fuentes auxiliares, piso de fuentes muertas + relleno de slots del breaker, aislamiento de enrutamiento de motores con cuota agotada, corrección de falsos positivos en cascada de serp_guard; importaciones diferidas de engines/evidence (import −50%) y cortocircuito del conjunto de existencia en admisión (open 261→99); guardas de entrada MCP y de argumentos numéricos cerradas; nueva sub-skill js-run (JS web sin navegador, P50 ≈1ms). |
| **v2.9.1** | **Optimización de calidad de contenido + resistencia a granjas de contenido + adaptación a la última versión**: evaluación de calidad de contenido mejorada, con mayor capacidad de identificar y filtrar contenido de baja calidad generado en masa; adaptación a la última versión para una colaboración sin fisuras; la búsqueda local añade una guarda de su propio árbol de instalación para evitar que los resultados se contaminen con su propio código fuente. |
| **v2.9.0** | **Optimización de fuentes + paridad plugin/CLI + lenguas minoritarias**: fuentes 237→253 (sin clave 198→219); se añaden 14 fuentes de noticias en lenguas minoritarias, la fuente de texto completo CORE, TinEye de búsqueda inversa de imágenes, Bing RSS y más; Baidu y Sogou revividas; 18 comandos CLI corresponden uno a uno con 19 herramientas MCP; cadena de importación −79%, rerank 33ms→1.5ms, aciertos de caché notablemente mejorados; corrección de seguridad entre procesos en la ruta de escritura de cuotas; nuevo registro de uso local `argo stats`. Ver [notas de la versión](docs/RELEASE_NOTES_v2.9.0.md) |
| **v2.8.9** | **Salida más ligera + recuperación más rica y rápida + 5 fuentes internacionales y de verificación**: salida por defecto 15.5KB→5.2KB (−66%, `--envelope` restaura el sobre completo); la caché de decisiones de enrutado reduce las consultas repetidas −30%; despacho en red lenta −36% (dominios serie con respaldo automático tras 0.8s); revisión de la cadena de fetch en cinco rondas (recall +35%, latencia −30%, P90 de cola larga −8%) + restauración de estructura del cuerpo (títulos/listas/tablas 0/6→6/6) + corrección de la puntuación de calidad para CJK; nuevas fuentes sin clave Guardian RSS / France 24 / DW / FactCheck.org / Full Fact (232→237, sin clave 194→198, dominios 90→92), gdelt retirado; seis defectos de autoconsistencia corregidos + embudo de seis etapas + herramienta de repetición sin conexión (`scripts/replay_eval.py`) + puertas de despliegue post-política y contratos de umbral por escenario. Ver [notas de la versión](docs/RELEASE_NOTES_v2.8.9.md) |
| **v2.8.8** | **Correcciones reportadas por usuarios reales (#12 silencio del alias de clave, #13 fetch sin proxy) + aceleración general + fuentes 218 → 232**: despacho de salida unificado (`ARGO_PROXY` / reglas por dominio / variables de proxy estándar, respetando `NO_PROXY`); 16 puntos de lectura de claves unificados en la cadena de alias; arranque en frío 2.1s→0.55s, caché de configuración 50–82ms→16–18ms, parada temprana con umbral de planitud QPP, `--list-engines --detail` reducido 152KB→51KB; nuevos `argo answer` (respuestas directas con citas) y `argo watch` (detección de cambios web), 14 fuentes sin clave (tendencias y vida diaria de China / avisos de seguridad / académico de acceso abierto / directorios de skills / búsqueda para agentes), 69 motores reclasificados (cuota del fallback `web_general` 41%→20%, nuevo dominio security); rutas convencionales por plataforma (`argo paths`) + Python 3.9 + concurrencia acotada que hace efectivos los timeouts; search.py dividido en módulos 3351→2526 líneas, golden de relevancia sobre 22 motores, puertas de defectos estáticos y de contrato de salida. Ver [notas de la versión](docs/RELEASE_NOTES_v2.8.8.md) |
| **v2.8.7** | **218 fuentes / 89 dominios + tres canales de salida directa del cuerpo + disciplina de disparo de rutas + corrección de cero resultados en macro**: 50 fuentes nuevas acumuladas en los lotes 7/8/9 (leyes, estándares, inteligencia de seguridad, academia, noticias, entretenimiento, energía/transporte, legal/administrativo), motores stackexchange y doi; sondeo de nivel 0 llms.txt y variantes `.md` en la cadena de fetch, más nivel lector r.jina.ai; corrección de la lista de motores separada por comas en `--engine`, alcance de tfidf y route_reason, matriz de control de rutas negativas, golden de ranking y puertas de ablación de fusión; las consultas macro de China priorizan el buró nacional de estadística, la recuperación de cero resultados abre L3 y los motores de rescate se contabilizan con honestidad. Ver [notas de la versión](docs/RELEASE_NOTES_v2.8.7.md) |
| **v2.8.6** | **Carrera hedged + reparto de tres fuentes de Zhihu + despacho declarativo por idioma + puerta de alcanzabilidad + protocolo de búsqueda académica**: carrera con ventana de gracia para el primer motor (los motores rápidos pagan 1 llamada), búsqueda global y datos personales de Zhihu con antiexterminio, despacho por idioma/académico de subconsultas (fuentes en inglés y 17 fuentes académicas en la recolección), metadatos de idioma por motor y puerta de alcanzabilidad (las fuentes muertas salen a la luz), cola geo −56%, protocolo de construcción de consultas académicas. Ver [notas de la versión](docs/RELEASE_NOTES_v2.8.6.md) |
| **v2.8.5** | **Herramientas nativas del plugin DSH + MCP apagado por defecto + compatibilidad Windows + autocuración de cuotas + deadline de fetch**: `argo_search`/`argo_fetch` como herramientas nativas de primera clase (CLI de un tiro, mismo motor y guardas que MCP, esquema de fuente única + puerta contra deriva); tres formas de conexión, MCP a demanda; compatibilidad Windows (rutas temp / GBK / resolución de intérprete / junction / `install.ps1`, PR #11); bucle de autocuración de cuotas (detección de sobre HTTP 200 + exclusión de ruta + autocuración por periodo); deadline global de fetch (`ARGO_FETCH_DEADLINE_S`) + renderizado tinyfish + sondas `.md`; env de recarga caliente y directorio de estado de fuente única. [Notas](docs/RELEASE_NOTES_v2.8.5.md) |
| **v2.8.4** | **Fusión de datos locales + inyección MCP multi-cliente + búsqueda estructurada + Keenable**: investigación L1 con datos locales de primera mano (`file_inputs` + `recompute` + `local_sources`); `argo mcp inject` (`mcp/clients.yaml` declarativo); normalización / variantes / puerta de complejidad / sintaxis social primero / arreglo TF-IDF / `--include-local`; motor Keenable (prueba gratis); endurecimiento de seguridad. Ver [notas de release](docs/RELEASE_NOTES_v2.8.4.md) |
| **v2.8.3** | **Arreglo de enrutamiento multilingüe + anysearch in-process + RRF ponderado**: ja/ko devuelven el idioma objetivo; DE/FR/ES/IT vía anysearch; downweight weakest-link (paper 2508.01405). Ver [notas de release](docs/RELEASE_NOTES_v2.8.3.md) |
| **v2.8.2** | **Windows + semántica de evidencia unificada**: se quita el límite npm `os`; UTF-8 contra cuelgues GBK; `dsh.bundle` en el paquete principal; puerta de calidad de `wide_research`. Ver [notas de release](docs/RELEASE_NOTES_v2.8.2.md) |
| **v2.8.0** | **Bucle de evidencia + empleos v3 + clima dual**: `fetch_required` / `--verify`; `argo job`; wttr.in + Open-Meteo; Parallel / You.com. Ver [notas de release](docs/RELEASE_NOTES_v2.8.0.md) |
| **v2.7.3** | HttpClient en capa de motor; TF-IDF activa 25 verticales; TTL de 70 dominios; verticales bilingües. Ver [notas de release](docs/RELEASE_NOTES_v2.7.3.md) |
| **v2.7.2** | Búsqueda profesional con sesión (ego-search, off por defecto); JA/KO ya no mezclan motores chinos. Ver [notas de release](docs/RELEASE_NOTES_v2.7.2.md) |
| **v2.7.1** | Endurecimiento SSRF + arreglo del estado de salud del routing. Ver [notas de release](docs/RELEASE_NOTES_v2.7.1.md) |
| **v2.7.0** | **Tarjetas modales verticales estructuradas**: motores nativos `bocha` / `bocha_ai` integrados; el dominio `modal_card` reconoce en un solo lugar tarjetas en tiempo real — billetes de tren / precios de combustible / metales preciosos / calendario perpetuo / horóscopo / consulta de teléfono / vehículos / citas médicas, etc.; corregido un defecto de análisis web de `bocha`. Ver [notas de la versión](docs/RELEASE_NOTES_v2.7.0.md) |
| **v2.6.2** | Fusión de líneas de mejora independientes: conciencia del entorno de red / RRF ponderado + caché semántica / desactivación adaptativa de motores / seguridad de contenido + variantes de consulta / tres grandes motores verticales / mejora del enrutamiento de dominios ja-ko; incluye la corrección de enrutamiento de v2.6.1. Ver [notas de la versión](docs/RELEASE_NOTES_v2.6.2.md) |
| **v2.6.1** | Versión de corrección de v2.6.0: corrección de daño colateral de enrutamiento (`capital of` ya no se apodera de fact_check); sincronización de versión. Ver [notas de la versión](docs/RELEASE_NOTES_v2.6.1.md) |
| **v2.6.0** | **Búsqueda multilingüe** (detect / engine params / cross-lang fallback); verticales film·sports·geo·org·media; recovery anti-contaminación; familias de capacidad + regresión matrix; ~120+ fuentes. Ver [notas de release](docs/RELEASE_NOTES_v2.6.0.md) |
| **v2.5.1** | Fuentes de respuesta finanzas/macro/química más densas; tiers de motor + presupuesto combo; [notas v2.5.1](docs/RELEASE_NOTES_v2.5.1.md) |
| **v2.5.0** | Script de instalación + npx; rewrite desacoplado del routing; caché hot-path; MCP compacto |
| **v2.4.0** | Fallback de ruta de baja puntuación + filtros de mal-enrutado social; caché depth / soft hits; breakers y caché negativa; `engine_outcomes` |
| **v2.2–v2.3** | Evidencia en dos etapas, tabla de fuentes chinas, content_signals, stack fetch, más motores |
| **v2.1** | Capa de motores sociales (UGC multi-plataforma) |
| **v1.x** | Nombre unificado Argo; enrutamiento multi-motor + caché de dos capas |

---

## Contribuir

Issues y PRs bienvenidos. Si cambias lógica de routing o evidencia, añade tests:

```bash
python3 -m pytest tests/test_unit.py tests/test_multilingual.py -q
python3 scripts/regression_p0p1.py --offline
python3 scripts/matrix_search_eval.py --offline
python3 scripts/ab_eval_p0p1.py   # optional, online
```

Antes del commit: sin claves API reales, rutas absolutas de máquina ni cookies de cuenta. Las rutas locales de Skill van en `installs.local.yaml` (gitignored).

## License

Apache License 2.0 © 2026 [taxueseek](https://github.com/taxueseek)

<p align="center">
  <a href="https://github.com/oil-oil/beautify-github-readme"><img src="assets/readme/made-with-beautify.svg" width="300" alt="README made with beautify-github-readme"></a>
</p>

---

> Una buena búsqueda no es ver más: es concluir con confianza, y saber cuándo aún no debes.
