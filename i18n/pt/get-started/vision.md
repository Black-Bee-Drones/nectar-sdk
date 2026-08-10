# Ver com uma câmera

Abra qualquer câmera por meio de uma factory, transforme-a em um stream orientado a callback
com um `ImageHandler` e rode um algoritmo em cada frame. Só a fonte muda entre câmeras; o
pipeline permanece o mesmo.

Escolha a câmera na aba abaixo; a seleção vale para todos os passos. Novo no workspace?
Faça a [Instalação](../setup/index.md) primeiro; câmeras de profundidade também precisam da
[configuração RealSense](../setup/realsense.md).

## 1. Instale o módulo de visão

```bash
make setup            # pick: vision

# or: make python-vision

```

## 2. Abra a câmera

`CameraFactory.from_source(...)` devolve o driver correspondente a qualquer chave que
entenda:

=== "Webcam"

    ```python
    from nectar.vision import CameraFactory, OpenCVConfig
    camera = CameraFactory.from_source("webcam", config=OpenCVConfig(width=1280, height=720))
    ```

=== "RealSense"

    ```python
    from nectar.vision import CameraFactory
    camera = CameraFactory.from_source("realsense")   # depth-capable
    ```

=== "OAK-D"

    ```python
    from nectar.vision import CameraFactory
    camera = CameraFactory.from_source("oakd")        # depth-capable
    ```

=== "ROS topic"

    ```python
    from nectar.vision import CameraFactory
    camera = CameraFactory.from_source("/camera/image_raw")
    ```

Um frame avulso é `camera.get_frame()`; câmeras de profundidade acrescentam
`get_depth_frame()` e `get_distance()`.

As abas acima cobrem as quatro mais comuns. `from_source` aceita todas as chaves abaixo;
veja a [referência de Cameras](../modules/vision/camera.md) para o dataclass
de config de cada driver:

| Chave | Câmera | Notas |
|-------|--------|-------|
| `webcam` / `opencv` | Webcam USB genérica | `OpenCVConfig` (resolução, fps, foco) |
| `realsense` | Intel RealSense D4xx | Cor + profundidade |
| `t265` | Intel RealSense T265 | Fisheye + profundidade estéreo no host + pose 6DOF |
| `oakd` | Luxonis OAK-D | Cor + profundidade |
| `c920` | Logitech C920/C920e | `OpenCVCam` por perfil |
| `imx219` | Raspberry Pi Camera v2 | Jetson (GStreamer) |
| `ros` | Tópico de imagem ROS 2 | Qualquer tópico `sensor_msgs/Image` |
| `ros_depth` | Tópicos ROS 2 cor + profundidade | Com profundidade |
| `file` | Arquivo de imagem estático | Um caminho resolve para isto automaticamente |

Um caminho de arquivo resolve para `file` e uma fonte que começa com `/` para `ros`, então
essas duas não precisam de chave explícita.

## 3. Transmita frames por um ImageHandler

`ImageHandler` envolve a fonte em um nó ROS 2 acionado por timer e chama seu callback a
cada frame:

=== "Webcam"

    ```python
    import nectar
    from nectar.vision.camera import ImageHandler

    nectar.init()
    ImageHandler(
        image_source="webcam",
        image_processing_callback=lambda frame: print(frame.shape),
        show_result="Camera",          # optional preview window
    ).run()
    nectar.spin()                      # Ctrl+C to stop
    nectar.shutdown()
    ```

=== "RealSense"

    ```python
    import nectar
    from nectar.vision.camera import ImageHandler

    nectar.init()
    ImageHandler(
        image_source="realsense",
        image_processing_callback=lambda frame: print(frame.shape),
        show_result="Camera",
    ).run()
    nectar.spin()
    nectar.shutdown()
    ```

=== "OAK-D"

    ```python
    import nectar
    from nectar.vision.camera import ImageHandler

    nectar.init()
    ImageHandler(
        image_source="oakd",
        image_processing_callback=lambda frame: print(frame.shape),
        show_result="Camera",
    ).run()
    nectar.spin()
    nectar.shutdown()
    ```

=== "ROS topic"

    ```python
    import nectar
    from nectar.vision.camera import ImageHandler

    nectar.init()
    ImageHandler(
        image_source="/camera/image_raw",
        image_processing_callback=lambda frame: print(frame.shape),
        show_result="Camera",
    ).run()
    nectar.spin()
    nectar.shutdown()
    ```

## 4. Rode um algoritmo

Construa um algoritmo e chame-o dentro do callback. Todos seguem a mesma forma:

| Algoritmo | Classe | Use para |
|-----------|--------|----------|
| Marcadores ArUco | `Aruco` | Detecção fiducial e pose 6-DoF (`detect`, `pose_estimate`) |
| Cor | `ColorDetector` | Filtro de cor HSV/LAB (calibre e depois `mode="preset"`) |
| Linha | `LineDetector` | Seguimento de linha com Hough / RANSAC / elipse |
| Distância | `DistanceEstimator` | Regressão de tamanho em pixels para distância |
| Mão / face | `HandTracker`, `FaceMeshTracker` | Tracking de landmarks MediaPipe |
| Optical flow | `OpticalFlowEstimator` | Movimento frame a frame |

A estimativa de pose ArUco devolve o id do marcador, a translação e o yaw, e desenha os eixos
no frame. Troque `Aruco` por qualquer classe acima; a fonte continua a escolhida no passo 2:

=== "Webcam"

    ```python
    import nectar
    from nectar.vision import Aruco
    from nectar.vision.camera import ImageHandler

    nectar.init()
    aruco = Aruco(marker_dict=5, tag_size=0.05)
    ImageHandler(
        "webcam",
        image_processing_callback=lambda frame: aruco.pose_estimate(frame, draw=True),
        show_result="ArUco",
    ).run()
    nectar.spin()
    nectar.shutdown()
    ```

=== "RealSense"

    ```python
    import nectar
    from nectar.vision import Aruco
    from nectar.vision.camera import ImageHandler

    nectar.init()
    aruco = Aruco(marker_dict=5, tag_size=0.05)
    ImageHandler(
        "realsense",
        image_processing_callback=lambda frame: aruco.pose_estimate(frame, draw=True),
        show_result="ArUco",
    ).run()
    nectar.spin()
    nectar.shutdown()
    ```

=== "OAK-D"

    ```python
    import nectar
    from nectar.vision import Aruco
    from nectar.vision.camera import ImageHandler

    nectar.init()
    aruco = Aruco(marker_dict=5, tag_size=0.05)
    ImageHandler(
        "oakd",
        image_processing_callback=lambda frame: aruco.pose_estimate(frame, draw=True),
        show_result="ArUco",
    ).run()
    nectar.spin()
    nectar.shutdown()
    ```

=== "ROS topic"

    ```python
    import nectar
    from nectar.vision import Aruco
    from nectar.vision.camera import ImageHandler

    nectar.init()
    aruco = Aruco(marker_dict=5, tag_size=0.05)
    ImageHandler(
        "/camera/image_raw",
        image_processing_callback=lambda frame: aruco.pose_estimate(frame, draw=True),
        show_result="ArUco",
    ).run()
    nectar.spin()
    nectar.shutdown()
    ```

Argumentos exatos do construtor e tipos de retorno estão na
[referência de Vision](../modules/vision/index.md).

!!! success "Resultado esperado"
    A janela de preview mostra o stream ao vivo com o overlay do algoritmo (no ArUco, os
    eixos e o id do marcador).

<figure class="nectar-shot">
  <div class="nectar-shot__media">
    <img src="../assets/media/aruco-ex.jpg" alt="Overlay ArUco com eixos e ids em 15 marcadores em um frame">
  </div>
  <figcaption>Estimativa de pose ArUco detectando 15 marcadores em um único frame, cada um com id e eixos.</figcaption>
</figure>

## Ver também

- [Referência de Vision](../modules/vision/index.md): drivers de câmera, APIs dos
  algoritmos, nós ROS 2 e calibração de câmera/cor.
- [Exemplos de Vision](../modules/examples/vision.md): captura e profundidade.
- [Detectar, segmentar e classificar](ai.md).
