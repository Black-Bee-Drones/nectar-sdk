# Detect & segment

Run object detection or instance segmentation across Ultralytics YOLO, HuggingFace
Transformers (DETR), and RF-DETR behind one `Detector` / `Segmentor`. The framework is
auto-detected from the model name; only the model string changes.

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
    from nectar.ai.detection import Detector, Framework
    detector = Detector("facebook/detr-resnet-50", framework=Framework.TRANSFORMERS)
    ```

=== "RF-DETR"

    ```python
    from nectar.ai.detection import Detector, Framework
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
    from nectar.ai.detection import Framework
    segmentor = Segmentor("facebook/maskformer-swin-tiny-coco", framework=Framework.TRANSFORMERS)
    ```

=== "RF-DETR-seg"

    ```python
    from nectar.ai.segmentation import Segmentor
    from nectar.ai.detection import Framework
    segmentor = Segmentor("rfdetr-seg-medium", framework=Framework.RFDETR)
    ```

```python
segmentor.load()
result = segmentor.segment(image, conf=0.5)
```

!!! success "Expected result"
    A list of detections/segments per frame, each with a class label, a confidence, and a box
    (detection) or mask (segmentation).

## 4. Beyond inference

The same `Detector` / `Segmentor` cover the whole workflow — pointers into the reference:

- **Slicing inference** for small objects in high-resolution frames, with NMS / Soft-NMS / WBF /
  NMM post-processing — [Detection reference](../modules/ai/detection.md).
- **Training** with per-framework config dataclasses, TensorBoard logging, and HuggingFace Hub
  push; **evaluation** with mAP (\(\mathrm{mAP} = \frac{1}{N}\sum_{i=1}^{N} \mathrm{AP}_i\)
  over \(N\) classes); **dataset** tooling — [AI overview](../modules/ai/index.md).
- **`nectar-ai` CLI** for predict / train / evaluate without writing a script.

## Go deeper

- [AI overview](../modules/ai/index.md) · [Detection](../modules/ai/detection.md) ·
  [Segmentation](../modules/ai/segmentation.md).
- [AI examples](../modules/examples/ai.md) — detector and batch-detector scripts.
