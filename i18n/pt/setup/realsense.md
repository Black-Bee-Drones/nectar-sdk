# RealSense e navegação indoor

Câmeras Intel RealSense de profundidade e tracking alimentam tanto os recursos de
profundidade da visão quanto o voo sem GPS (indoor). Esta página instala librealsense e
realsense-ros; o pipeline VSLAM indoor se apoia neles.

## Instalar

Compila librealsense a partir do source e instala realsense-ros. O menu interativo oferece
passos customizados, auto-detecção de CUDA e verificação.

```bash
make realsense
```

As versões de `realsense-ros` / `librealsense` por distro são selecionadas automaticamente
em `scripts/lib/config.sh`; veja [COMPATIBILITY](compatibility.md#pinned-versions).

!!! tip "CUDA"
    Em GPUs NVIDIA o librealsense compila com CUDA automaticamente (detectado via `nvcc`).
    Desative com `REALSENSE_CUDA=false make realsense`.

!!! note "Câmera de tracking T265 (descontinuada)"
    A T265 precisa das últimas versões suportadas de **librealsense** / **realsense-ros**,
    só no Humble:

    ```bash
    LIBREALSENSE_VERSION=v2.53.1 REALSENSE_ROS_TAG=4.51.1 make realsense
    ```

    Esse build source também fornece o **pyrealsense2** correspondente para o modo direto
    da T265. O extra pip `nectar-sdk[realsense]` (PyPI pyrealsense2 ≥2.55) é só para modo
    direto D4xx — veja
    [Cameras](../modules/vision/camera.md#t265-tracking-camera).

## Navegação indoor

A navegação indoor (sem GPS) está no módulo de Localização do SDK: um RealSense alimenta o
Isaac ROS Visual SLAM em um Jetson, que envia pose ao FCU via MAVROS ou MAVLink direto.

| Doc | Escopo |
|-----|--------|
| [Localization](../modules/control/localization/index.md) | Arquitetura, Run, FCU, origem EKF, SOP indoor |
| [Concepts](../modules/control/localization/concepts.md) | Teoria SLAM / VIO / V-SLAM |
| [Legacy T265](../modules/control/localization/legacy.md) | T265 + `vision_to_mavros` |

O producer Isaac roda no próprio container (`make isaac-run`). Veja o
[guia Docker](docker.md) para o container.
