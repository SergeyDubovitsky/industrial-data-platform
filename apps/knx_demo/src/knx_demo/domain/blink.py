from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    state: bool
    duration: float
    label: str


def build_sos_steps(unit: float, repeats: int, finish_off_seconds: float) -> list[Step]:
    short = unit
    long = unit * 3
    intra_gap = unit
    letter_gap = unit * 2
    repeat_gap = unit * 5
    steps: list[Step] = []
    letters = [
        ("S", [short, short, short]),
        ("O", [long, long, long]),
        ("S", [short, short, short]),
    ]

    for repeat_index in range(repeats):
        for letter_index, (letter_name, pulses) in enumerate(letters):
            for pulse_index, pulse_duration in enumerate(pulses):
                steps.append(
                    Step(
                        state=True,
                        duration=pulse_duration,
                        label=f"{letter_name}{pulse_index + 1}",
                    )
                )
                is_last_pulse = (
                    repeat_index == repeats - 1
                    and letter_index == len(letters) - 1
                    and pulse_index == len(pulses) - 1
                )
                if is_last_pulse:
                    continue
                if pulse_index < len(pulses) - 1:
                    gap = intra_gap
                elif letter_index < len(letters) - 1:
                    gap = letter_gap
                else:
                    gap = repeat_gap
                steps.append(
                    Step(
                        state=False,
                        duration=gap,
                        label=f"gap_{repeat_index + 1}_{letter_name}_{pulse_index + 1}",
                    )
                )

    steps.append(Step(state=False, duration=finish_off_seconds, label="finish_off"))
    return steps


def build_steps(
    rhythm: str,
    unit: float,
    repeats: int,
    finish_off_seconds: float,
) -> list[Step]:
    if rhythm == "sos":
        return build_sos_steps(
            unit=unit,
            repeats=repeats,
            finish_off_seconds=finish_off_seconds,
        )
    raise ValueError(f"Unsupported rhythm: {rhythm}")


def calculate_total_duration(prepare_off_seconds: float, steps: list[Step]) -> float:
    return prepare_off_seconds + sum(step.duration for step in steps)
