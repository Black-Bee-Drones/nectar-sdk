# Documentation translations (i18n)

Portuguese (Brazil) pages for the [Nectar SDK docs site](https://black-bee-drones.github.io/nectar-sdk/).
English remains the source of truth for module `README.md` files in the package tree.
Python API pages stay English-only; from PT, link to `/api/…` with “(em inglês)”.

## Layout

| Path | Role |
|------|------|
| `i18n/pt/` | Author Portuguese Markdown (edit these) |
| `build/docs-pt/` | Assembled PT docs dir (generated — do not edit) |
| `build/site/pt/` | Built PT HTML under the English site (generated) |

English authored pages stay in `website/` and `docs/`; module reference pages are synced from package READMEs by `scripts/docs/sync_readmes.py`.

## Workflow

1. Edit or add files under `i18n/pt/`, mirroring the site path (e.g. `i18n/pt/setup/index.md` → `/pt/setup/`).
2. Keep meaning, structure, code fences, Mermaid, and identifiers identical to the English source. Follow the glossary below.
3. Run `make docs-sync` (or `make docs`) — never hand-edit `build/`.
4. Preview bilingual site (same URL layout as GitHub Pages):

   ```bash
   make docs-serve
   ```

   Open [http://localhost:8000/nectar-sdk/](http://localhost:8000/nectar-sdk/) and [http://localhost:8000/nectar-sdk/pt/](http://localhost:8000/nectar-sdk/pt/).
   The header language selector switches between them. English-only live reload:
   `make docs-serve-en` (Portuguese URLs 404 in that mode).

5. Add the page to `nav` in `mkdocs.pt.yml` when publishing.
6. Flip the checklist status below (`todo` → `draft` → `reviewed`).

## Quality

- Natural pt-BR; no calque “atrás de” for architectural *behind*.
- Code comments in fences stay English.
- Untranslated targets (API only): escape `/pt/` and mark “(em inglês)”.

## Glossary (pt-BR)

Preferred wording for Portuguese documentation. Do not translate code identifiers, CLI flags, package names, topic names, or API symbols.

| English | Portuguese (docs) | Notes |
|---------|-------------------|--------|
| autonomous | autônomo / autônoma | |
| companion computer | computador de bordo | |
| drone / vehicle | drone / veículo | Prefer “drone” in tutorials |
| flight controller / FCU | controlador de voo / FCU | Keep `FCU` |
| firmware | firmware | Keep as-is |
| mission | missão | |
| takeoff | decolagem / `takeoff` | Verb in prose: “decolar”; method name unchanged |
| land / landing | pousar / pouso | Method `land` unchanged |
| return to launch / RTL | retorno ao ponto de lançamento / RTL | Keep `RTL` next to APIs; spell out once in prose |
| pose | pose | Keep as-is |
| setpoint | setpoint | Keep as-is |
| waypoint | waypoint | Keep as-is |
| transport | transporte | MAVROS/MAVLink “transport” in control docs |
| pose source | fonte de pose | |
| rangefinder | rangefinder / medidor de distância | Prefer “rangefinder” next to APIs |
| obstacle avoidance / obstacle handling | desvio de obstáculos | Never “tratamento de obstáculos” |
| localization | localização | |
| odometry | odometria | |
| frame (TF / image) | frame | Keep in technical context |
| overlay | overlay | Keep as-is |
| handler | handler | Keep class role name; explain in prose if needed |
| factory | factory | Keep pattern name and English word order (“camera factory”); “fábrica” only in plain explanation |
| runtime | runtime | Keep as-is |
| workspace | workspace | |
| driver | driver | |
| simulation / SITL | simulação / SITL | |
| SITL run | execução SITL / sessão SITL | Not “corrida SITL” |
| annotated run | execução anotada | |
| wire format | formato on-wire / formato de transmissão | Not “formato do fio” |
| behind (architecture) | por meio de / em uma interface unificada | Never calque “atrás de” for “behind one interface” |
| indoor / outdoor | indoor / outdoor | Keep as-is next to competition/mission context; “interno/externo” only in plain explanation |
| installation | instalação | |
| setup | configuração / instalação | Prefer “instalação” for install guides; “configuração” for config |
| computer vision | visão computacional | |
| detection | detecção | |
| segmentation | segmentação | |
| classification | classificação | |
| model | modelo | |
| inference | inferência | |
| training | treinamento | |
| ground truth | ground truth | Keep as-is |
| zoom / watch larger | ampliar | Carousel/figcaption UI |
| Get started | Começar | Nav label |
| Setup | Instalação | Nav section for install/setup guides |
| Concepts | Conceitos | |
| Architecture | Arquitetura | |
| Modules | Módulos | |
| Examples | Exemplos | |
| Development | Desenvolvimento | |
| Community | Comunidade | |
| Home | Início | Nav label |
| With / without | Com / sem | Nav / button |

### Code and comments

- Identifiers, CLI flags, topics, package names, API symbols: always English.
- Comments inside fenced code blocks: keep English (same as identifiers).
- Shell prompt hints such as `# pick: control` stay English when they mirror the installer UI.

### Always keep in English

ArduPilot, PX4, MAVROS, MAVLink, Crazyflie, Bebop, ROS 2, Humble, Jazzy, Kilted, Gazebo, Docker, RealSense, T265, Ultralytics, YOLO, DETR, RF-DETR, MediaPipe, Qt6, Black Bee Drones, IMAV, CBR, SAE Eletroquad, Nectar SDK, and all code/API names.

If another language is added later, either extend this README with a locale section or split a per-locale glossary back out (e.g. `glossary.es.md`).

## Phase checklist

Statuses: `todo` | `draft` | `reviewed`.

### Phase 0 — Standards + Phase 1 polish

| Page | Status |
|------|--------|
| Glossary (this README) | reviewed |
| `pt/index.md` | reviewed |
| `pt/get-started/index.md` | reviewed |
| `pt/get-started/control.md` | reviewed |
| `pt/get-started/vision.md` | reviewed |
| `pt/get-started/ai.md` | reviewed |
| `pt/concepts/architecture.md` | reviewed |
| `pt/setup/index.md` | reviewed |
| `pt/setup/drivers.md` | reviewed |
| `pt/setup/simulation.md` | reviewed |
| `pt/setup/realsense.md` | reviewed |
| `pt/setup/configuration.md` | reviewed |
| `pt/setup/compatibility.md` | reviewed |

### Phase 1b — Onboarding gaps

| Page | Status |
|------|--------|
| `pt/get-started/with-without.md` | reviewed |
| `pt/setup/docker.md` | reviewed |

### Phase 2 — Module overviews

| Page | Status |
|------|--------|
| `pt/modules/control/index.md` | reviewed |
| `pt/modules/vision/index.md` | reviewed |
| `pt/modules/ai/index.md` | reviewed |
| `pt/modules/sensors.md` | reviewed |
| `pt/modules/interface.md` | reviewed |
| `pt/modules/simulation.md` | reviewed |
| `pt/modules/interfaces.md` | reviewed |
| `pt/modules/utils.md` | reviewed |

### Phase 3 — Control deep reference

| Page | Status |
|------|--------|
| `pt/modules/control/vehicle.md` | reviewed |
| `pt/modules/control/mavros.md` | reviewed |
| `pt/modules/control/mavlink.md` | reviewed |
| `pt/modules/control/ardupilot.md` | reviewed |
| `pt/modules/control/px4.md` | reviewed |
| `pt/modules/control/localization/index.md` | reviewed |
| `pt/modules/control/localization/concepts.md` | reviewed |
| `pt/modules/control/localization/legacy.md` | reviewed |
| `pt/modules/control/obstacles.md` | reviewed |
| `pt/modules/control/pid.md` | reviewed |
| `pt/modules/control/bebop.md` | reviewed |
| `pt/modules/control/crazyflie.md` | reviewed |

### Phase 4 — Vision + AI deep reference

| Page | Status |
|------|--------|
| `pt/modules/vision/camera.md` | reviewed |
| `pt/modules/vision/algorithms.md` | reviewed |
| `pt/modules/vision/nodes.md` | reviewed |
| `pt/modules/ai/detection.md` | reviewed |
| `pt/modules/ai/segmentation.md` | reviewed |
| `pt/modules/ai/classification.md` | reviewed |

### Phase 5 — Examples, projects, community, development

| Page | Status |
|------|--------|
| `pt/modules/examples/index.md` | reviewed |
| `pt/modules/examples/control.md` | reviewed |
| `pt/modules/examples/vision.md` | reviewed |
| `pt/modules/examples/ai.md` | reviewed |
| `pt/modules/examples/sensors.md` | reviewed |
| `pt/projects/index.md` | reviewed |
| `pt/community/index.md` | reviewed |
| `pt/development/commands.md` | reviewed |
| `pt/project/contributing.md` | reviewed |
| `pt/project/releasing.md` | reviewed |
| `pt/project/code-of-conduct.md` | reviewed |
| `pt/project/security.md` | reviewed |
| API (`website/api/*`) | skipped (EN only) |

### Phase 6 — Consistency

| Item | Status |
|------|--------|
| Glossary grep / link / switcher pass | reviewed |
