from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
import yaml
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from mirela_sdk.vision.algorithms.distance.models import (
    ModelType,
    create_model,
)

warnings.filterwarnings("ignore")


@dataclass
class CalibrationResult:
    """
    Results from fitting a single estimation model.

    Parameters
    ----------
    model_type : ModelType
        Type of the fitted model.
    params : Dict[str, Any]
        Fitted parameter values.
    rmse : float
        Root Mean Square Error in distance units.
    r2 : float
        Coefficient of determination (R-squared).
    mae : float
        Mean Absolute Error in distance units.
    aic : float
        Akaike Information Criterion for model selection.
    predictions : np.ndarray
        Model predictions on calibration data.

    Attributes
    ----------
    name : str
        Lowercase name of the model type.
    """

    model_type: ModelType
    params: Dict[str, Any]
    rmse: float
    r2: float
    mae: float
    aic: float
    predictions: np.ndarray = field(repr=False)

    @property
    def name(self) -> str:
        """Lowercase name of the model type."""
        return self.model_type.name.lower()


class ModelCalibrator:
    """
    Calibrate and compare distance estimation models.

    Parameters
    ----------
    data : List[Tuple[float, float]]
        Calibration data as list of (distance_cm, pixel_measurement) tuples.

    Attributes
    ----------
    pixels : np.ndarray
        Pixel measurements from calibration data.
    distances : np.ndarray
        Distance measurements from calibration data.
    results : Dict[ModelType, CalibrationResult]
        Fitted model results keyed by model type.

    Examples
    --------
    >>> data = [(50, 32.2), (60, 28.5), (70, 24.2)]
    >>> calibrator = ModelCalibrator(data)
    >>> calibrator.fit_all()
    >>> best = calibrator.best_model()
    >>> print(f"Best model: {best.name} with R²={best.r2:.4f}")
    """

    def __init__(self, data: List[Tuple[float, float]]):
        sorted_data = sorted(data, key=lambda x: x[1])
        self.pixels = np.array([p[1] for p in sorted_data])
        self.distances = np.array([p[0] for p in sorted_data])
        self.results: Dict[ModelType, CalibrationResult] = {}

    def fit_model(self, model_type: ModelType) -> CalibrationResult:
        """
        Fit a single model type to the calibration data.

        Parameters
        ----------
        model_type : ModelType
            Type of model to fit.

        Returns
        -------
        CalibrationResult
            Fitted model with parameters and metrics.

        Notes
        -----
        Computes the following metrics:
        - RMSE: Root Mean Square Error
        - MAE: Mean Absolute Error
        - R²: Coefficient of determination
        - AIC: Akaike Information Criterion
        """
        model = create_model(model_type)
        params = model.fit(self.pixels, self.distances)
        predictions = np.array([model.estimate(v) for v in self.pixels])

        mse = float(np.mean((predictions - self.distances) ** 2))
        rmse = float(np.sqrt(mse))
        mae = float(np.mean(np.abs(predictions - self.distances)))
        ss_res = np.sum((self.distances - predictions) ** 2)
        ss_tot = np.sum((self.distances - np.mean(self.distances)) ** 2)
        r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0
        n_params = len(params)
        aic = (
            float(len(self.distances) * np.log(mse) + 2 * n_params)
            if mse > 0
            else float("inf")
        )

        result = CalibrationResult(
            model_type=model_type,
            params=params,
            rmse=rmse,
            r2=r2,
            mae=mae,
            aic=aic,
            predictions=predictions,
        )
        self.results[model_type] = result
        return result

    def fit_all(self) -> Dict[ModelType, CalibrationResult]:
        """
        Fit all available model types to the calibration data.

        Returns
        -------
        Dict[ModelType, CalibrationResult]
            Dictionary of results for all successfully fitted models.

        Notes
        -----
        Models that fail to fit (e.g., due to convergence issues)
        are silently skipped.
        """
        for model_type in ModelType:
            try:
                self.fit_model(model_type)
            except Exception:
                pass
        return self.results

    def best_model(self, criterion: str = "aic") -> CalibrationResult:
        """
        Get the best model according to specified criterion.

        Parameters
        ----------
        criterion : str, default="aic"
            Selection criterion: "aic", "rmse", or "r2".

        Returns
        -------
        CalibrationResult
            Best model result.

        Raises
        ------
        ValueError
            If no models have been fitted.

        Notes
        -----
        - AIC: Lower is better (penalizes model complexity)
        - RMSE: Lower is better
        - R²: Higher is better
        """
        if not self.results:
            raise ValueError("No models fitted. Call fit_all() first.")

        key_func = {
            "aic": lambda r: r.aic,
            "rmse": lambda r: r.rmse,
            "r2": lambda r: -r.r2,
        }.get(criterion, lambda r: r.aic)

        return min(self.results.values(), key=key_func)

    def save_params(self, path: Path, default_method: str = None) -> None:
        """
        Save fitted parameters to YAML file.

        Parameters
        ----------
        path : Path
            Output file path.
        default_method : str, optional
            Default method to set in config. If None, uses best model.

        Raises
        ------
        ValueError
            If no models have been fitted.
        """
        if not self.results:
            raise ValueError("No models fitted. Call fit_all() first.")

        data = {}
        for model_type, result in self.results.items():
            data[model_type.name.lower()] = result.params

        if default_method is None:
            default_method = self.best_model().name
        data["default_method"] = default_method

        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    def print_results(self) -> None:
        """
        Print formatted comparison table of all fitted models.
        """
        if not self.results:
            print("No models fitted.")
            return

        print("\n" + "=" * 80)
        print(f"{'Model':<20} {'R²':<10} {'RMSE':<10} {'MAE':<10} {'AIC':<10}")
        print("=" * 80)

        sorted_results = sorted(self.results.values(), key=lambda r: r.aic)
        for r in sorted_results:
            print(
                f"{r.name:<20} {r.r2:<10.4f} {r.rmse:<10.2f} {r.mae:<10.2f} {r.aic:<10.1f}"
            )

        best = self.best_model()
        print("=" * 80)
        print(f"Best model: {best.name} (AIC: {best.aic:.1f}, R²: {best.r2:.4f})")

    def plot(self, save_path: Path) -> None:
        """
        Generate comparison plots and save to file.

        Creates a 2x2 figure with:
        - Model fits overlaid on data points
        - Residual analysis
        - RMSE comparison (horizontal bar chart)
        - AIC comparison (vertical bar chart)

        Parameters
        ----------
        save_path : Path
            Output image file path (e.g., "comparison.png").

        Raises
        ------
        ValueError
            If no models have been fitted.
        """
        if not self.results:
            raise ValueError("No models fitted. Call fit_all() first.")

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        colors = plt.cm.tab10(np.linspace(0, 1, len(self.results)))
        x_smooth = np.linspace(min(self.pixels) - 3, max(self.pixels) + 3, 200)

        ax1, ax2, ax3, ax4 = axes.flat

        ax1.scatter(
            self.pixels,
            self.distances,
            color="red",
            s=80,
            label="Data",
            zorder=10,
            edgecolor="black",
        )
        for i, (model_type, result) in enumerate(self.results.items()):
            model = create_model(model_type, result.params)
            y_smooth = np.array([model.estimate(v) for v in x_smooth])
            ax1.plot(
                x_smooth,
                y_smooth,
                color=colors[i],
                linewidth=2,
                label=f"{result.name} (R²={result.r2:.3f})",
            )
        ax1.set_xlabel("Pixels")
        ax1.set_ylabel("Distance (cm)")
        ax1.set_title("Model Fits")
        ax1.legend(fontsize=8)
        ax1.grid(True, alpha=0.3)

        for i, (model_type, result) in enumerate(self.results.items()):
            residuals = result.predictions - self.distances
            ax2.plot(
                self.pixels,
                residuals,
                "o-",
                color=colors[i],
                label=f"{result.name} (RMSE={result.rmse:.2f})",
            )
        ax2.axhline(y=0, color="red", linestyle="--", alpha=0.7)
        ax2.set_xlabel("Pixels")
        ax2.set_ylabel("Residuals")
        ax2.set_title("Residual Analysis")
        ax2.legend(fontsize=8)
        ax2.grid(True, alpha=0.3)

        sorted_results = sorted(self.results.values(), key=lambda r: r.rmse)
        names = [r.name for r in sorted_results]
        rmse_vals = [r.rmse for r in sorted_results]
        r2_vals = [r.r2 for r in sorted_results]

        bar_colors = [
            (
                "green"
                if r2 > 0.95
                else "steelblue" if r2 > 0.9 else "orange" if r2 > 0 else "red"
            )
            for r2 in r2_vals
        ]
        bars = ax3.barh(names, rmse_vals, color=bar_colors)
        ax3.set_xlabel("RMSE (cm)")
        ax3.set_title("Model Error (sorted by RMSE)")
        ax3.grid(True, alpha=0.3, axis="x")
        for bar, r2 in zip(bars, r2_vals):
            ax3.text(
                bar.get_width() + 0.5,
                bar.get_y() + bar.get_height() / 2,
                f"R²={r2:.3f}",
                va="center",
                fontsize=8,
            )

        aic_vals = [r.aic for r in self.results.values()]
        bars = ax4.bar(names, aic_vals, color=colors[: len(names)])
        best_idx = np.argmin(aic_vals)
        bars[best_idx].set_color("gold")
        bars[best_idx].set_edgecolor("black")
        ax4.set_xticklabels(names, rotation=45, ha="right")
        ax4.set_ylabel("AIC (lower is better)")
        ax4.set_title("Model Selection (AIC)")
        ax4.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        print(f"Plot saved to: {save_path}")


def main():
    """
    Command-line interface for model calibration.

    Usage
    -----
    python calibrator.py [--data FILE] [--output FILE] [--plot [FILE]]

    Arguments
    ---------
    --data : str
        Path to CSV file with (distance,pixels) per line.
        If not provided, uses default sample data.
    --output : str
        Output YAML filename (default: parameters.yaml).
    --plot : str, optional
        Save comparison plot. If flag given without filename,
        saves as model_comparison.png.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Calibrate distance estimation models")
    parser.add_argument("--data", type=str, help="Path to CSV file (distance,pixels)")
    parser.add_argument(
        "--output", type=str, default="parameters.yaml", help="Output YAML"
    )
    parser.add_argument(
        "--plot", type=str, nargs="?", const="model_comparison.png", help="Save plot"
    )
    args = parser.parse_args()

    if args.data:
        data = []
        with open(args.data) as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) == 2:
                    data.append((float(parts[0]), float(parts[1])))
    else:
        data = [
            (50, 32.2),
            (60, 28.5),
            (70, 24.2),
            (80, 23.9),
            (90, 23),
            (100, 21.6),
            (110, 20.1),
            (120, 19.9),
            (130, 18.1),
            (140, 17.2),
            (150, 16.8),
            (160, 16),
            (170, 15),
            (180, 14.8),
        ]

    calibrator = ModelCalibrator(data)
    calibrator.fit_all()
    calibrator.print_results()

    output_path = Path(__file__).parent / args.output
    calibrator.save_params(output_path)
    print(f"Parameters saved to: {output_path}")

    if args.plot is not None:
        plot_path = Path(__file__).parent / args.plot
        calibrator.plot(plot_path)


if __name__ == "__main__":
    main()
