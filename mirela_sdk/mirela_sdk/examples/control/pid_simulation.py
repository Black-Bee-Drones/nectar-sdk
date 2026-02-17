#!/usr/bin/env python3
import argparse
import time
from dataclasses import dataclass

from mirela_sdk.control.pid import PIDController


@dataclass
class SimulationResult:
    """Simulation data for one timestep."""

    time: float
    setpoint: float
    value: float
    error: float
    output: float


class FirstOrderPlant:
    """
    Simple first-order plant: dT/dt = -k*(T - T_ambient) + u

    Models a room with heat loss to ambient and heater input.
    """

    def __init__(self, initial: float = 20.0, ambient: float = 15.0, tau: float = 10.0):
        self.value = initial
        self.ambient = ambient
        self.tau = tau

    def update(self, control_input: float, dt: float) -> float:
        """Apply control input and return new value."""
        # Heat loss + heater effect
        dv = (-1 / self.tau) * (self.value - self.ambient) + control_input
        self.value += dv * dt
        return self.value


def run_simulation(
    setpoint: float = 25.0,
    kp: float = 0.5,
    ki: float = 0.1,
    kd: float = 0.0,
    duration: float = 60.0,
    dt: float = 0.1,
) -> list[SimulationResult]:
    """
    Run PID simulation.

    Returns list of SimulationResult for each timestep.
    """
    plant = FirstOrderPlant(initial=20.0, ambient=18.0, tau=5.0)

    pid = PIDController(
        kp=kp,
        ki=ki,
        kd=kd,
        setpoint=setpoint,
        output_limits=(0.0, 5.0),
        integral_limits=(-5.0, 5.0),
    )

    results = []
    t = 0.0

    while t < duration:
        error = setpoint - plant.value
        output = pid.update(plant.value)

        results.append(
            SimulationResult(
                time=t,
                setpoint=setpoint,
                value=plant.value,
                error=error,
                output=output,
            )
        )

        plant.update(output, dt)
        t += dt
        time.sleep(0.001)

    return results


def print_results(results: list[SimulationResult]):
    """Print results as table."""
    print(f"{'Time':>6} {'Setpoint':>10} {'Value':>10} {'Error':>10} {'Output':>10}")
    print("-" * 50)

    for i, r in enumerate(results):
        if i % 10 == 0:
            print(
                f"{r.time:6.1f} {r.setpoint:10.2f} {r.value:10.2f} {r.error:10.2f} {r.output:10.2f}"
            )


def print_csv(results: list[SimulationResult]):
    """Print results as CSV"""
    print("time,setpoint,value,error,output")
    for r in results:
        print(f"{r.time:.2f},{r.setpoint:.2f},{r.value:.2f},{r.error:.2f},{r.output:.2f}")


def plot_results(results: list[SimulationResult], save_path: str = None):
    """Plot results."""
    try:
        import matplotlib

        matplotlib.use("TkAgg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed. Use --csv for data export.")
        return
    except Exception:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

    times = [r.time for r in results]
    setpoints = [r.setpoint for r in results]
    values = [r.value for r in results]
    outputs = [r.output for r in results]

    _, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)

    ax1.plot(times, setpoints, "r--", label="Setpoint", linewidth=2)
    ax1.plot(times, values, "b-", label="Value", linewidth=2)
    ax1.set_ylabel("Temperature (°C)")
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.set_title("PID Temperature Control Simulation")

    ax2.plot(times, outputs, "g-", label="Control Output", linewidth=2)
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Heater Power")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150)
        print(f"Plot saved to {save_path}")
    else:
        plt.show()


def main():
    parser = argparse.ArgumentParser(description="PID simulation")
    parser.add_argument("--setpoint", type=float, default=25.0, help="Target value")
    parser.add_argument("--kp", type=float, default=2.0, help="Proportional gain")
    parser.add_argument("--ki", type=float, default=5.0, help="Integral gain")
    parser.add_argument("--kd", type=float, default=0.0, help="Derivative gain")
    parser.add_argument("--duration", type=float, default=60.0, help="Simulation time (s)")
    parser.add_argument("--plot", action="store_true", help="Plot results")
    parser.add_argument("--save", type=str, default=None, help="Save plot to file (e.g. plot.png)")
    parser.add_argument("--csv", action="store_true", help="Output CSV format")
    args = parser.parse_args()

    print(
        f"Running PID simulation: setpoint={args.setpoint}, kp={args.kp}, ki={args.ki}, kd={args.kd}"
    )

    results = run_simulation(
        setpoint=args.setpoint,
        kp=args.kp,
        ki=args.ki,
        kd=args.kd,
        duration=args.duration,
    )

    if args.csv:
        print_csv(results)
    elif args.plot or args.save:
        plot_results(results, save_path=args.save)
    else:
        print_results(results)

        final = results[-1]
        print(f"\nFinal: value={final.value:.2f}, error={final.error:.2f}")


if __name__ == "__main__":
    main()
