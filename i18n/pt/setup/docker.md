# Docker

## Imagens

Imagens x86_64 (`Dockerfile`) recebem tag por distro ROS (`nectar-sdk:<distro>`), por exemplo `:humble`, `:jazzy`, `:kilted`; variantes de AI acrescentam `-full-<torch>`. Imagens Jetson (`Dockerfile.jetson`) recebem as tags `:jetson` / `:jetson-full` — veja [Jetson (Orin)](#jetson-orin).

| Tag | Conteúdo | PyTorch |
|-----|----------|---------|
| `:humble` | core + control + vision + interface + realsense + oakd + `INSTALL_DRONE=all` | Nenhum |
| `:humble-t265` | Tudo acima + librealsense v2.53.1 + suporte a T265 | Nenhum |
| `:humble-full-cpu` | Tudo acima + pacotes de AI | CPU |
| `:humble-full-cu126` | Tudo acima + pacotes de AI | CUDA 12.6 |
| `:jetson` | todos os módulos não-AI (base L4T) | Nenhum |
| `:jetson-full` | Tudo acima + AI + RealSense (RSUSB) | CUDA 12.6 (wheels Jetson) |

## Início rápido

```bash
make docker-build       # SDK (no AI, ~5 min)
make docker-run         # auto-selects image, GPU auto-detected
make docker-exec        # open more terminals
```

No Jetson, esses comandos direcionam automaticamente para `Dockerfile.jetson` (tags `:jetson`) e `--runtime nvidia` — veja [Jetson (Orin)](#jetson-orin).

## Build

```bash
make docker-build                              # SDK (no AI)
make docker-build-full                         # + AI with PyTorch CPU (default)
TORCH_VARIANT=cu126 make docker-build-full     # + AI with PyTorch CUDA 12.6
TORCH_VARIANT=auto  make docker-build-full     # auto-detect CUDA from nvidia-smi
```

### Distro ROS diferente

```bash
ROS_DISTRO=jazzy make docker-build
ROS_DISTRO=jazzy TORCH_VARIANT=cu126 make docker-build-full
```

### Fixar uma versão específica do PyTorch (avançado)

Por padrão o pip resolve a versão mais recente do torch compatível com o índice CUDA escolhido.
Sobrescreva com variáveis de ambiente:

```bash
TORCH_VERSION=2.9.1 TORCHVISION_VERSION=0.24.1 TORCH_VARIANT=cu126 make docker-build-full
```

## Rodar

```bash
make docker-run         # shows menu if multiple images exist
make docker-exec        # extra terminal in running container
```

`docker-run` automaticamente:

- Detecta as imagens disponíveis (mostra um menu se houver mais de uma)
- Adiciona `--gpus all` quando detecta uma GPU NVIDIA
- Monta o projeto local dentro do container (edição de código ao vivo)
- Monta X11, câmeras (`/dev/video*`), USB, `/dev`
- Habilita host networking para o ROS2

O mount do projeto local significa que edições em arquivos Python no host aparecem
instantaneamente dentro do container (via `--symlink-install`). Para mudanças em C++ ou
em mensagens, rode `colcon build` dentro do container.

Para rodar só com o código já embutido na imagem (sem mount local):

```bash
DOCKER_NO_MOUNT=true make docker-run
```

### Windows

**Nota:** usuários Windows não podem usar comandos `make` nem o script bash `setup.sh`. Use o script auxiliar do PowerShell.

**PowerShell:**

```powershell
.\docker\run_docker_win.ps1 build jazzy full-cu126 -Realsense   # + librealsense (~15-20 min)
.\docker\run_docker_win.ps1 test jazzy full-cu126
.\docker\run_docker_win.ps1 run jazzy full-cu126                # GUI + GPU + USB bus
.\docker\run_docker_win.ps1 exec
```

O script suporta:

- Distros ROS 2: `humble`, `jazzy`, `kilted`
- Variantes de build: `full-cpu`, `full-cu126` (para builds completos; `cu126` casa com os pins padrão do torch 2.9.x)
- `-Realsense` em `build` — define `INSTALL_REALSENSE=true` (librealsense + realsense-ros a partir do source)
- Detecção automática de GPU (exige Docker Desktop com NVIDIA Container Toolkit)
- GUI via [VcXsrv](https://sourceforge.net/projects/vcxsrv/) / XLaunch (`DISPLAY=host.docker.internal:0.0`)
- USB via [usbipd-win](https://github.com/dorssel/usbipd-win) (subcomando `usb`; veja abaixo)

#### GUI (VcXsrv)

1. Instale o [VcXsrv](https://sourceforge.net/projects/vcxsrv/) e rode o **XLaunch**.
2. **Multiple windows**, display **0**, **Start no client**.
3. Habilite **Disable access control** (obrigatório).
4. Inicie o XLaunch **antes** do `run`. Desmarque **Native opengl** se a janela do Qt aparecer em branco.

```powershell
.\docker\run_docker_win.ps1 run jazzy full-cu126

# inside container:

ros2 run nectar app.py
```

#### Câmeras USB e RealSense

<span id="usb-cameras-and-realsense"></span>

O Docker Desktop não repassa dispositivos USB nativamente ([Docker FAQ](https://docs.docker.com/desktop/troubleshoot-and-support/faqs/general/#can-i-pass-through-a-usb-device-to-a-container)). Use o **usbipd-win** para compartilhar dispositivos com a VM WSL `docker-desktop` e depois monte `/dev/bus/usb` dentro do container (o comando `run` faz isso por padrão).

**Instale o usbipd-win** ([releases](https://github.com/dorssel/usbipd-win/releases)) e depois:

```powershell
.\docker\run_docker_win.ps1 usb list
```

| Dispositivo | Windows Docker | Notas |
|--------|----------------|-------|
| **Intel RealSense D435i** | Suportado (com instalação) | Usa libusb (RSUSB); **não** precisa de `/dev/video*`. Rebuild com `-Realsense`. |
| **Webcam integrada / USB** | Limitado | O USB conecta e o `lsusb` vê o dispositivo, mas o kernel WSL do Docker Desktop costuma não ter o driver UVC — `/dev/video0` pode não aparecer, então `webcam` / `VideoCapture(0)` do OpenCV falha. Use RealSense ou Linux nativo para fluxos de webcam. |

**Fluxo de trabalho com RealSense:**

```powershell

# 1) One-time bind (admin PowerShell) — or use: .\run_docker_win.ps1 usb bind realsense

usbipd bind --busid <BUSID>    # from: .\run_docker_win.ps1 usb list

# 2) Attach before each session (re-attach after unplug with -AutoAttach)

.\docker\run_docker_win.ps1 usb attach realsense -AutoAttach

# 3) Rebuild image with RealSense stack (once, ~15-20 min extra)

.\docker\run_docker_win.ps1 build jazzy full-cu126 -Realsense

# 4) Probe inside container

.\docker\run_docker_win.ps1 -Command usb -UsbAction check -Distro jazzy -Variant full-cu126

# 5) Run and test

.\docker\run_docker_win.ps1 run jazzy full-cu126
```

Dentro do container:

```bash
source /opt/ros/$ROS_DISTRO/setup.bash
source /home/ros2_ws/install/local_setup.bash
rs-enumerate-devices
ros2 launch realsense2_camera rs_launch.py
```

Enquanto um dispositivo está anexado ao WSL, o acesso é **exclusivo** — apps do Windows não conseguem usá-lo até um `usbipd detach`.

**Webcam (experimental):** `usb attach webcam` compartilha o dispositivo, mas sem `/dev/video*` o OpenCV não consegue abri-lo. Se nós de vídeo aparecerem (`usb list` os mostra sob docker-desktop), o `run` acrescenta flags `--device` automaticamente.

Passe `-NoUsb` no `run` para pular os mounts de volume USB.

**Nota:** para aplicações GUI no Windows, garanta que o VcXsrv esteja rodando com o controle de acesso desabilitado.

## GPU

| Hardware | Comando de build |
|----------|-------------|
| Sem GPU | `make docker-build-full` |
| GPU NVIDIA | `TORCH_VARIANT=cu126 make docker-build-full` |
| Auto-detecção | `TORCH_VARIANT=auto make docker-build-full` |
| Jetson (Orin) | `make docker-build-full` (auto-detectado → `Dockerfile.jetson`) |
| Não precisa de AI | `make docker-build` |

O passthrough de GPU é adicionado automaticamente em runtime: `--gpus all` em x86_64 quando `nvidia-smi` é encontrado, `--runtime nvidia` no Jetson.
Veja a [documentação de GPU do Docker](https://docs.docker.com/desktop/features/gpu/) para a instalação.

Você também pode instalar o torch CUDA dentro de um container CPU já em execução:

```bash
./scripts/setup.sh pytorch cu126
./scripts/setup.sh python ai
```

## Jetson (Orin)

`make docker-build` / `docker-build-full` auto-detectam o Jetson (Tegra) e fazem build do
[`Dockerfile.jetson`](https://github.com/Black-Bee-Drones/nectar-sdk/blob/main/docker/Dockerfile.jetson): uma base `l4t-jetpack` com ROS 2 Humble e o SDK;
`-full` acrescenta o PyTorch a partir do [índice do Jetson AI Lab](https://pypi.jetson-ai-lab.io/jp6/cu126)
(CUDA 12.6) mais a stack de AI. As imagens recebem as tags `:jetson` / `:jetson-full`.

```bash
make docker-build        # nectar-sdk:jetson
make docker-build-full   # nectar-sdk:jetson-full
make docker-run          # auto-uses --runtime nvidia (Tegra rejects --gpus all)
```

Exige o NVIDIA Container Toolkit. Sobrescreva a imagem base ou o índice do torch com
`L4T_TAG=` / `TORCH_INDEX=`. Esta é a imagem do SDK (control/vision/AI); o producer VSLAM
sem GPS é um container separado — veja [Isaac ROS Visual SLAM](#isaac-ros-visual-slam-jetson).

O RealSense também é opt-in aqui (backend RSUSB, necessário para a IMU do D435i no
JetPack 6; CUDA é opcional). O build compila o librealsense a partir do source, então
leva ~40-50 min em um Orin Nano:

```bash
INSTALL_REALSENSE=true REALSENSE_CUDA=true make docker-build-full
```

### Publicando a imagem Jetson

O CI x86 não consegue fazer build da imagem Jetson (L4T), então ela é publicada manualmente a partir de
um Jetson no release. `make docker-publish-jetson` verifica a imagem local
nesse hardware (SDK + `torch.cuda` + RealSense) e só faz push se a verificação passar:

```bash
docker login                                                       # Docker Hub account
INSTALL_REALSENSE=true REALSENSE_CUDA=true make docker-build-full  # complete image
make docker-publish-jetson JETSON_NAMESPACE=blackbeedrones VERSION=v1.1.0
```

Isso faz push de três tags: `:jetson-full-<VERSION>`, `:jetson-full-jp6.2` (linha do JetPack
— a imagem só roda em um JetPack compatível) e `:jetson-full`. Passe
`JETSON_TARGET=sdk` para publicar a imagem sem AI em vez disso.

## Backends de controle

Backends de controle são opt-in via o build arg `INSTALL_DRONE`. Use `all` para a
imagem de release publicada (`make drone-all`: MAVROS + Crazyflie são obrigatórios; Bebop e
PX4 uXRCE-DDS são best-effort por distro). A imagem core traz só MAVLink (`pymavlink`).

**Conjunto publicado** (`INSTALL_DRONE=all`):

```bash
INSTALL_DRONE=all make docker-build
```

**Só MAVLink/pymavlink** (padrão):

```bash
make docker-build
```

**Lista customizada:**

```bash
INSTALL_DRONE="mavros crazyflie" make docker-build
```

O Crazyflie instala via apt no Humble/Jazzy e a partir do source no Kilted quando não há
binário apt disponível. Bebop e PX4-DDS são tentados em `all`, mas são pulados com um aviso
se falharem em uma determinada distro. PX4 sobre MAVROS precisa do `mavros` (incluído em `all`).

## RealSense

O suporte a RealSense é opt-in (compila o librealsense a partir do source, acrescenta ~15-20 min e ~500 MB).
É instalado no stage `sdk`, então tanto a imagem base (`:<distro>`) quanto a full (`:<distro>-full-*`) o incluem.

**SDK com RealSense** (sem AI):

```bash
INSTALL_REALSENSE=true make docker-build
```

**Full com RealSense + AI + GPU**:

```bash
INSTALL_REALSENSE=true TORCH_VARIANT=cu126 make docker-build-full
```

**Com librealsense acelerado por CUDA**:

```bash
INSTALL_REALSENSE=true REALSENSE_CUDA=true TORCH_VARIANT=cu126 make docker-build-full
```

As versões são auto-selecionadas por distro ROS (`scripts/lib/config.sh`). Os pins padrão de
librealsense / realsense-ros do D4xx por distro estão em
[COMPATIBILITY.md](compatibility.md#pinned-versions).

**T265 (só no Humble, descontinuada):** librealsense **v2.53.1** e realsense-ros **4.51.1**.
Sobrescreva no momento do build:

```bash

# T265 tracking camera (Humble only, last supported versions)

LIBREALSENSE_VERSION=v2.53.1 REALSENSE_ROS_TAG=4.51.1 \
  INSTALL_REALSENSE=true make docker-build
```

Regras udev e scripts de hotplug para D435/D435i/D455/T265 estão incluídos para
acesso a dispositivos em runtime (seguindo o padrão Docker do
[VSLAM-UAV](https://github.com/bandofpv/VSLAM-UAV)).

### Câmera de tracking T265 (Docker)

Usa as versões de override da T265 acima. O build usa `FORCE_RSUSB_BACKEND=true` (libusb
em user-space), então qualquer kernel do host funciona, incluindo o 6.x. O Docker mantém essas
versões legadas isoladas do librealsense mais novo no host.

**Build** (exige a imagem base `:humble` — construída automaticamente se estiver faltando):

```bash
make docker-build-t265
```

Isso produz `nectar-sdk:humble-t265`. Internamente ele inicia um container
a partir de `:humble`, instala librealsense v2.53.1 + realsense-ros 4.51.1,
refaz o build do workspace e commita o resultado.

**Run** (conecte a T265 primeiro):

```bash
make docker-run   # select the humble-t265 image from the menu
```

O comando `docker-run` já passa `--privileged`, `--device=/dev/bus/usb`
e forwarding de X11, o que é suficiente para acesso a câmeras USB e ferramentas GUI.

**Teste dentro do container:**

```bash

# Check if the T265 is detected

rs-enumerate-devices

# GUI viewer (requires X11 forwarding)

realsense-viewer

# ROS 2 launch

source /home/ros2_ws/install/setup.bash
ros2 launch realsense2_camera rs_launch.py device_type:=t265

# Relay the camera pose to the FCU with the SDK vision-pose bridge (replaces the

# external vision_to_mavros). Point input_topic at the T265 pose topic; see

# nectar/nectar/control/localization/README.md.

ros2 launch nectar vision_pose.launch.py backend:=mavros
```

**Regra udev no host** (opcional, para permissões USB consistentes):

```bash

# Copy the rules file to the host

sudo cp docker/realsense/99-realsense-libusb-custom.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

> **Nota:** se o `realsense-viewer` falhar com erros de OpenGL, defina `LIBGL_ALWAYS_SOFTWARE=1` dentro do
> container para renderização via software.

## Isaac ROS Visual SLAM (Jetson)

O **producer** do pipeline de localização (RealSense + Isaac ROS Visual SLAM) roda
no container de dev do Isaac ROS. Ele é separado da imagem principal do SDK porque
o Isaac ROS só é suportado dentro do seu próprio ambiente de dev (que traz o
repositório apt da NVIDIA Isaac e as versões corretas de CUDA/TensorRT/VPI). A imagem
do SDK ou o host roda o lado **consumer** (MAVROS + ponte vision-pose), compartilhando
`ROS_DOMAIN_ID`.

[`docker/isaac_vslam`](https://github.com/Black-Bee-Drones/nectar-sdk/tree/main/docker/isaac_vslam) é um wrapper autocontido em torno do
[`isaac_ros_common/run_dev.sh`](https://nvidia-isaac-ros.github.io/v/release-3.2/concepts/docker_devenv/index.html) oficial da NVIDIA.
Um único comando clona o `isaac_ros_common` (`release-3.2`) e faz build da imagem
com a key `ros2_humble.realsense.nectar` de baixo para cima: a base NVCR pré-compilada →
`realsense` (o [`Dockerfile.realsense`](https://github.com/NVIDIA-ISAAC-ROS/isaac_ros_common) do isaac_ros_common:
librealsense `v2.55.1` compilado a partir do source com o **backend RSUSB/libuvc** +
realsense-ros `4.51.1-isaac`) → `nectar`
([`Dockerfile.nectar`](https://github.com/Black-Bee-Drones/nectar-sdk/blob/main/docker/isaac_vslam/Dockerfile.nectar): Visual SLAM + o
helper `nectar-vslam`). O `run_dev.sh` fornece toda a config de device/GPU/X11/Jetson
(`--privileged`, `--runtime nvidia`, mounts do tegra, `-e ROS_DOMAIN_ID`); o wrapper acrescenta
`-v /dev/bus/usb:/dev/bus/usb` para que o RealSense continue visível entre re-enumerações de USB.

> **Nota — O primeiro build leva ~40-50 min em um Orin Nano:** ele compila o librealsense a partir do source;
> as execuções seguintes usam cache.
> **Nota — Por que o backend RSUSB (não instale `realsense2-camera` via apt):** o backend RSUSB é
> necessário para a IMU do D435i no JetPack 6, que removeu o suporte de kernel `hiddraw` do qual o build
> apt do `realsense2-camera` depende (senão: `No HID info provided, IMU is disabled`).
> Instalar `realsense2-camera` via apt no `Dockerfile.nectar` traria esse build quebrado de kernel-HID
> no lugar do build a partir do source.
> **Aviso — Mounts de device: bind em `/dev/bus/usb`, nunca em todo o `/dev`:** com `--privileged` sozinho
> o `/dev` do container é um snapshot estático tirado na criação, então os nós da câmera — recriados na
> enumeração/reset de USB depois que o container inicia — nunca aparecem; o bind mount de `/dev/bus/usb`
> é uma visão viva do host que sobrevive a essas re-enumerações. Não monte todo o `/dev` (`-v /dev:/dev`):
> isso esconde os nós de device de GPU que o `--runtime nvidia` injeta, e como o `run_dev.sh` roda o cuVSLAM
> como o usuário não-root `admin`, a inicialização do pool de memória CUDA falha com `cudaErrorNotSupported` /
> `setCUDAMemoryPoolSize Error: GXF_FAILURE` (funciona como root, falha como `admin`).

**Inicie (ou entre no) container Isaac** — clone + build (se necessário) + entrada:

```bash
make isaac-run        # or: ./docker/isaac_vslam/run_docker.sh
```

**Dentro do container, inicie o producer** com o helper já embutido:

```bash
nectar-vslam          # alias → launch do nectar montado; encaminha "$@"
```

Todos os parâmetros de RealSense + Visual SLAM ficam no YAML montado (edite no host ou
dentro do container e reinicie o `nectar-vslam`):

`/workspaces/isaac_ros-dev/src/nectar-sdk/nectar/nectar/control/localization/config/vslam_realsense.yaml`

Não edite `/opt/ros/humble/share/isaac_ros_visual_slam/...` — esse é o launch empacotado da
NVIDIA, não o do Nectar. O padrão habilita RGB (`/camera/color/...`) junto com infra para
o cuVSLAM; o SLAM não consome color. Config alternativa:
`nectar-vslam params_file:=/path/to/other.yaml`.

> **Aviso — rode só um container cuVSLAM por vez:** o container usa `--ipc=host` e
> `--pid=host`, então se o cuVSLAM travar, o processo GXF morto deixa um mutex robusto em memória
> compartilhada que aborta o próximo launch com `cudaErrorNotSupported` / `setCUDAMemoryPoolSize Error` e
> uma assertion `pthread ... ESRCH`. Recupere removendo o container (ao qual o `run_dev.sh`, senão,
> voltaria a se conectar):
>
> ```bash
> make isaac-stop       # docker rm -f the nectar (and old isaac) containers
> make isaac-run        # fresh container; cuVSLAM initializes cleanly
> ```

Lado consumer (imagem do SDK ou host), mesmo `ROS_DOMAIN_ID`:

```bash
ros2 launch nectar vision_pose.launch.py backend:=mavros fcu_url:=/dev/ttyTHS1:921600
```

Requisitos no Jetson: Docker (non-root), `git-lfs` e o NVIDIA Container
Toolkit. Para permissões USB do RealSense no host, instale as regras udev em
[`docker/realsense`](https://github.com/Black-Bee-Drones/nectar-sdk/tree/main/docker/realsense).

### Requisitos de hardware (cuVSLAM)

O Isaac ROS Visual SLAM (cuVSLAM) tem um piso de GPU rígido, segundo as páginas oficiais de
[compute setup](https://nvidia-isaac-ros.github.io/v/release-3.2/getting_started/hardware_setup/compute/index.html)
e [Visual SLAM](https://nvidia-isaac-ros.github.io/v/release-3.2/repositories_and_packages/isaac_ros_visual_slam/index.html)
(release-3.2):

- Jetson: família Orin no JetPack 6.1 / 6.2.
- x86_64: GPU NVIDIA discreta, **arquitetura Ampere ou mais recente**, **>= 8 GB de VRAM**
  (12 GB+ recomendado), driver **560+**, CUDA 12.6+, Ubuntu 22.04+.

GPUs pré-Ampere **não** são compatíveis com a biblioteca cuVSLAM (os maintainers
confirmam isso para arquiteturas mais antigas em
[isaac_ros_visual_slam#117](https://github.com/NVIDIA-ISAAC-ROS/isaac_ros_visual_slam/issues/117)).
Uma placa GTX série 16 (Turing) ou anterior não consegue rodar o nó Visual SLAM. A
imagem do container ainda **faz build e inicia** nesse hardware (útil para validar
a fiação Docker do SDK), mas o próprio nó cuVSLAM não vai rodar -- teste o pipeline
de localização via o sim indoor do Gazebo em vez disso (veja o
[módulo Simulation](../modules/simulation.md)), que exercita as mesmas
pontes e tópicos sem precisar de cuVSLAM/Jetson.

### Versão e distro ROS

O Isaac ROS vincula cada linha de release a uma distro ROS 2 e um JetPack, segundo as
[release notes](https://nvidia-isaac-ros.github.io/releases/index.html):

| Isaac ROS | ROS 2 | Ubuntu | JetPack | CUDA | Método de build |
|---|---|---|---|---|---|
| **3.2** (padrão do SDK) | Humble | 22.04 | 6.1 / 6.2 | 12.6 | `isaac_ros_common/run_dev.sh` (este wrapper) |
| 4.x (mais recente, 4.4) | Jazzy | 24.04 | 7.x | 13.0 | Repo APT do Isaac ROS + CLI `isaac-ros` |

O SDK fixa **`ISAAC_ROS_VERSION=release-3.2`** ([scripts/lib/config.sh](https://github.com/Black-Bee-Drones/nectar-sdk/blob/main/scripts/lib/config.sh))
porque o Jetson alvo roda JetPack 6.2 (Humble). O Isaac ROS 4.x **não** é
um simples bump de config: ele exige um reflash para JetPack 7 (Ubuntu 24.04 / Jazzy) e usa uma
toolchain diferente.

#### Migrando para o Isaac ROS 4.x (futuro, requer JetPack 7)

O 4.x substitui o `run_dev.sh` pela [CLI `isaac-ros`](https://github.com/NVIDIA-ISAAC-ROS/isaac-ros-cli)
sobre um repositório APT ([getting started](https://nvidia-isaac-ros.github.io/getting_started/)):

```bash

# 1. Add the Isaac ROS APT repo (noble = Ubuntu 24.04; use noble-jetpack on Jetson)

#    deb https://isaac.download.nvidia.com/isaac-ros/release-4 noble main

sudo apt-get install isaac-ros-cli
sudo isaac-ros init docker        # modes: docker | venv | baremetal
isaac-ros activate
sudo apt-get install ros-jazzy-isaac-ros-visual-slam ros-jazzy-isaac-ros-examples ros-jazzy-isaac-ros-realsense
```

Quando o time migrar para o JetPack 7, o lado producer (`docker/isaac_vslam`) passaria
a usar esse fluxo baseado em CLI com pacotes `ros-jazzy-*`; o lado consumer do SDK
(`vision_pose_node`, launches, configs) é agnóstico de distro e não é afetado. Nota:
as release notes apontam problemas de estabilidade do RealSense no JetPack 7 (nvbugs/5561995),
mitigados pelo tutorial de instalação do RealSense.

## Gazebo

O suporte a simulação Gazebo é opt-in. Instala o Gazebo, a ponte `ros_gz` e o
plugin ArduPilot Gazebo. A versão correta do Gazebo e o método de instalação são
selecionados automaticamente por distro ROS (`scripts/lib/config.sh`).

**SDK com Gazebo** (sem AI):

```bash
INSTALL_GAZEBO=true make docker-build
```

**Distro ROS diferente**:

```bash
INSTALL_GAZEBO=true ROS_DISTRO=jazzy make docker-build
```

**Combinado com RealSense + AI + GPU**:

```bash
INSTALL_GAZEBO=true INSTALL_REALSENSE=true TORCH_VARIANT=cu126 make docker-build-full
```

As versões do Gazebo por distro e o método de instalação do `ros_gz` (source vs binário)
estão fixados em [`config.sh`](https://github.com/Black-Bee-Drones/nectar-sdk/blob/main/scripts/lib/config.sh)
e resumidos em [COMPATIBILITY.md](compatibility.md#pinned-versions).

### SITL (voo em simulação)

`INSTALL_SIM` compila a stack SITL do autopilot (`ardupilot`, `px4` ou `all`) dentro
da imagem — pesado, já que os autopilots compilam a partir do source (~1-2 h a frio). Para
voar de fato você também precisa do backend de controle correspondente (`INSTALL_DRONE`):

```bash

# ArduPilot SITL image (MAVROS + direct MAVLink)

INSTALL_SIM=ardupilot INSTALL_DRONE=mavros make docker-build
```

Rode a suíte de voo headless (sem precisar de GPU — usa Mesa software GL):

```bash
docker run --rm --shm-size=1g -e LIBGL_ALWAYS_SOFTWARE=1 nectar-sdk:<distro> \
  bash -lc 'source /opt/ros/$ROS_DISTRO/setup.bash; \
            source /home/ros2_ws/install/local_setup.bash; \
            make verify-sitl FIRMWARE=ardupilot'
```

O PX4 não precisa de mavros (use `INSTALL_SIM=px4`; para uXRCE-DDS acrescente `INSTALL_DRONE=px4-dds`).
Em um host você não precisa de imagem nenhuma — `make sim-install` e depois `make verify-sitl`.

## Estratégia de dependências

O PyTorch **não** está listado nas dependências do `pyproject.toml`. Isso é intencional:

1. `setup.sh pytorch <variant>` instala torch + torchvision a partir do índice
   correto de wheels (CPU ou CUDA) e salva um arquivo de constraints.
2. `setup.sh python ai` instala o extra `[ai]` **com** esse arquivo de constraints
   e `--extra-index-url`, então o pip nunca substitui as wheels CUDA por
   wheels genéricas do PyPI.

### numpy < 2.0

`numpy>=1.26,<2.0` é forçado no `pyproject.toml` para compatibilidade com os binários
`cv_bridge` / `vision_opencv` do ROS 2 em Humble, Jazzy e Kilted.
Veja [vision_opencv#535](https://github.com/ros-perception/vision_opencv/issues/535).

## Instalação do Docker

### Windows

1. Baixe o [instalador do Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/#install-from-the-command-line).
2. Abra a pasta que contém o instalador no Command Prompt (execute como Administrador).
3. Instale o Docker Desktop usando a linha de comando para ter mais controle sobre as opções de instalação:

    ```bash
    start /w "" "Docker Desktop Installer.exe" install -accept-license --installation-dir="D:\Docker\Docker" --wsl-default-data-root="D:\Docker\wsl" --windows-containers-default-data-root="D:\Docker"
    ```

    - Essa configuração permite personalizar o diretório de instalação e o local padrão do WSL (imagens Docker).
    - Personalizar esses caminhos é especialmente útil se o seu drive principal (por exemplo, `C:`) tiver espaço limitado.

4. Para GUI no Docker, instale o [VcXsrv](https://sourceforge.net/projects/vcxsrv/) (XLaunch: desabilite o access control). Para câmeras USB / RealSense, instale o [usbipd-win](https://github.com/dorssel/usbipd-win/releases) — veja [Windows USB](#usb-cameras-and-realsense) neste guia.

### Linux (Ubuntu)

1. Adicione a chave GPG e o repositório oficiais do Docker:

    ```bash
    sudo apt-get update
    sudo apt-get install ca-certificates curl
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc

    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update
    ```

2. Baixe o arquivo `.deb` mais recente do Docker Desktop nas [release notes oficiais](https://docs.docker.com/desktop/release-notes/).
3. Instale o Docker Desktop e o Docker Engine:

    ```bash
    sudo apt-get update
    sudo apt-get install ./docker-desktop-amd64.deb
    sudo apt-get install docker-ce
    ```
