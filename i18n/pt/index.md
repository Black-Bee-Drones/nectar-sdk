---
hide:
  - toc
---

# Nectar SDK

<div class="nectar-meta" markdown>

- [:simple-github: GitHub](https://github.com/Black-Bee-Drones/nectar-sdk)
- [:simple-apache: Apache 2.0](https://github.com/Black-Bee-Drones/nectar-sdk/blob/main/LICENSE){ .cb style="--b:#D22128" }
- [:octicons-tag-16: Última release](https://github.com/Black-Bee-Drones/nectar-sdk/releases/latest)
- [:simple-ros: ROS 2 · Humble · Jazzy · Kilted](setup/compatibility.md)

</div>

Nectar SDK é um kit de desenvolvimento ROS 2 para drones autônomos. Ele unifica
controle de voo, visão computacional e IA por meio de um conjunto consistente de
interfaces, para que uma missão escrita uma vez rode em veículos, sensores e
simuladores diferentes com pouca mudança.

[Começar](get-started/index.md){ .md-button .md-button--primary }
[Com / sem](get-started/with-without.md){ .md-button }
[Arquitetura](concepts/architecture.md){ .md-button }

## Veja em ação

Missões autônomas que nossa equipe voou com o SDK, em competição e em campo. Clique
em qualquer clipe para ampliar.

<div class="nectar-carousel nectar-carousel--marquee">
  <button class="nectar-carousel__btn nectar-carousel__btn--prev" aria-label="Anterior">&lsaquo;</button>
  <div class="nectar-carousel__track">
    <div class="nectar-tile nectar-tile--portrait" data-src="assets/media/comp-imav25.mp4" data-poster="assets/media/comp-imav25.jpg">
      <div class="nectar-tile__media">
        <video class="nectar-autoplay" muted loop playsinline preload="none" poster="assets/media/comp-imav25.jpg">
          <source src="assets/media/comp-imav25.mp4" type="video/mp4">
        </video>
      </div>
      <div class="nectar-cap"><a href="https://github.com/Black-Bee-Drones/imav-2025">IMAV 2025, indoor</a><span class="cap-sub">Entrada em portão, obstáculos, plataforma de fumaça móvel · 3º lugar</span></div>
    </div>
    <div class="nectar-tile" data-src="assets/media/comp-hook.mp4" data-poster="assets/media/comp-hook.jpg">
      <div class="nectar-tile__media">
        <video class="nectar-autoplay" muted loop playsinline preload="none" poster="assets/media/comp-hook.jpg">
          <source src="assets/media/comp-hook.mp4" type="video/mp4">
        </video>
      </div>
      <div class="nectar-cap"><a href="https://github.com/Black-Bee-Drones/SAE-Eletroquad">SAE Eletroquad 2026</a><span class="cap-sub">Hook and place, execução anotada</span></div>
    </div>
    <div class="nectar-tile" data-src="assets/media/comp-imav23.mp4" data-poster="assets/media/comp-imav23.jpg">
      <div class="nectar-tile__media">
        <video class="nectar-autoplay" muted loop playsinline preload="none" poster="assets/media/comp-imav23.jpg">
          <source src="assets/media/comp-imav23.mp4" type="video/mp4">
        </video>
      </div>
      <div class="nectar-cap"><a href="https://github.com/Black-Bee-Drones/imav2023-indoor">IMAV 2023, indoor</a><span class="cap-sub">Seguimento de linha e pouso em ArUco · 3º lugar</span></div>
    </div>
    <div class="nectar-tile nectar-tile--portrait" data-src="assets/media/comp-cbr.mp4" data-poster="assets/media/comp-cbr.jpg">
      <div class="nectar-tile__media">
        <video class="nectar-autoplay" muted loop playsinline preload="none" poster="assets/media/comp-cbr.jpg">
          <source src="assets/media/comp-cbr.mp4" type="video/mp4">
        </video>
      </div>
      <div class="nectar-cap"><a href="https://github.com/Black-Bee-Drones/cbr-2025">CBR 2025</a><span class="cap-sub">Fase 1: pouso de precisão em uma base</span></div>
    </div>
    <div class="nectar-tile" data-src="assets/media/comp-slalom.mp4" data-poster="assets/media/comp-slalom.jpg">
      <div class="nectar-tile__media">
        <video class="nectar-autoplay" muted loop playsinline preload="none" poster="assets/media/comp-slalom.jpg">
          <source src="assets/media/comp-slalom.mp4" type="video/mp4">
        </video>
      </div>
      <div class="nectar-cap"><a href="https://github.com/Black-Bee-Drones/SAE-Eletroquad">SAE Eletroquad 2025</a><span class="cap-sub">Missão de slalom</span></div>
    </div>
  </div>
  <button class="nectar-carousel__btn nectar-carousel__btn--next" aria-label="Próximo">&rsaquo;</button>
</div>

## O que você pode construir

<div class="nectar-features">
  <div class="nectar-feature">
    <div class="nectar-feature__media" data-src="assets/media/feat-control.mp4" data-poster="assets/media/feat-control.jpg">
      <video class="nectar-autoplay" muted loop playsinline preload="none" poster="assets/media/feat-control.jpg">
        <source src="assets/media/feat-control.mp4" type="video/mp4">
      </video>
    </div>
    <div class="nectar-feature__body">
      <h3>Voar qualquer veículo</h3>
      <p>ArduPilot e PX4 via MAVROS, MAVLink direto ou uXRCE-DDS nativo, além de Bebop e Crazyflie, por meio de uma interface de voo. Navegação, waypoints GPS, retorno ao ponto de lançamento (RTL), PID e desvio de obstáculos.</p>
      <a href="get-started/control/">Voar um drone</a>
    </div>
  </div>
  <div class="nectar-feature">
    <div class="nectar-feature__media" data-src="assets/media/feat-vision.mp4" data-poster="assets/media/feat-vision.jpg">
      <video class="nectar-autoplay" muted loop playsinline preload="none" poster="assets/media/feat-vision.jpg">
        <source src="assets/media/feat-vision.mp4" type="video/mp4">
      </video>
    </div>
    <div class="nectar-feature__body">
      <h3>Ver com qualquer câmera</h3>
      <p>USB, RealSense, OAK-D, Pi Camera ou um tópico ROS por meio de uma camera factory e um image handler compartilhado. ArUco, cor, linha, estimativa de distância, optical flow e MediaPipe.</p>
      <a href="get-started/vision/">Ver com uma câmera</a>
    </div>
  </div>
  <div class="nectar-feature">
    <div class="nectar-feature__media" data-src="assets/media/feat-ai.mp4" data-poster="assets/media/feat-ai.jpg">
      <video class="nectar-autoplay" muted loop playsinline preload="none" poster="assets/media/feat-ai.jpg">
        <source src="assets/media/feat-ai.mp4" type="video/mp4">
      </video>
    </div>
    <div class="nectar-feature__body">
      <h3>Detectar, segmentar e classificar</h3>
      <p>Detecção de objetos, segmentação de instâncias e classificação com Ultralytics YOLO, HuggingFace DETR e RF-DETR por meio de uma interface preparada para novos modelos e tarefas, com treinamento e avaliação.</p>
      <a href="get-started/ai/">Detectar, segmentar e classificar</a>
    </div>
  </div>
  <div class="nectar-feature">
    <div class="nectar-feature__media" data-src="assets/media/feat-localize.mp4" data-poster="assets/media/feat-localize.jpg">
      <video class="nectar-autoplay" muted loop playsinline preload="none" poster="assets/media/feat-localize.jpg">
        <source src="assets/media/feat-localize.mp4" type="video/mp4">
      </video>
    </div>
    <div class="nectar-feature__body">
      <h3>Voar indoor sem GPS</h3>
      <p>Uma ponte de rangefinder no computador de bordo e um RealSense com pipeline Isaac VSLAM alimentam o controlador de voo, para o mesmo código de navegação e a mesma precisão indoor e outdoor.</p>
      <a href="modules/control/localization/">Localização</a>
    </div>
  </div>
  <div class="nectar-feature">
    <div class="nectar-feature__media" data-src="assets/media/feat-interface.mp4" data-poster="assets/media/feat-interface.jpg">
      <video class="nectar-autoplay" muted loop playsinline preload="none" poster="assets/media/feat-interface.jpg">
        <source src="assets/media/feat-interface.mp4" type="video/mp4">
      </video>
    </div>
    <div class="nectar-feature__body">
      <h3>Operar sem código</h3>
      <p>Um app desktop para armar, decolar, voar, transmitir câmeras com filtros ao vivo, ajustar PID com gráficos e inspecionar tópicos, serviços e parâmetros ROS 2.</p>
      <a href="modules/interface/">Interface</a>
    </div>
  </div>
  <div class="nectar-feature">
    <div class="nectar-feature__media" data-src="assets/media/feat-sim.mp4" data-poster="assets/media/feat-sim.jpg">
      <video class="nectar-autoplay" muted loop playsinline preload="none" poster="assets/media/feat-sim.jpg">
        <source src="assets/media/feat-sim.mp4" type="video/mp4">
      </video>
    </div>
    <div class="nectar-feature__body">
      <h3>Testar em simulação</h3>
      <p>ArduPilot ou PX4 SITL com Gazebo, indoor e outdoor, rodando as mesmas missões que você voa no hardware.</p>
      <a href="setup/simulation/">Simulação</a>
    </div>
  </div>
</div>

## Para quem é

Nectar SDK serve laboratórios acadêmicos, grupos de pesquisa, equipes de competição e
prototipagem industrial: quem constrói voo autônomo e quer controle, visão e IA sob um
conjunto consistente de interfaces. É um bom encaixe quando você quer:

- Rodar uma missão em veículos e transportes diferentes, em simulação ou no hardware.
- Combinar controle de voo, visão computacional e IA em um único código com APIs tipadas e consistentes.
- Voar indoor e outdoor com o mesmo código de navegação e a mesma precisão.
- Adicionar um novo drone, câmera ou modelo seguindo um padrão familiar, sem fork do núcleo.

Não é um controlador de voo nem um substituto do ArduPilot ou do PX4. Roda no computador
de bordo e os aciona via ROS 2.

## Sobre

Nectar SDK é desenvolvido pela [Black Bee Drones](https://github.com/Black-Bee-Drones), a
primeira equipe acadêmica de drones autônomos da América Latina, fundada em 2014 na
Universidade Federal de Itajubá (UNIFEI). A equipe constrói aeronaves autônomas para
missões que dependem de visão computacional e inteligência artificial, e compete em nível
nacional e internacional, incluindo
[IMAV](https://www.imavs.org/) (3º lugar indoor em 2023 e 2025), a
[CBR RoboCup Flying Robots League](https://cbr.robocup.org.br/) e
[SAE Eletroquad](https://saebrasil.org.br/programas-estudantis/eletroquad/).

Começou em 2023 como forma de parar de reescrever o mesmo código de câmera, PID e detecção
para cada missão de competição, e cresceu até um pacote ROS 2 com interfaces consistentes
em controle de voo, visão computacional e IA. É open source sob Apache 2.0 para que outras
equipes e laboratórios construam sistemas autônomos com mais rapidez.

### Construído sobre

<div class="nectar-ack__group" markdown>

<p class="nectar-ack__title">Robótica e voo</p>

- [:simple-ros: ROS 2](https://docs.ros.org/)
- <a class="b-logo" href="https://ardupilot.org/" aria-label="ArduPilot"><img class="nectar-logo off-glb" src="assets/logos/ardupilot.svg" alt="ArduPilot"></a>
- <a class="b-logo" href="https://px4.io/"><img class="nectar-logo off-glb" src="assets/logos/px4.svg" alt="" onerror="this.remove()">PX4</a>
- <a class="b-logo" href="https://mavlink.io/"><img class="nectar-logo off-glb" src="assets/logos/mavlink.png" alt="" onerror="this.remove()">MAVLink</a>
- <a class="b-logo" href="https://www.parrot.com/"><img class="nectar-logo off-glb" src="assets/logos/parrot.svg" alt="Parrot">Bebop</a>
- <a class="b-logo" href="https://www.bitcraze.io/"><img class="nectar-logo off-glb" src="assets/logos/bitcraze.png" alt="" onerror="this.remove()">Bitcraze Crazyflie</a>

</div>

<div class="nectar-ack__group" markdown>

<p class="nectar-ack__title">Percepção e IA</p>

- [:simple-opencv: OpenCV](https://opencv.org/){ .cb style="--b:#5C3EE8" }
- [:simple-pytorch: PyTorch](https://pytorch.org/){ .cb style="--b:#EE4C2C" }
- <a class="b-logo" href="https://docs.ultralytics.com/" aria-label="Ultralytics"><img class="nectar-logo off-glb" src="assets/logos/ultralytics.svg" alt="Ultralytics"></a>
- [:simple-huggingface: HuggingFace](https://huggingface.co/){ .cb style="--b:#FFD21E" }
- [:simple-roboflow: Roboflow](https://roboflow.com/){ .cb style="--b:#6706CE" }
- [:simple-mediapipe: MediaPipe](https://ai.google.dev/edge/mediapipe/solutions){ .cb style="--b:#0097A7" }

</div>

<div class="nectar-ack__group" markdown>

<p class="nectar-ack__title">Localização e sensores</p>

- [:simple-nvidia: NVIDIA Isaac ROS](https://nvidia-isaac-ros.github.io/){ .cb style="--b:#76B900" }
- [:simple-intel: Intel RealSense](https://github.com/realsenseai/librealsense){ .cb style="--b:#0071C5" }
- <a class="b-logo" href="https://www.luxonis.com/"><img class="nectar-logo off-glb" src="assets/logos/luxonis.svg" alt="" onerror="this.remove()">Luxonis</a>

</div>

### Roda em

<div class="nectar-supported" markdown>

- [:fontawesome-brands-ubuntu: Ubuntu](https://ubuntu.com/){ .cb style="--b:#E95420" }
- [:simple-nvidia: Jetson](https://developer.nvidia.com/embedded-computing){ .cb style="--b:#76B900" }
- [:fontawesome-brands-raspberry-pi: Raspberry Pi](https://www.raspberrypi.com/){ .cb style="--b:#A22846" }
- [:fontawesome-brands-windows: Windows (WSL2)](setup/compatibility.md){ .cb style="--b:#0078D4" }

</div>
