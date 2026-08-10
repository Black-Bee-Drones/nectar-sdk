# Começar

Nectar SDK oferece uma interface Python para **controle de voo**, **visão computacional** e
**IA**, todas compartilhando um único runtime ROS 2. Escolha um tópico abaixo, siga os
passos para sua plataforma, câmera ou modelo, e use os links quando quiser a referência
completa.

## O modelo mental

Todo módulo segue a mesma forma, então ao conhecer um você conhece todos:

```python
import nectar

nectar.init()                      # start the shared runtime (one background executor)
obj = SomeFactory.create(...)      # build a drone / camera / detector by key + config
obj.do_something(...)              # call the same API regardless of backend
nectar.shutdown()                  # stop the runtime
```

- **Factories** montam o backend concreto a partir de uma chave em string e de um config
  tipado (`DroneFactory`, `CameraFactory`, `Detector`) — troque a chave, mantenha o código.
- **Um runtime** (`nectar.init` / `nectar.spin` / `nectar.shutdown`) possui um executor
  compartilhado, para que controle, visão e IA se componham em uma única missão. Veja
  [Arquitetura](../concepts/architecture.md).

## Pré-requisitos

Um workspace Nectar SDK já configurado. Se ainda não tiver, faça a
[Instalação](../setup/index.md) primeiro (instala só os módulos que você escolher). Cada
tópico abaixo lista a instalação do módulo de que precisa.

## Escolha seu caminho

<div class="grid cards" markdown>

-   **Voar um drone**

    Escolha uma plataforma e um transporte, inicie o driver ou um simulador, configure uma
    fonte de pose e voe um quadrado — as mesmas chamadas em ArduPilot, PX4, Crazyflie ou Bebop.

    [Voar um drone](control.md)

-   **Ver com uma câmera**

    Abra qualquer câmera por meio de uma factory, transmita frames por um `ImageHandler` e rode
    um algoritmo (ArUco, cor, linha, distância, MediaPipe).

    [Ver com uma câmera](vision.md)

-   **Detectar, segmentar e classificar**

    Carregue um modelo de detecção, segmentação ou classificação com Ultralytics YOLO,
    HuggingFace DETR ou RF-DETR por meio de um `Detector` / `Segmentor` / `Classifier`, e
    rode em um frame.

    [Detectar, segmentar e classificar](ai.md)

-   **Com e sem Nectar**

    Os mesmos comportamentos de missão com o SDK e com scripts completos da stack
    subjacente.

    [Com e sem Nectar](with-without.md)

</div>

Cada página é independente e compartilha o runtime, então você pode combinar controle,
visão e IA em uma única missão.
