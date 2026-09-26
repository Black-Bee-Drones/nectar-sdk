# Exemplos do Módulo Vision

Exemplos funcionais dos drivers de câmera e do processamento de imagem do módulo Vision.

| Exemplo | Script | O que faz |
|---------|--------|--------------|
| **Captura de Câmera** | `camera_example.py` | Suporte a múltiplas câmeras com opções de configuração |
| **Visualização de Profundidade** | `depth_example.py` | Medição de profundidade com câmera RGB-D e exibição de colormap |
| **Tracking do T265** | `t265_example.py` | Pose/odometria do RealSense T265 (SDK direto ou ROS) |
| **Optical Flow** | `optical_flow_example.py` | Visualização de optical flow esparso/denso |
| **Coleta de Fotos** | `collect_photos.py` | Salva frames em intervalos para criação de dataset |

Todos os scripts usam flags de `argparse` (não `--ros-args -p`). Rode com
`python3 <script>.py [flags]`. Alguns scripts também são instalados como executáveis ROS 2
(`ros2 run nectar <script>.py -- [flags]`): `camera_example.py`, `depth_example.py`,
`t265_example.py`, `collect_photos.py`. Use `python3` para `optical_flow_example.py` (não
instalado como executável).

## Exemplo de Câmera

Captura de câmera usando `ImageHandler` com backends configuráveis.

### Uso

Rode com a webcam padrão, ou passe `--source` e as flags de câmera (`--help`); adicione `--no-show` para rodar sem interface.

```bash
python3 camera_example.py
python3 camera_example.py --source realsense
python3 camera_example.py --source webcam --device-index 1 --width 1280 --height 720
```

### Argumentos

Flags compartilhadas de câmera/stream (`--source`, `--device-index`, `--width`, `--show` / `--no-show`, …). Veja a tabela de flags compartilhadas em [nós de visão](../vision/nodes.md).

### Tipos de Câmera Suportados {#tipos-de-camera-suportados}

| `--source` | Driver | Notas |
|------------|--------|-------|
| `webcam` / `opencv` | `OpenCVCam` | `--device-index`, `--width`, `--height`, `--fps` |
| `realsense` | `RealsenseCam` | `--color-width`, `--color-height`, `--enable-depth` |
| `ros_depth` | `ROSDepthCam` | `--topic`, `--depth-topic` |
| `oakd` | `OakdCam` | `--cam-num`, `--enable-depth` (padrão off) |
| `c920` | `C920Cam` | `--profile` |
| `imx219` | `IMX219Cam` | `--sensor-id`, `--width` padrão 1920 |
| `ros` | `ROSCam` | `--topic`, `--compressed` |
| `/tópico` ou caminho de arquivo | auto | Mesmas regras de `CameraFactory.from_source` |

---

## Exemplo de Profundidade

Demonstra o uso de câmera de profundidade com medição de distância interativa.

### Uso

| Fonte | Comando |
|--------|---------|
| RealSense (SDK pyrealsense2 direto) | `python3 depth_example.py --source realsense` |
| RealSense via tópicos ROS | `python3 depth_example.py --source ros_depth` |
| OAK-D | `python3 depth_example.py --source oakd --enable-depth` |

### Funcionalidades

- **Exibição RGB**: imagem de cor com mira no pixel selecionado
- **Colormap de Profundidade**: visualização com colormap Plasma (faixa de 0,1 m - 3,0 m)
- **Seleção Interativa**: clique na imagem de cor para selecionar o ponto de medição
- **Exibição de Distância**: distância em tempo real, em metros, no pixel selecionado

### Controles de Teclado

| Tecla | Ação |
|-----|--------|
| `q` | Encerra a aplicação |
| Clique do mouse | Seleciona o pixel para medição de distância |

---

## Tracking do T265

Pose/odometria da câmera de tracking RealSense T265, pelo SDK direto ou por tópicos ROS.

Roda em modo SDK direto por padrão; veja os argumentos abaixo para o modo ROS e a opção de
profundidade.

```bash
python3 t265_example.py
python3 t265_example.py --use-ros-topics
```

| Flag | Padrão | Descrição |
|------|---------|-------------|
| `--source` | `t265` | Deve permanecer `t265` |
| `--use-ros-topics` / `--no-use-ros-topics` | off | Inscreve nos tópicos fisheye/pose em vez do SDK |
| `--enable-depth` / `--no-enable-depth` | on | Caminho de profundidade estéreo |

---

## Optical Flow

Optical flow esparso (Lucas-Kanade) ou denso (Farneback). Com `--focal`/`--altitude` também
decodifica a taxa angular (rad/s) e a velocidade horizontal (m/s), como o pipeline
OPTICAL_FLOW do ArduPilot.

| Caso | Comando |
|------|---------|
| Webcam, Farneback denso (padrão) | `python3 optical_flow_example.py` |
| RealSense, Lucas-Kanade esparso | `python3 optical_flow_example.py --source realsense --method lucas_kanade` |
| Qualquer tópico de imagem ROS | `python3 optical_flow_example.py --source /camera/image_raw` |
| Decodifica taxa angular + velocidade horizontal | `python3 optical_flow_example.py --focal 500 --altitude 1.5` |
| Sem interface (headless) | `python3 optical_flow_example.py --no-show` |

| Flag | Padrão | Descrição |
|------|---------|-------------|
| `--source` | `webcam` | Chave da câmera (`webcam`, `realsense`, `oakd`, `c920`, `imx219`), um tópico ROS (`/...`), ou o caminho de um arquivo de imagem/vídeo |
| `--method` | `farneback` | `farneback` (denso) ou `lucas_kanade` (esparso) |
| `--focal` | `0` | Distância focal da câmera em px (`0` pula a decodificação de rad/s e m/s) |
| `--altitude` | `0` | Altura da câmera em m (`0` pula a decodificação de m/s) |
| `--no-show` | off | Desabilita a janela de preview |

---

## Coleta de Fotos

Captura frames em um intervalo configurável e os salva em uma estrutura de diretórios
organizada. Útil para construir datasets de treinamento — voe o drone via rádio (RC) ou pela
interface do Nectar enquanto este nó grava os frames.

### Uso

| Caso | Comando |
|------|---------|
| Padrão (webcam, 1 foto/s, pasta com timestamp) | `python3 collect_photos.py` |
| Diretório de saída e intervalo personalizados (2 fotos/s) | `python3 collect_photos.py --output-dir hook_photos --capture-interval 0.5` |
| Execução nomeada para uma sessão de voo | `python3 collect_photos.py --output-dir hook_photos --run-name flight_01_low_alt` |
| RealSense com janela de preview | `python3 collect_photos.py --source realsense --show` |
| Webcam em alta resolução, PNG, máximo de 500 fotos | `python3 collect_photos.py --width 1920 --height 1080 --image-format png --max-photos 500` |

### Argumentos

| Flag | Padrão | Descrição |
|------|---------|-------------|
| `--source` | `webcam` | Fonte da câmera (flags compartilhadas; veja `--help`) |
| `--output-dir` | `collected_photos` | Diretório de saída base sob `~/` |
| `--run-name` | *(timestamp)* | Nome da subpasta desta execução |
| `--capture-interval` | `1.0` | Segundos entre capturas |
| `--image-format` | `jpg` | Formato de saída: `jpg` ou `png` |
| `--jpeg-quality` | `90` | Qualidade JPEG de 0 a 100 |
| `--show` | off | Exibe a janela de preview do OpenCV em tempo real |
| `--max-photos` | `0` | Para depois de N fotos (`0` = ilimitado) |
| `--width` / `--height` / `--fps` | padrões do dataclass | Ajustes de captura quando o driver os usa |
| `--publish` / `--publish-topic` / `--publish-scale` | off / `collect_photos/compressed` / `0.5` | Republica os frames capturados como um tópico de imagem comprimida |

### Estrutura de Saída

```
~/hook_photos/
├── flight_01_low_alt/
│   ├── frame_00001.jpg
│   ├── frame_00002.jpg
│   └── ...
├── flight_02_high_alt/
│   ├── frame_00001.jpg
│   └── ...
└── 20260416_143022/          # auto-named when run_name is empty
    └── ...
```

---

## Solução de Problemas

### Câmera Não Encontrada

```
ValueError: Unknown camera source type: xyz
```

Verifique os tipos de câmera registrados:

```python
from nectar.vision.camera import CameraFactory

# Registered: webcam, opencv, realsense, t265, oakd, c920, imx219, ros, ros_depth, file

```

### Erro de Importação do RealSense

```
RuntimeError: pyrealsense2 is not installed
```

Instale o librealsense e o realsense-ros (builda o pyrealsense2 correspondente a partir do
código-fonte):

```bash
make realsense

# T265 (Humble only): LIBREALSENSE_VERSION=v2.53.1 REALSENSE_ROS_TAG=4.51.1 make realsense

```

Ou use o modo de tópico ROS (`--source ros_depth`) com o `realsense2_camera` já em
execução.

### Erro de Importação do OAK-D

```
ModuleNotFoundError: No module named 'depthai'
```

Instale o DepthAI:

```bash
pip install depthai
```

### FPS Baixo / Frames Perdidos

Ajuste as configurações de buffer e threading:

```python
config = OpenCVConfig(
    buffer_size=2,    # Increase if dropping frames
    threaded=True,    # Enable background capture
)
```

### Exibição Não Funciona

```
cv2.error: The function is not implemented
```

Build headless do OpenCV. Opções:

- Instale `opencv-python` em vez de `opencv-python-headless`
- Desabilite a exibição: `show_result=None`

---

## Dependências

| Pacote | Finalidade |
|---------|---------|
| `opencv-python` | Captura de câmera, processamento de imagem |
| `numpy` | Operações com arrays |
| `rclpy` | Cliente Python do ROS 2 |
| `cv_bridge` | Conversão de imagem do ROS |
| `pyrealsense2` | SDK do RealSense (opcional) |
| `depthai` | SDK do OAK-D (opcional) |
