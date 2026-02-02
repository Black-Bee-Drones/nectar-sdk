from typing import Optional, Dict
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QLineEdit,
    QDoubleSpinBox,
    QCheckBox,
    QStackedWidget,
    QGridLayout,
    QFrame,
)
from PySide6.QtCore import Qt, Signal, Slot, QThread, QObject

from mirela_sdk.interface.theme import COLORS


class ModelLoadWorker(QObject):
    """
    Background worker for loading detection models.

    Handles model initialization in a separate thread to prevent
    UI blocking during potentially slow model loading.

    Signals
    -------
    finished : Signal(bool, str)
        Emitted when loading completes with (success, error_message).
    progress : Signal(str)
        Emitted with status updates during loading.
    """

    finished = Signal(bool, str)
    progress = Signal(str)

    def __init__(
        self,
        model_source: str,
        framework: str,
        device: str = "auto",
        hf_token: Optional[str] = None,
    ) -> None:
        super().__init__()
        self._model_source = model_source
        self._framework = framework
        self._device = device
        self._hf_token = hf_token
        self._detector = None

    @property
    def detector(self):
        """Return the loaded detector instance."""
        return self._detector

    def run(self) -> None:
        """Load the detection model."""
        try:
            self.progress.emit(f"Loading {self._model_source}...")

            from mirela_sdk.ai.detection import Detector
            import os

            if self._hf_token:
                os.environ["HF_TOKEN"] = self._hf_token

            self._detector = Detector(
                model_source=self._model_source,
                framework=self._framework if self._framework != "auto" else None,
                device=self._device,
            )

            self.progress.emit("Initializing model...")
            self._detector.load()

            self.finished.emit(True, "")
        except (ImportError, ValueError, RuntimeError, OSError) as e:
            self.finished.emit(False, str(e))


class DetectionConfigPanel(QWidget):
    """
    Configuration panel for AI object detection.

    Provides controls for selecting detection framework, model source,
    confidence threshold, and inference parameters. Supports local models,
    default YOLO models, and HuggingFace models.

    Signals
    -------
    detectorReady : Signal(object)
        Emitted when detector is loaded with the Detector instance.
    detectorUnloaded : Signal()
        Emitted when detector is unloaded.
    configChanged : Signal()
        Emitted when any configuration value changes.
    statusChanged : Signal(str)
        Emitted with status message updates.

    Parameters
    ----------
    parent : QWidget, optional
        Parent widget.
    """

    # Pre-configured team models on HuggingFace
    TEAM_MODELS = {
        "IMAV Gate": "blackbeedrones/imav-2025-gate:best.pt",
        "IMAV Platform": "blackbeedrones/imav-2025-platform:best.pt",
        "CBR Base": "blackbeedrones/cbr-25-base:best.pt",
    }

    # Default models by framework
    DEFAULT_MODELS = {
        "ultralytics": [
            "yolo11n.pt",
            "yolo11s.pt",
            "yolo11m.pt",
            "yolov8n.pt",
            "yolov8s.pt",
            "yolov8m.pt",
            "yolov10n.pt",
            "yolov10s.pt",
            "yolov10m.pt",
            "yolo26n.pt",
            "yolo26s.pt",
            "yolo26m.pt",
            "yolo26l.pt",
            "yolo26x.pt",
        ],
        "rfdetr": [
            "rfdetr-base",
            "rfdetr-large",
        ],
        "transformers": [
            "facebook/detr-resnet-50",
            "facebook/detr-resnet-101",
            "microsoft/conditional-detr-resnet-50",
        ],
    }

    detectorReady = Signal(object)
    detectorUnloaded = Signal()
    configChanged = Signal()
    statusChanged = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._detector = None
        self._load_thread: Optional[QThread] = None
        self._load_worker: Optional[ModelLoadWorker] = None

        self._conf_threshold = 0.25
        self._iou_threshold = 0.5
        self._show_labels = True
        self._show_confidence = True

        self._default_model_combo: Optional[QComboBox] = None
        self._team_model_combo: Optional[QComboBox] = None
        self._team_token_edit: Optional[QLineEdit] = None
        self._hf_repo_edit: Optional[QLineEdit] = None
        self._hf_token_edit: Optional[QLineEdit] = None
        self._local_path_edit: Optional[QLineEdit] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Framework selection
        fw_layout = QHBoxLayout()
        fw_layout.setSpacing(6)
        fw_lbl = QLabel("Framework:")
        fw_lbl.setProperty("secondary", True)
        fw_lbl.setFixedWidth(70)

        self._framework_combo = QComboBox()
        self._framework_combo.addItems(
            ["auto", "ultralytics", "transformers", "rfdetr"]
        )
        self._framework_combo.setToolTip(
            "Detection framework (auto-detects from model)"
        )
        self._framework_combo.currentTextChanged.connect(self._on_framework_changed)
        fw_layout.addWidget(fw_lbl)
        fw_layout.addWidget(self._framework_combo, 1)
        layout.addLayout(fw_layout)

        # Model source type
        src_layout = QHBoxLayout()
        src_layout.setSpacing(6)
        src_lbl = QLabel("Source:")
        src_lbl.setProperty("secondary", True)
        src_lbl.setFixedWidth(70)

        self._source_combo = QComboBox()
        self._source_combo.addItems(
            ["Defaults", "Team Models", "HuggingFace", "Local File"]
        )
        self._source_combo.currentTextChanged.connect(self._on_source_changed)
        src_layout.addWidget(src_lbl)
        src_layout.addWidget(self._source_combo, 1)
        layout.addLayout(src_layout)

        # Stacked widget for different source configs
        self._source_stack = QStackedWidget()
        self._create_defaults_page()
        self._create_team_models_page()
        self._create_huggingface_page()
        self._create_local_file_page()
        layout.addWidget(self._source_stack)

        # Device selection
        dev_layout = QHBoxLayout()
        dev_layout.setSpacing(6)
        dev_lbl = QLabel("Device:")
        dev_lbl.setProperty("secondary", True)
        dev_lbl.setFixedWidth(70)

        self._device_combo = QComboBox()
        self._device_combo.addItems(["auto", "cuda", "cpu", "0", "1"])
        self._device_combo.setToolTip(
            "Inference device (auto, cuda, cpu, or GPU index)"
        )
        dev_layout.addWidget(dev_lbl)
        dev_layout.addWidget(self._device_combo, 1)
        layout.addLayout(dev_layout)

        # Confidence threshold
        conf_layout = QHBoxLayout()
        conf_layout.setSpacing(6)
        conf_lbl = QLabel("Conf:")
        conf_lbl.setProperty("secondary", True)
        conf_lbl.setFixedWidth(70)

        self._conf_spin = QDoubleSpinBox()
        self._conf_spin.setRange(0.01, 1.0)
        self._conf_spin.setSingleStep(0.05)
        self._conf_spin.setValue(0.25)
        self._conf_spin.setDecimals(2)
        self._conf_spin.setToolTip("Confidence threshold for detections")
        self._conf_spin.valueChanged.connect(self._on_conf_changed)
        conf_layout.addWidget(conf_lbl)
        conf_layout.addWidget(self._conf_spin, 1)
        layout.addLayout(conf_layout)

        # IoU threshold
        iou_layout = QHBoxLayout()
        iou_layout.setSpacing(6)
        iou_lbl = QLabel("IoU:")
        iou_lbl.setProperty("secondary", True)
        iou_lbl.setFixedWidth(70)

        self._iou_spin = QDoubleSpinBox()
        self._iou_spin.setRange(0.1, 1.0)
        self._iou_spin.setSingleStep(0.05)
        self._iou_spin.setValue(0.5)
        self._iou_spin.setDecimals(2)
        self._iou_spin.setToolTip("IoU threshold for NMS")
        self._iou_spin.valueChanged.connect(self._on_iou_changed)
        iou_layout.addWidget(iou_lbl)
        iou_layout.addWidget(self._iou_spin, 1)
        layout.addLayout(iou_layout)

        # Display options
        opt_layout = QHBoxLayout()
        opt_layout.setSpacing(8)

        self._show_labels_cb = QCheckBox("Labels")
        self._show_labels_cb.setChecked(True)
        self._show_labels_cb.setToolTip("Show class labels on detections")
        self._show_labels_cb.stateChanged.connect(self._on_display_changed)

        self._show_conf_cb = QCheckBox("Scores")
        self._show_conf_cb.setChecked(True)
        self._show_conf_cb.setToolTip("Show confidence scores on detections")
        self._show_conf_cb.stateChanged.connect(self._on_display_changed)

        opt_layout.addWidget(self._show_labels_cb)
        opt_layout.addWidget(self._show_conf_cb)
        opt_layout.addStretch()
        layout.addLayout(opt_layout)

        # Load/Unload buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self._load_btn = QPushButton("Load Model")
        self._load_btn.setProperty("accent", True)
        self._load_btn.clicked.connect(self._on_load_clicked)

        self._unload_btn = QPushButton("Unload")
        self._unload_btn.clicked.connect(self._on_unload_clicked)
        self._unload_btn.setEnabled(False)

        btn_layout.addWidget(self._load_btn)
        btn_layout.addWidget(self._unload_btn)
        layout.addLayout(btn_layout)

        # Status label
        self._status_label = QLabel("No model loaded")
        self._status_label.setProperty("muted", True)
        self._status_label.setWordWrap(True)
        self._status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._status_label)

        # Detection stats
        self._stats_frame = QFrame()
        self._stats_frame.setStyleSheet(
            f"""
            QFrame {{
                background-color: {COLORS.surface_elevated};
                border-radius: 4px;
                padding: 4px;
            }}
        """
        )
        stats_layout = QGridLayout(self._stats_frame)
        stats_layout.setContentsMargins(6, 4, 6, 4)
        stats_layout.setSpacing(4)

        self._det_count_label = QLabel("Detections: -")
        self._det_count_label.setStyleSheet(
            f"color: {COLORS.accent}; font-weight: 600;"
        )

        self._inf_time_label = QLabel("Inference: - ms")
        self._inf_time_label.setProperty("secondary", True)

        self._classes_label = QLabel("")
        self._classes_label.setProperty("muted", True)
        self._classes_label.setWordWrap(True)

        stats_layout.addWidget(self._det_count_label, 0, 0)
        stats_layout.addWidget(self._inf_time_label, 0, 1)
        stats_layout.addWidget(self._classes_label, 1, 0, 1, 2)

        self._stats_frame.setVisible(False)
        layout.addWidget(self._stats_frame)

    def _create_defaults_page(self) -> None:
        """Create page for default model selection (framework-dependent)."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        model_layout = QHBoxLayout()
        model_layout.setSpacing(6)
        lbl = QLabel("Model:")
        lbl.setProperty("secondary", True)
        lbl.setFixedWidth(70)

        self._default_model_combo = QComboBox()
        self._default_model_combo.addItems(self.DEFAULT_MODELS["ultralytics"])
        self._default_model_combo.setToolTip("Pre-trained model (depends on framework)")
        model_layout.addWidget(lbl)
        model_layout.addWidget(self._default_model_combo, 1)
        layout.addLayout(model_layout)

        self._source_stack.addWidget(page)

    def _create_team_models_page(self) -> None:
        """Create page for team HuggingFace models."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        model_layout = QHBoxLayout()
        model_layout.setSpacing(6)
        lbl = QLabel("Model:")
        lbl.setProperty("secondary", True)
        lbl.setFixedWidth(70)

        self._team_model_combo = QComboBox()
        self._team_model_combo.addItems(list(self.TEAM_MODELS.keys()))
        self._team_model_combo.setToolTip("Team models on HuggingFace")
        model_layout.addWidget(lbl)
        model_layout.addWidget(self._team_model_combo, 1)
        layout.addLayout(model_layout)

        # HF token (optional for private repos)
        token_layout = QHBoxLayout()
        token_layout.setSpacing(6)
        token_lbl = QLabel("Token:")
        token_lbl.setProperty("secondary", True)
        token_lbl.setFixedWidth(70)

        self._team_token_edit = QLineEdit()
        self._team_token_edit.setPlaceholderText("HF token (if private repo)")
        self._team_token_edit.setEchoMode(QLineEdit.Password)
        token_layout.addWidget(token_lbl)
        token_layout.addWidget(self._team_token_edit, 1)
        layout.addLayout(token_layout)

        self._source_stack.addWidget(page)

    def _create_huggingface_page(self) -> None:
        """Create page for custom HuggingFace model input."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        # Repo ID
        repo_layout = QHBoxLayout()
        repo_layout.setSpacing(6)
        repo_lbl = QLabel("Repo:")
        repo_lbl.setProperty("secondary", True)
        repo_lbl.setFixedWidth(70)

        self._hf_repo_edit = QLineEdit()
        self._hf_repo_edit.setPlaceholderText("user/repo:model.pt")
        self._hf_repo_edit.setToolTip("HuggingFace repo in format user/repo:filename")
        repo_layout.addWidget(repo_lbl)
        repo_layout.addWidget(self._hf_repo_edit, 1)
        layout.addLayout(repo_layout)

        # Token
        token_layout = QHBoxLayout()
        token_layout.setSpacing(6)
        token_lbl = QLabel("Token:")
        token_lbl.setProperty("secondary", True)
        token_lbl.setFixedWidth(70)

        self._hf_token_edit = QLineEdit()
        self._hf_token_edit.setPlaceholderText("HF token (optional)")
        self._hf_token_edit.setEchoMode(QLineEdit.Password)
        token_layout.addWidget(token_lbl)
        token_layout.addWidget(self._hf_token_edit, 1)
        layout.addLayout(token_layout)

        self._source_stack.addWidget(page)

    def _create_local_file_page(self) -> None:
        """Create page for local file path input."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        path_layout = QHBoxLayout()
        path_layout.setSpacing(6)
        path_lbl = QLabel("Path:")
        path_lbl.setProperty("secondary", True)
        path_lbl.setFixedWidth(70)

        self._local_path_edit = QLineEdit()
        self._local_path_edit.setPlaceholderText("/path/to/model.pt")
        self._local_path_edit.setToolTip("Path to local model file")
        path_layout.addWidget(path_lbl)
        path_layout.addWidget(self._local_path_edit, 1)
        layout.addLayout(path_layout)

        self._source_stack.addWidget(page)

    @Slot(str)
    def _on_framework_changed(self, _framework: str) -> None:
        """Handle framework selection change."""
        self._update_default_models()
        self.configChanged.emit()

    def _update_default_models(self) -> None:
        """Update default models combo based on selected framework."""
        framework = self._framework_combo.currentText()

        if framework == "auto":
            framework = "ultralytics"

        models = self.DEFAULT_MODELS.get(framework, self.DEFAULT_MODELS["ultralytics"])

        if self._default_model_combo is not None:
            self._default_model_combo.clear()
            self._default_model_combo.addItems(models)

    @Slot(str)
    def _on_source_changed(self, source: str) -> None:
        """Handle source type selection change."""
        source_map = {
            "Defaults": 0,
            "Team Models": 1,
            "HuggingFace": 2,
            "Local File": 3,
        }
        self._source_stack.setCurrentIndex(source_map.get(source, 0))
        self.configChanged.emit()

    @Slot(float)
    def _on_conf_changed(self, value: float) -> None:
        """Handle confidence threshold change."""
        self._conf_threshold = value
        self.configChanged.emit()

    @Slot(float)
    def _on_iou_changed(self, value: float) -> None:
        """Handle IoU threshold change."""
        self._iou_threshold = value
        self.configChanged.emit()

    @Slot()
    def _on_display_changed(self) -> None:
        """Handle display options change."""
        self._show_labels = self._show_labels_cb.isChecked()
        self._show_confidence = self._show_conf_cb.isChecked()
        self.configChanged.emit()

    def _get_model_source(self) -> str:
        """Get the current model source string."""
        source_type = self._source_combo.currentText()

        if source_type == "Defaults":
            return self._default_model_combo.currentText()
        elif source_type == "Team Models":
            model_name = self._team_model_combo.currentText()
            return self.TEAM_MODELS.get(model_name, "")
        elif source_type == "HuggingFace":
            return self._hf_repo_edit.text().strip()
        elif source_type == "Local File":
            return self._local_path_edit.text().strip()

        return ""

    def _get_hf_token(self) -> Optional[str]:
        """Get HuggingFace token if provided."""
        source_type = self._source_combo.currentText()

        if source_type == "Team Models":
            token = self._team_token_edit.text().strip()
            return token if token else None
        elif source_type == "HuggingFace":
            token = self._hf_token_edit.text().strip()
            return token if token else None

        return None

    @Slot()
    def _on_load_clicked(self) -> None:
        """Handle load button click."""
        model_source = self._get_model_source()
        if not model_source:
            self._status_label.setText("Please specify a model")
            return

        framework = self._framework_combo.currentText()
        device = self._device_combo.currentText()
        hf_token = self._get_hf_token()

        # Disable UI during loading
        self._load_btn.setEnabled(False)
        self._source_combo.setEnabled(False)
        self._framework_combo.setEnabled(False)
        self._status_label.setText("Loading model...")
        self.statusChanged.emit("Loading detection model...")

        # Start loading in background thread
        self._load_thread = QThread()
        self._load_worker = ModelLoadWorker(model_source, framework, device, hf_token)
        self._load_worker.moveToThread(self._load_thread)

        self._load_thread.started.connect(self._load_worker.run)
        self._load_worker.progress.connect(self._on_load_progress)
        self._load_worker.finished.connect(self._on_load_finished)
        self._load_worker.finished.connect(self._load_thread.quit)

        self._load_thread.start()

    @Slot(str)
    def _on_load_progress(self, message: str) -> None:
        """Handle loading progress update."""
        self._status_label.setText(message)
        self.statusChanged.emit(message)

    @Slot(bool, str)
    def _on_load_finished(self, success: bool, error: str) -> None:
        """Handle model loading completion."""
        if success and self._load_worker:
            self._detector = self._load_worker.detector
            model_name = self._get_model_source().split("/")[-1].split(":")[-1]
            self._status_label.setText(f"✓ {model_name} loaded")
            self._status_label.setStyleSheet(f"color: {COLORS.success};")
            self._unload_btn.setEnabled(True)
            self._stats_frame.setVisible(True)
            self.detectorReady.emit(self._detector)
            self.statusChanged.emit(f"Detection model loaded: {model_name}")
        else:
            self._status_label.setText(f"✗ Error: {error[:50]}...")
            self._status_label.setStyleSheet(f"color: {COLORS.error};")
            self._load_btn.setEnabled(True)
            self._source_combo.setEnabled(True)
            self._framework_combo.setEnabled(True)
            self.statusChanged.emit(f"Failed to load model: {error}")

    @Slot()
    def _on_unload_clicked(self) -> None:
        """Handle unload button click."""
        self._detector = None
        self._status_label.setText("No model loaded")
        self._status_label.setStyleSheet("")
        self._load_btn.setEnabled(True)
        self._unload_btn.setEnabled(False)
        self._source_combo.setEnabled(True)
        self._framework_combo.setEnabled(True)
        self._stats_frame.setVisible(False)
        self._det_count_label.setText("Detections: -")
        self._inf_time_label.setText("Inference: - ms")
        self._classes_label.setText("")
        self.detectorUnloaded.emit()
        self.statusChanged.emit("Detection model unloaded")

    def update_stats(
        self,
        count: int,
        inference_time_ms: float,
        class_counts: Optional[Dict[str, int]] = None,
    ) -> None:
        """
        Update detection statistics display.

        Parameters
        ----------
        count : int
            Number of detections.
        inference_time_ms : float
            Inference time in milliseconds.
        class_counts : Dict[str, int], optional
            Count per class name.
        """
        self._det_count_label.setText(f"Detections: {count}")
        self._inf_time_label.setText(f"Inference: {inference_time_ms:.1f} ms")

        if class_counts:
            items = [f"{k}: {v}" for k, v in sorted(class_counts.items())]
            self._classes_label.setText(" | ".join(items[:4]))
        else:
            self._classes_label.setText("")

    @property
    def detector(self):
        """Return the loaded detector or None."""
        return self._detector

    @property
    def is_loaded(self) -> bool:
        """Check if a detector is loaded."""
        return self._detector is not None and self._detector.is_loaded

    @property
    def conf_threshold(self) -> float:
        """Current confidence threshold."""
        return self._conf_threshold

    @property
    def iou_threshold(self) -> float:
        """Current IoU threshold."""
        return self._iou_threshold

    @property
    def show_labels(self) -> bool:
        """Whether to show class labels."""
        return self._show_labels

    @property
    def show_confidence(self) -> bool:
        """Whether to show confidence scores."""
        return self._show_confidence

    def setEnabled(self, enabled: bool) -> None:
        """Enable or disable all controls."""
        super().setEnabled(enabled)
        if not enabled and self._detector is None:
            self._load_btn.setEnabled(False)
        elif enabled and self._detector is None:
            self._load_btn.setEnabled(True)

    def cleanup(self) -> None:
        """Clean up resources."""
        if self._load_thread and self._load_thread.isRunning():
            self._load_thread.quit()
            self._load_thread.wait(1000)
        self._detector = None
