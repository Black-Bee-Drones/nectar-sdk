# Detect & segment & classify

Run object detection, instance segmentation, or image classification across Ultralytics
YOLO, HuggingFace Transformers, and RF-DETR (detect/seg only) behind one
`Detector` / `Segmentor` / `Classifier`. The framework is auto-detected from the model
name; only the model string changes.

Need the full install first? See [Installation](../setup/index.md).

## 1. Install the AI module

The AI module needs PyTorch:

```bash
make setup            # pick: control ai   (installs PyTorch)
# or: make python-ai && make pytorch
```

Model weights download automatically on first load.

## 2. Detect objects

Pick a framework — the model name selects it. `detect()` returns typed results with
`class_name`, `confidence`, and `xyxy`:

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

Then load once and detect per frame:

```python
detector.load()
result = detector.detect(image, conf=0.5)

for det in result:
    print(f"{det.class_name}: {det.confidence:.2f} at {det.xyxy}")

annotated = detector.draw_detections(image, result)
```

To run it live on a camera, put `detector.detect` in an `ImageHandler` callback
(see [See with a camera](vision.md)).

## 3. Segment objects

`Segmentor` mirrors `Detector` with per-instance masks; `segment()` returns masks plus the
same class/score fields:

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

!!! success "Expected result"
    A list of detections/segments per frame, each with a class label, a confidence, and a box
    (detection) or mask (segmentation).

## 4. Classify images

`classify()` returns typed top-k results with `top1_name` and `top1_confidence`:

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

## 5. Beyond inference

The same `Detector` / `Segmentor` / `Classifier` cover the whole workflow — pointers into the reference:

- **Slicing inference** for small objects in high-resolution frames, with NMS / Soft-NMS / WBF /
  NMM post-processing — [Detection reference](../modules/ai/detection.md).
- **Training** with per-framework config dataclasses, TensorBoard logging, and HuggingFace Hub
  push; **evaluation** and **dataset** tooling — [AI overview](../modules/ai/index.md).
- **`nectar-ai` CLI** for predict / train / evaluate without writing a script.

## 6. Notebook tutorials (Colab)

End-to-end workflows in Google Colab:

- **Detection:** [Open in Colab](https://colab.research.google.com/drive/1mQmbWwnwn-nzMdBlzvkuBmYPMHUrCm_Z?usp=sharing)
- **Classification:** [Open in Colab](https://colab.research.google.com/drive/1mEo05wfYJRsuxKodxbFwBuxRSRh43f-X?usp=sharing)
- **Segmentation:** [Open in Colab](https://colab.research.google.com/drive/1qZzAF_iD2sZyuWPin48XpxaY6dtak_gV?usp=sharing)

## Go deeper

- [AI overview](../modules/ai/index.md) · [Detection](../modules/ai/detection.md) ·
  [Segmentation](../modules/ai/segmentation.md) · [Classification](../modules/ai/classification.md).
- [AI examples](../modules/examples/ai.md) — detector, classifier, and batch-detector scripts.
