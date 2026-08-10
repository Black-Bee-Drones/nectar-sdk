# Exemplos do Módulo AI

Implementações de referência para detecção de objetos e segmentação baseadas em deep
learning, em cada um dos frameworks suportados.

| Exemplo | Script | O que faz |
|---------|--------|--------------|
| **Stream de Detector** | `detector_example.py` | Detecção de objetos em tempo real a partir de um stream de câmera, com integração ROS 2 |
| **Stream de Classificador** | `classifier_example.py` | Classificação de imagem em tempo real a partir de um stream de câmera, com integração ROS 2 |
| **Batch Detector** | `batch_detector.py` | Processamento offline de diretórios de imagens ou arquivos de vídeo |
| **Sequence Inference** | `sequence_inference.py` | Detecção + segmentação multi-modelo sobre um diretório de imagens ou vídeo, com saída em MP4 anotado |

## Frameworks Suportados

| Framework | Modelos | Exemplo |
|-----------|--------|---------|
| **Ultralytics** | YOLOv8/11/26 detect, seg, cls | `yolov8n.pt`, `yolo26n-cls.pt` |
| **Transformers** | DETR, ViT, … | `facebook/detr-resnet-50`, `google/vit-base-patch16-224` |
| **RF-DETR** | RF-DETR Nano/Small/Medium/Large | `rfdetr-medium` |

---

## Stream de Detecção em Tempo Real

Detecção em stream de câmera usando `Detector` + `ImageHandler`.

### Uso

| Caso | Comando |
|------|---------|
| Padrão (webcam + YOLO, GPU automática) | `python3 detector_example.py` |
| Framework explícito (DETR) | `python3 detector_example.py --model facebook/detr-resnet-50 --framework transformers` |
| YOLO personalizado a partir do HuggingFace | `python3 detector_example.py --model "blackbeedrones/cbr-25-base:yolov11n.pt"` |
| Modelo local, sem interface, republicado como tópico ROS | `python3 detector_example.py --model /path/to/model.pt --no-show --publish --topic /inference/compressed` |

Modelos privados do HuggingFace: passe `--hf-token hf_...` ou defina
`export HF_TOKEN=hf_...`. Selecione o dispositivo de computação com
`--device {auto,cpu,cuda,0,1}` (padrão `auto`).

### Argumentos

| Flag | Padrão | Descrição |
|------|---------|-------------|
| `--model` | `yolov8n.pt` | Caminho do modelo ou repositório HuggingFace |
| `--framework` | "" | Framework explícito: `ultralytics`, `transformers`, `rfdetr` (vazio = detecção automática) |
| `--confidence` | `0.25` | Limiar de confiança de detecção |
| `--camera-source` | `webcam` | Identificador da fonte de câmera |
| `--no-show` | off | Desabilita a janela de detecção (por padrão ela é exibida) |
| `--annotator-type` | `color` | Estilo de anotação: `box`, `round_box`, `color` |
| `--show-labels` / `--show-confidence` / `--show-class` | on | Ativa/desativa os campos do overlay |
| `--device` | `auto` | Dispositivo: `auto`, `cpu`, `cuda`, `0`, `1` |
| `--hf-token` | "" | Token de API do HuggingFace (ou variável de ambiente `HF_TOKEN`) |
| `--publish` / `--topic` / `--jpeg-quality` | off / `/inference/compressed` / `80` | Republica os frames anotados como um tópico de imagem comprimida |

### Estilos de Anotação

| Estilo | Renderização |
|-------|-----------|
| `box` | Contorno de retângulo |
| `round_box` | Retângulo com cantos arredondados |
| `color` | Região preenchida com overlay de alpha |

### Overlay de Estatísticas

O stream exibe estatísticas em tempo real:

- **Framework**: framework de detecção em uso
- **FPS**: frames por segundo (baseado no tempo de inferência)
- **Detections**: contagem de detecções no frame atual
- **Total**: detecções acumuladas

---

## Batch Detector

Script standalone para processamento offline de sequências de imagens ou arquivos de vídeo.

### Uso

**Diretório de imagens ou arquivo de vídeo** (framework detectado automaticamente;
`--input` aceita qualquer um dos dois):

```bash
python3 batch_detector.py \
    --input /path/to/images \
    --output-dir ./results
```

**Framework explícito** (`ultralytics`, `transformers` ou `rfdetr`):

```bash
python3 batch_detector.py \
    --input /path/to/images \
    --model-source facebook/detr-resnet-50 \
    --framework transformers \
    --output-dir ./results
```

**Modelo HuggingFace**

```bash
python3 batch_detector.py \
    --input /path/to/images \
    --model-source "blackbeedrones/cbr-25-base:yolov11n.pt" \
    --output-dir ./results
```

**Opções completas**

```bash
python3 batch_detector.py \
    --input /path/to/video.mp4 \
    --output-dir ./results \
    --model-source yolov8n.pt \
    --framework ultralytics \
    --confidence 0.5 \
    --device cuda \
    --annotator-type round_box \
    --fps 30
```

### Argumentos

| Argumento | Tipo | Padrão | Descrição |
|----------|------|---------|-------------|
| `--input` | string | obrigatório | Diretório de imagens ou arquivo de vídeo |
| `--output-dir` | string | obrigatório | Diretório de saída para os resultados |
| `--model-source` | string | `yolov8n.pt` | Caminho do modelo ou formato HuggingFace |
| `--framework` | string | "" | Framework: `ultralytics`, `transformers`, `rfdetr` (vazio = automático) |
| `--confidence` | float | 0.5 | Limiar de confiança de detecção |
| `--device` | string | auto | Dispositivo de computação |
| `--annotator-type` | string | box | Estilo de anotação |
| `--hide-labels` | flag | false | Esconde os rótulos de detecção |
| `--hide-confidence` | flag | false | Esconde os scores de confiança |
| `--fps` | int | 30 | FPS do vídeo de saída (somente para imagens) |

### Estrutura de Saída

```
output-dir/
├── detection_video.mp4    # Annotated video with all frames
├── frames/                # Individual annotated frames
│   ├── frame_0000.jpg
│   ├── frame_0001.jpg
│   └── ...
└── extracted_frames/      # (video input only) Original frames
    ├── frame_000000.jpg
    └── ...
```

### Processamento de Vídeo

Para entrada em vídeo, o batch detector:

1. Extrai todos os frames para um diretório temporário
2. Processa cada frame com o modelo selecionado
3. Reconstrói o vídeo no FPS original
4. Salva os frames anotados individualmente

---

## Sequence Inference

Roda um ou mais modelos (detecção e/ou segmentação) sobre um diretório de imagens ou vídeo e
grava um MP4 anotado (mais JPGs por frame). Adicione o sufixo `@detection` / `@segmentation`
a um modelo para sobrescrever a detecção automática da tarefa.

**Um único modelo de detecção sobre uma pasta de imagens**

```bash
python3 sequence_inference.py --input ./frames --output-dir ./out --models yolov8n.pt
```

**Detecção + segmentação, confiança por classe, paleta personalizada**

```bash
python3 sequence_inference.py --input clip.mp4 --output-dir ./out \
    --models cbr.pt@detection seg.pt@segmentation \
    --conf 0.25 --class-conf "rose=0.47,sphere=0.70" --palette contrast
```

| Flag | Padrão | Descrição |
|------|---------|-------------|
| `--input` | obrigatório | Diretório de imagens ou arquivo de vídeo |
| `--output-dir` | obrigatório | Diretório raiz de saída |
| `--models` | obrigatório | Uma ou mais fontes de modelo (sufixo `@detection`/`@segmentation` opcional) |
| `--conf` | `0.25` | Limiar de confiança padrão/fallback |
| `--class-conf` | nenhum | Sobrescritas de confiança por classe, por exemplo `rose=0.47,sphere=0.70` |
| `--iou` | `0.5` | Limiar de IoU (NMS de segmentação) |
| `--device` | `auto` | Dispositivo de computação |
| `--fps` | `15.0` | FPS de saída para entradas de diretório de imagens |
| `--no-save-frames` | off | Mantém somente o MP4 |
| `--hf-token` | `HF_TOKEN` | Token do HuggingFace |

Estilo de anotação: `--palette`, `--colors`, `--box-thickness`, `--text-scale`,
`--mask-opacity`, `--no-mask-outline` (veja `--help`).
