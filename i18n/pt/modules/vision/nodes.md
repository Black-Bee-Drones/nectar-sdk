# Visão — Nós ROS 2

Nós prontos para rodar que envolvem os [algoritmos](../algorithms/) e as [câmeras](../camera/)
de visão como executáveis ROS 2 (`ros2 run nectar <node>.py`). Cada um controla um
`ImageHandler` internamente e publica em mensagens `nectar_interfaces`.

Flags de câmera e preview são compartilhadas. Flags do algoritmo ficam no nó. Launch files passam
`arguments=['--source', 'webcam']` (não um dump YAML de cada driver).

Veja também: [Cameras](../camera/) · [Algorithms](../algorithms/) ·
[Vision overview](../).

## Flags compartilhadas

Todo nó de visão aceita as mesmas flags de câmera e stream. Os campos de câmera vêm das
dataclasses `CameraConfig`; flags omitidas mantêm o default daquele driver.

```bash
ros2 run nectar aruco_node.py --source webcam --device-index 1 --no-show
ros2 run nectar aruco_node.py --source ros --topic /camera/color/image_raw/compressed --compressed
ros2 run nectar aruco_node.py --source /image_raw --publish
```

| Flag | Mapeia para | Notas |
|------|-------------|-------|
| `--source` | chave de `CameraFactory`, tópico ROS (`/…`) ou caminho de arquivo | Padrão `webcam` |
| `--device-index` | `OpenCVConfig.device_index` | Webcam / opencv |
| `--width` `--height` `--fps` | campos OpenCV / IMX219 | Default da dataclass se omitido |
| `--topic` `--compressed` | `ROSConfig` | `--source ros`, ou um tópico como `--source` |
| `--path` | `FileImageConfig.path` | `--source file` |
| `--color-width` `--color-height` | `RealSenseConfig.color_res` | Só RealSense |
| `--show` / `--no-show` | `ImageHandler.show_result` | Nós interativos ligam por padrão; o publisher desliga |
| `--publish` `--publish-topic` `--jpeg-quality` | JPEG opcional do frame processado | Não usado por `camera_publisher_node` (ele sempre publica o frame) |

`ros2 run nectar <node>.py --help` lista os grupos por driver. `--ros-args` restantes ainda chegam
ao `rclpy`. A detecção de linha ainda expõe `line_colors` / `method` / `spaces` / `roi` como
parâmetros ROS para `ros2 param set` ao vivo.

## Arquitetura

```mermaid
classDiagram
    class ArucoNode {
        -aruco Aruco
        -img_handler ImageHandler
        -pose_estime_pub Publisher
        +process_image(img)
        +cleanup()
    }

    class LineDetectionNode {
        -line_detectors Dict~str,LineDetector~
        -estimation_methods Dict~str,ILineEstimationMethod~
        -image_handler ImageHandler
        +process_image(img)
        +initialize_color_detector(color, color_space)
        +run()
        +cleanup()
    }

    class ColorCalibrationNode {
        -color_detector ColorDetector
        -img_handler ImageHandler
        -_process(img)
    }

    class CameraPublisherNode {
        -camera AbstractCam
        -image_handler ImageHandler
        -publisher Publisher
        +cleanup()
    }

    ArucoNode o-- Aruco
    ArucoNode o-- ImageHandler
    LineDetectionNode o-- LineDetector
    LineDetectionNode o-- ImageHandler
    ColorCalibrationNode o-- ColorDetector
    ColorCalibrationNode o-- ImageHandler
    CameraPublisherNode o-- ImageHandler
```

## Nó de detecção ArUco

```bash
ros2 run nectar aruco_node.py --source webcam --marker-dict 5 --tag-size 0.05
```

| Flag | Tipo | Padrão | Descrição |
|------|------|--------|-----------|
| `--marker-dict` | int | 5 | Dicionário ArUco (4, 5, 6, 7) |
| `--tag-size` | float | 0.2 | Tamanho do marcador em metros |

Publica `/aruco/pose_estimate` (`nectar_interfaces/ArucoTransforms`). `--publish` adiciona a
imagem anotada em `--publish-topic` (padrão `/aruco/image/compressed`).

## Nó de detecção de linha

```bash
ros2 run nectar line_detection_node.py --source webcam \
    --line-colors blue,red --method HoughLinesP --spaces hsv,lab
```

| Flag | Tipo | Padrão | Descrição |
|------|------|--------|-----------|
| `--line-colors` | string | teste | Nomes de cor separados por vírgula, do JSON de calibração (por exemplo, `blue,red`). O padrão `teste` é um placeholder — defina nomes que existam no seu arquivo. |
| `--method` | string | HoughLinesP | Método de estimação |
| `--spaces` | string | hsv | Espaços de cor separados por vírgula |
| `--roi` | string | 480,280 | Janela de detecção como `width,height` |
| `--visualization-name` | string | Line Detection | Título da janela |
| `--calibration-file` | string | (vazio) | JSON de calibração. Vazio usa `~/.config/nectar/color_calibration.json`. |

Métodos: `HoughLinesP`, `RotatedRect`, `FitEllipse`, `RansacLine`, `AdaptiveHoughLinesP`. Por
cor, publica `/line_state/{color}` (`nectar_interfaces/LineInfo`) e `/line_detect/{color}`
(`std_msgs/Bool`).

## Nó de calibração de cor

```bash
ros2 run nectar color_calibration_node.py --source webcam --color-space hsv --flood-tolerance 15
```

Calibração interativa HSV/LAB em uma única janela: clique com o botão esquerdo em uma região
colorida para computar automaticamente os thresholds via flood fill, depois ajuste fino com as
seis trackbars de canal. A visão empilhada mostra `original | mask | result`. Exige uma GUI do
OpenCV.

| Flag | Tipo | Padrão | Descrição |
|------|------|--------|-----------|
| `--color-space` | string | hsv | Espaço de cor inicial (`hsv` ou `lab`) |
| `--flood-tolerance` | int | 15 | Tolerância inicial de flood-fill para a amostragem por clique |
| `--calibration-file` | string | (vazio) | JSON de calibração. Vazio usa `~/.config/nectar/color_calibration.json`. |

| Tecla | Ação |
|-------|------|
| clique esquerdo | Amostra a região clicada (flood fill) |
| `c` | Alterna HSV / LAB |
| `s` | Salva (pede um nome de cor) |
| `l` | Carrega uma cor nomeada |
| `z` | Desfaz a última amostra |
| `r` | Reseta |
| `q` | Sai |

As cores salvas são gravadas em `~/.config/nectar/color_calibration.json` (ou `--calibration-file`) e
carregadas via `ColorDetector(mode="preset", color=<name>)` e pelo nó de detecção de linha.

## Nó publisher de câmera

Publica qualquer fonte de `CameraFactory` como um tópico de imagem ROS 2. Este nó sempre publica o
frame; use `--no-compression` para `sensor_msgs/Image` cru. Preview desligado até `--show`.

```bash
ros2 run nectar camera_publisher_node.py --source webcam --device-index 0 \
    --width 1280 --height 720 --fps 30 --jpeg-quality 80
```

| Flag | Tipo | Padrão | Descrição |
|------|------|--------|-----------|
| `--no-compression` | flag | (compressão ligada) | Publica `sensor_msgs/Image` em vez de JPEG |
| `--jpeg-quality` | int | 80 | Qualidade do JPEG (0-100) |
| `--log-fps-interval` | float | 5.0 | Período do log de FPS; `0` desliga |
| `--poll-interval` | float | -1 | Período de poll; `-1` = auto |
| `--frame-timeout` | float | -1 | Espera por frame novo; `-1` = auto |

Publica `image_raw/compressed` (`sensor_msgs/CompressedImage`) ou `image_raw`
(`sensor_msgs/Image`).
