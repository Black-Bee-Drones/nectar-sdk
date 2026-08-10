# Detectar, segmentar e classificar

Rode detecção de objetos, segmentação de instâncias ou classificação de imagens com
Ultralytics YOLO, HuggingFace Transformers e RF-DETR (só detect/seg) por meio de um
`Detector` / `Segmentor` / `Classifier`. O framework é detectado automaticamente pelo nome
do modelo; só a string do modelo muda.

Precisa da instalação completa primeiro? Veja [Instalação](../setup/index.md).

## 1. Instale o módulo de IA

O módulo de IA precisa do PyTorch:

```bash
make setup            # pick: control ai   (installs PyTorch)

# or: make python-ai && make pytorch

```

Os pesos do modelo baixam automaticamente no primeiro carregamento.

## 2. Detecte objetos

Escolha um framework — o nome do modelo o seleciona. `detect()` devolve resultados tipados
com `class_name`, `confidence` e `xyxy`:

=== "YOLO"

    ```python
    from nectar.ai.detection import Detector
    detector = Detector("yolov8n.pt")                      # ultralytics, auto-detected
    ```

=== "DETR"

    ```python
    from nectar.ai.core import Framework
    from nectar.ai.detection import Detector
    detector = Detector("facebook/detr-resnet-50", framework=Framework.TRANSFORMERS)
    ```

=== "RF-DETR"

    ```python
    from nectar.ai.core import Framework
    from nectar.ai.detection import Detector
    detector = Detector("rfdetr-medium", framework=Framework.RFDETR)
    ```

Depois carregue uma vez e detecte por frame:

```python
detector.load()
result = detector.detect(image, conf=0.5)

for det in result:
    print(f"{det.class_name}: {det.confidence:.2f} at {det.xyxy}")

annotated = detector.draw_detections(image, result)
```

Para rodar ao vivo em uma câmera, coloque `detector.detect` em um callback de
`ImageHandler` (veja [Ver com uma câmera](vision.md)).

## 3. Segmente objetos

`Segmentor` espelha `Detector` com máscaras por instância; `segment()` devolve máscaras
mais os mesmos campos de classe/score:

=== "YOLO-seg"

    ```python
    from nectar.ai.segmentation import Segmentor
    segmentor = Segmentor("yolov8n-seg.pt")
    ```

=== "MaskFormer (DETR)"

    ```python
    from nectar.ai.segmentation import Segmentor
    from nectar.ai.core import Framework
    segmentor = Segmentor("facebook/maskformer-swin-tiny-coco", framework=Framework.TRANSFORMERS)
    ```

=== "RF-DETR-seg"

    ```python
    from nectar.ai.segmentation import Segmentor
    from nectar.ai.core import Framework
    segmentor = Segmentor("rfdetr-seg-medium", framework=Framework.RFDETR)
    ```

```python
segmentor.load()
result = segmentor.segment(image, conf=0.5)
```

!!! success "Resultado esperado"
    Uma lista de detecções/segmentos por frame, cada um com rótulo de classe, confiança e
    uma caixa (detecção) ou máscara (segmentação).

## 4. Classifique imagens

`classify()` devolve resultados tipados top-k com `top1_name` e `top1_confidence`:

=== "YOLO-cls"

    ```python
    from nectar.ai.classification import Classifier
    classifier = Classifier("yolo26n-cls.pt")
    classifier.load()
    result = classifier.classify(image)
    print(result.top1_name, result.top1_confidence)
    ```

=== "ViT"

    ```python
    from nectar.ai.classification import Classifier
    from nectar.ai.core import Framework
    classifier = Classifier(
        "google/vit-base-patch16-224",
        framework=Framework.TRANSFORMERS,
    )
    classifier.load()
    result = classifier.classify(image, topk=5)
    ```

## 5. Além da inferência

O mesmo `Detector` / `Segmentor` / `Classifier` cobre o fluxo completo — apontadores na
referência:

- **Slicing inference** para objetos pequenos em frames de alta resolução, com pós-processamento
  NMS / Soft-NMS / WBF / NMM —
  [Detection](../modules/ai/detection/).
- **Treinamento** com dataclasses de config por framework, logging TensorBoard e push no
  HuggingFace Hub; **avaliação** e ferramentas de **dataset** —
  [visão geral de AI](../modules/ai/).
- **CLI `nectar-ai`** para predict / train / evaluate sem escrever um script.

## 6. Tutoriais em notebook (Colab)

Fluxos ponta a ponta no Google Colab:

- **Detecção:** [Abrir no Colab](https://colab.research.google.com/drive/1mQmbWwnwn-nzMdBlzvkuBmYPMHUrCm_Z?usp=sharing)
- **Classificação:** [Abrir no Colab](https://colab.research.google.com/drive/1mEo05wfYJRsuxKodxbFwBuxRSRh43f-X?usp=sharing)
- **Segmentação:** [Abrir no Colab](https://colab.research.google.com/drive/1qZzAF_iD2sZyuWPin48XpxaY6dtak_gV?usp=sharing)

## Ver também

- [Visão geral de AI](../modules/ai/) · [Detection](../modules/ai/detection/) ·
  [Segmentation](../modules/ai/segmentation/) ·
  [Classification](../modules/ai/classification.md).
- [Exemplos de AI](../modules/examples/ai.md) — scripts de detector, classificador
  e batch-detector.
