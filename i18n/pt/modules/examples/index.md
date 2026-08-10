# Exemplos

Scripts executáveis que vivem junto ao código em `nectar/nectar/examples/`, agrupados pelo
módulo que exercitam. Cada um é pequeno, autocontido, e feito para ser lido tanto quanto
executado — comece por aqui para ver como os módulos são usados e combinados na prática.

| Grupo | O que cobre |
|-------|----------------|
| [Control](control.md) | Takeoff/land, voo por velocidade e posição, suítes de teste de navegação, REPL interativo, PID, servo/PWM, navegação com desvio de obstáculos |
| [Vision](vision.md) | Drivers de câmera, medição de profundidade, tracking do T265, optical flow, coleta de fotos para dataset |
| [AI](ai.md) | Stream de detecção em tempo real, processamento em lote de imagem/vídeo, detecção + segmentação multi-modelo |
| [Sensors](sensors.md) | Bancada de teste do rangefinder TF-Luna → ponte MAVLink |

## Como rodar

Todo exemplo usa `argparse`. Rode a partir do repositório com:

```bash
python3 nectar/nectar/examples/<group>/<script>.py [flags]
```

Alguns scripts também são instalados como executáveis ROS 2 (veja a página de cada grupo
para saber quais): `ros2 run nectar <script>.py -- [flags]`. Os exemplos de control **não**
são instalados — use somente `python3`.

Os exemplos de control usam `start_driver=False` por padrão — inicie o driver/bridge (ou o
simulador) ao qual a missão se conecta primeiro, em seu próprio terminal. Veja
[Voar um drone](../../get-started/control.md) para o fluxo de simulação e hardware.
