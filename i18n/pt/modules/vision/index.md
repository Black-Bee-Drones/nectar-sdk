# Módulo de Visão

Camada de abstração de câmeras e algoritmos de processamento de imagem para ROS 2. Uma `CameraFactory`
abre qualquer câmera suportada por meio de uma interface comum, um `ImageHandler` a transforma em um
stream orientado a callback, e um conjunto de algoritmos (ArUco, cor, linha, distância, MediaPipe)
roda sobre os frames.

## Resumo rápido

```python
import nectar
from nectar.vision.camera import ImageHandler

nectar.init()
ImageHandler("webcam", image_processing_callback=lambda frame: print(frame.shape)).run()
nectar.spin()
nectar.shutdown()
```

Frame único (sem stream):

```python
from nectar.vision import CameraFactory

cam = CameraFactory.from_source("webcam")
cam.start()
frame = cam.get_frame()
cam.close()
```

Lado a lado com OpenCV / subscribers do ROS:
[Com e sem Nectar](../../get-started/with-without.md)
([with-without.md](../../get-started/with-without/)).

## Documentação

| Página | Escopo |
|------|-------|
| [Cameras](camera/) | `CameraFactory`, `ImageHandler`, `AbstractCam`/`DepthCam`, drivers, configs, T265, calibração, geometria de imagem |
| [Algorithms](algorithms/) | ArUco, cor, linha, regressão de distância, mão/face MediaPipe, optical flow |
| [ROS 2 nodes](nodes/) | Nós de ArUco, detecção de linha, calibração de cor e publisher de câmera |

## Conceitos

Duas camadas sustentam o módulo:

- **Câmeras.** `CameraFactory.from_source(key)` devolve um driver que implementa `AbstractCam`
  (`start` / `get_frame` / `close`); câmeras com profundidade acrescentam `DepthCam` (`get_depth_frame` /
  `get_distance`). Veja [Cameras](camera/).
- **Streaming + algoritmos.** `ImageHandler` envolve qualquer câmera em um nó ROS 2 acionado por
  timer e chama seu callback de processamento em cada frame. O callback roda um [algoritmo](algorithms/)
  (ArUco, cor, linha, distância, MediaPipe), ou você pode rodar os
  [nós ROS 2](nodes/) prontos.

Ambos compartilham o executor de runtime do SDK (veja [`nectar.runtime`](https://github.com/Black-Bee-Drones/nectar-sdk/blob/main/nectar/nectar/runtime.py)), então o vision se compõe
com o control e a AI em uma única missão.

## Exemplos

Veja `examples/vision/` para scripts completos e funcionais:

| Exemplo | Descrição |
|---------|-------------|
| `camera_example.py` | Captura básica de câmera e configuração |
| `depth_example.py` | Visualização de câmera de profundidade e distância (RealSense D4xx, OAK-D) |
| `t265_example.py` | Fisheye T265 + profundidade estéreo + overlay de pose + medição por clique |
| `optical_flow_example.py` | Visualização de optical flow esparso/denso |
| `collect_photos.py` | Salva frames em intervalos para criação de dataset |

## Estendendo o módulo

- Drivers de câmera: adicione em `camera/drivers/`, herde de `AbstractCam` ou `DepthCam`, acrescente
  uma dataclass de config em `camera/config.py`, e registre-a com `CameraFactory.register()` em
  `camera/factory.py`.
- Algoritmos: adicione em `algorithms/<category>/`.
- Nós ROS 2: adicione em `nodes/`.
- Exporte os símbolos públicos em `__init__.py`.
