"""Logistics code inspection experiment for PsychoPy.

Run with the project virtual environment through run.ps1. The experiment writes
one real trial-level CSV per participant; it does not create example results.
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
import time
import traceback
from pathlib import Path

from psychopy import core, event, sound, visual


N_TRIALS_PER_CLASS = 20
PRACTICE_TRIALS = 16
PRACTICE_PASS_RATE = 0.75
ALARM_DELAY_S = 0.300
FEEDBACK_S = 0.400
FIXATION_S = 0.500
ALARM_DURATION_S = 0.150
ALARM_FREQUENCY_HZ = 1000
SYSTEM_VOLUME_TARGET_PCT = 30
# This is a digital amplitude, not an SPL value. Calibrate physically with a
# sound-level meter at the participant position before collecting data.
ALARM_VOLUME = 0.50
ORDER_SEQUENCES = (
    ("A", "B", "D", "C"),
    ("B", "C", "A", "D"),
    ("C", "D", "B", "A"),
    ("D", "A", "C", "B"),
)
# Balance the two key mappings within each block-order sequence as closely as
# possible (each sequence is assigned to three participants).
KEY_MAPPING_BY_PARTICIPANT = (1, 0, 1, 0, 0, 1, 0, 1, 1, 0, 1, 0)
CONDITIONS = {
    "A": {"far_pct": 10, "limit_s": 1.5},
    "B": {"far_pct": 10, "limit_s": 3.0},
    "C": {"far_pct": 40, "limit_s": 1.5},
    "D": {"far_pct": 40, "limit_s": 3.0},
}


def make_code(used: set[str]) -> str:
    while True:
        code = str(random.randint(100000, 999999))
        if code not in used:
            used.add(code)
            return code


def make_label(order_code: str, defect: bool) -> str:
    if not defect:
        return order_code
    position = random.randrange(6)
    replacement = random.choice([d for d in "0123456789" if d != order_code[position]])
    return order_code[:position] + replacement + order_code[position + 1 :]


def has_long_run(items: list[dict], key: str, max_run: int = 3) -> bool:
    run = 1
    for previous, current in zip(items, items[1:]):
        if previous[key] == current[key]:
            run += 1
            if run > max_run:
                return True
        else:
            run = 1
    return False


def constrained_shuffle(items: list[dict]) -> list[dict]:
    for _ in range(5000):
        random.shuffle(items)
        if not has_long_run(items, "defect") and not has_long_run(items, "alarm"):
            return items
    raise RuntimeError("Could not create a balanced trial order.")


def build_block_trials(condition_id: str, used_codes: set[str]) -> list[dict]:
    condition = CONDITIONS[condition_id]
    trials: list[dict] = []
    for defect in (0, 1):
        if defect:
            alarm_count = 18  # 90% hit rate for defect trials
        else:
            alarm_count = round(N_TRIALS_PER_CLASS * condition["far_pct"] / 100)
        alarms = [1] * alarm_count + [0] * (N_TRIALS_PER_CLASS - alarm_count)
        random.shuffle(alarms)
        for alarm in alarms:
            order_code = make_code(used_codes)
            trials.append(
                {
                    "condition": condition_id,
                    "far_pct": condition["far_pct"],
                    "limit_s": condition["limit_s"],
                    "defect": defect,
                    "alarm": alarm,
                    "order_code": order_code,
                    "label_code": make_label(order_code, bool(defect)),
                }
            )
    return constrained_shuffle(trials)


def response_type(defect: int, response: int | None) -> str:
    if response is None:
        return "NR"
    if defect and response:
        return "HIT"
    if defect and not response:
        return "MISS"
    if not defect and response:
        return "FA"
    return "CR"


def wait_for_space(win: visual.Window, message: str) -> None:
    text = visual.TextStim(win, text=message, height=0.055, wrapWidth=1.5, color="white")
    text.draw()
    win.flip()
    # Read names directly from PsychoPy's event queue. In some PsychoPy builds,
    # Keyboard(backend="event") returns (key, timestamp) tuples as key names.
    event.clearEvents(eventType="keyboard")
    while True:
        pressed = event.getKeys(keyList=["space", "escape"])
        if "escape" in pressed:
            raise KeyboardInterrupt
        if "space" in pressed:
            return
        core.wait(0.01)


def run_sound_check() -> None:
    win = visual.Window(fullscr=False, size=(900, 600), color="black", units="norm")
    message = visual.TextStim(
        win,
        text=(
            f"시스템 출력 음량을 {SYSTEM_VOLUME_TARGET_PCT}%로 설정하세요.\n"
            "같은 PC와 같은 이어폰으로 모든 참가자를 진행합니다.\n"
            "스페이스를 누르면 1초 경고음이 재생됩니다.\n"
            "리허설에서 잘 들리고 불편하지 않은지 확인한 뒤,\n"
            "필요하면 본 실험 전에 공통 음량을 한 번 조정하고 고정하세요.\n\n"
            "종료: ESC"
        ),
        height=0.06,
        wrapWidth=1.6,
        color="white",
    )
    tone = sound.Sound(value=ALARM_FREQUENCY_HZ, secs=1.0, volume=ALARM_VOLUME)
    try:
        event.clearEvents(eventType="keyboard")
        while True:
            message.draw()
            win.flip()
            pressed = event.getKeys(keyList=["space", "escape"])
            if "escape" in pressed:
                return
            if "space" in pressed:
                tone.stop()
                tone.play()
            core.wait(0.01)
    finally:
        tone.stop()
        win.close()


def run_experiment(resume: bool = False) -> None:
    try:
        participant_number = int(input("참가자 번호를 입력하세요 (1-12): ").strip())
    except ValueError as exc:
        raise SystemExit("참가자 번호는 1부터 12까지의 정수여야 합니다.") from exc
    if not 1 <= participant_number <= 12:
        raise SystemExit("참가자 번호는 1부터 12까지 입력하세요.")

    participant_id = f"P{participant_number:02d}"
    sequence_index = (participant_number - 1) % len(ORDER_SEQUENCES)
    order = ORDER_SEQUENCES[sequence_index]
    if KEY_MAPPING_BY_PARTICIPANT[participant_number - 1] == 0:
        key_mapping = {"f": 0, "j": 1}
    else:
        key_mapping = {"f": 1, "j": 0}
    key_mapping_label = f"F={('정상' if key_mapping['f'] == 0 else '결함')}, J={('정상' if key_mapping['j'] == 0 else '결함')}"
    out_dir = Path(__file__).resolve().parent / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{participant_id}_trials.csv"
    is_resume = False
    resume_start_block = 1
    used_codes: set[str] = set()
    if out_path.exists():
        if not resume:
            raise SystemExit(
                f"{out_path.name} 파일이 이미 있습니다. 기존 자료는 보존했습니다. "
                "완료된 블록 다음부터 이어 하려면 --resume을 사용하세요."
            )
        with out_path.open("r", newline="", encoding="utf-8-sig") as csv_file:
            existing_rows = list(csv.DictReader(csv_file))
        if not existing_rows:
            raise SystemExit("기존 CSV에 시행 자료가 없어 이어 실행할 수 없습니다.")
        if any(row.get("PID") != participant_id for row in existing_rows):
            raise SystemExit("기존 CSV의 참가자 ID가 입력한 ID와 달라 이어 실행을 중단했습니다.")
        expected_sequence = "-".join(order)
        if any(row.get("Sequence") != expected_sequence for row in existing_rows):
            raise SystemExit("기존 CSV의 블록 순서가 현재 배정과 달라 이어 실행할 수 없습니다.")

        block_counts = {block: 0 for block in range(1, len(order) + 1)}
        for row in existing_rows:
            block = int(row["Block"])
            if block not in block_counts:
                raise SystemExit(f"CSV에서 올바르지 않은 블록 번호를 발견했습니다: {block}")
            block_counts[block] += 1
            used_codes.add(row["OrderCode"])
            used_codes.add(row["LabelCode"])

        found_gap = False
        for block in range(1, len(order) + 1):
            count = block_counts[block]
            if count == N_TRIALS_PER_CLASS * 2:
                if found_gap:
                    raise SystemExit("완료된 블록 사이에 자료가 비어 있어 이어 실행할 수 없습니다.")
                resume_start_block = block + 1
            elif count == 0:
                found_gap = True
            else:
                raise SystemExit(
                    f"{block}번 블록 자료가 {count}회로 부분 완료 상태입니다. "
                    "이 블록은 자동 이어 실행하지 않으므로 CSV를 보존하고 진행자에게 확인하세요."
                )
        if resume_start_block > len(order):
            raise SystemExit("이 참가자는 이미 4개 블록을 모두 완료했습니다.")
        is_resume = True

    print(f"참가자: {participant_id}")
    print("블록 순서:", " → ".join(order))
    print("응답 키:", key_mapping_label)
    print(f"시스템 출력 음량 목표: {SYSTEM_VOLUME_TARGET_PCT}% (전 참가자 동일하게 유지)")
    if is_resume:
        print(f"기존 자료를 보존하고 {resume_start_block}번 블록부터 이어 실행합니다.")
    print("화면의 참가자 안내가 준비되면 참가자에게 스페이스를 누르게 하세요.")

    win = visual.Window(fullscr=True, color="black", units="norm", allowGUI=False)
    order_label = visual.TextStim(win, text="주문 코드", pos=(0, 0.45), height=0.055, color="white")
    order_code_text = visual.TextStim(win, text="", pos=(0, 0.25), height=0.12, color="white")
    label_label = visual.TextStim(win, text="라벨 코드", pos=(0, -0.02), height=0.055, color="white")
    label_code_text = visual.TextStim(win, text="", pos=(0, -0.24), height=0.12, color="white")
    alarm_text = visual.TextStim(win, text="▲ 경고", pos=(0, -0.54), height=0.09, color="red")
    fixation = visual.TextStim(win, text="+", height=0.08, color="white")
    feedback = visual.TextStim(win, text="", height=0.07, color="white")
    tone = sound.Sound(
        value=ALARM_FREQUENCY_HZ,
        secs=ALARM_DURATION_S,
        volume=ALARM_VOLUME,
    )

    fields = [
        "PID",
        "ParticipantNumber",
        "Sequence",
        "KeyMapping",
        "Block",
        "Trial",
        "Condition",
        "FAR_pct",
        "Limit_s",
        "OrderCode",
        "LabelCode",
        "Defect",
        "Alarm",
        "Response",
        "KeyPressed",
        "Type",
        "RT_ms",
        "Accuracy",
        "Timeout",
    ]

    def run_trials(
        trials: list[dict],
        writer: csv.DictWriter | None,
        block_number: int,
        practice: bool = False,
        output_stream=None,
    ) -> int:
        correct_count = 0
        for trial_number, trial in enumerate(trials, start=1):
            fixation.draw()
            win.flip()
            core.wait(FIXATION_S)

            order_code_text.text = trial["order_code"]
            label_code_text.text = trial["label_code"]
            # Keep the full stimulus on screen across every buffer flip while
            # the response loop is running. One-time draw() calls disappear
            # after the next flip unless autoDraw is enabled.
            order_label.setAutoDraw(True)
            order_code_text.setAutoDraw(True)
            label_label.setAutoDraw(True)
            label_code_text.setAutoDraw(True)
            alarm_text.setAutoDraw(False)
            event.clearEvents(eventType="keyboard")
            trial_clock = core.Clock()
            win.callOnFlip(trial_clock.reset)
            win.flip()

            response: int | None = None
            rt_ms: float | None = None
            alarm_started = False
            while trial_clock.getTime() < trial["limit_s"]:
                elapsed = trial_clock.getTime()
                if trial["alarm"] and not alarm_started and elapsed >= ALARM_DELAY_S:
                    alarm_text.setAutoDraw(True)
                    win.callOnFlip(tone.play)
                    alarm_started = True

                pressed = event.getKeys(
                    keyList=["f", "j", "escape"], timeStamped=trial_clock
                )
                pressed_names = [key_name for key_name, _ in pressed]
                if "escape" in pressed_names:
                    tone.stop()
                    raise KeyboardInterrupt
                valid = [key for key in pressed if key[0] in ("f", "j")]
                if valid:
                    response = key_mapping[valid[0][0]]
                    rt_ms = round(float(valid[0][1]) * 1000, 2)
                    break
                win.flip()

            tone.stop()
            order_label.setAutoDraw(False)
            order_code_text.setAutoDraw(False)
            label_label.setAutoDraw(False)
            label_code_text.setAutoDraw(False)
            alarm_text.setAutoDraw(False)
            correct = None if response is None else int(response == trial["defect"])
            if correct:
                correct_count += 1

            actual_state = "결함" if trial["defect"] else "정상"
            feedback.text = f"실제 상태: {actual_state}"
            feedback.draw()
            win.flip()
            core.wait(FEEDBACK_S)

            if not practice and writer is not None:
                writer.writerow(
                    {
                        "PID": participant_id,
                        "ParticipantNumber": participant_number,
                        "Sequence": "-".join(order),
                        "KeyMapping": key_mapping_label,
                        "Block": block_number,
                        "Trial": trial_number,
                        "Condition": trial["condition"],
                        "FAR_pct": trial["far_pct"],
                        "Limit_s": trial["limit_s"],
                        "OrderCode": trial["order_code"],
                        "LabelCode": trial["label_code"],
                        "Defect": trial["defect"],
                        "Alarm": trial["alarm"],
                        "Response": "" if response is None else response,
                        "KeyPressed": "" if response is None else valid[0].name,
                        "Type": response_type(trial["defect"], response),
                        "RT_ms": "" if rt_ms is None else rt_ms,
                        "Accuracy": "" if correct is None else correct,
                        "Timeout": int(response is None),
                    }
                )
                # Flush after every completed trial so an interrupted session
                # retains all data collected up to that point.
                if output_stream is not None:
                    output_stream.flush()
        return correct_count

    try:
        if is_resume:
            wait_for_space(
                win,
                f"기존 자료를 보존했습니다. {resume_start_block}번 블록 "
                f"(조건 {order[resume_start_block - 1]})부터 이어서 진행합니다.\n\n"
                "계속하려면 스페이스",
            )
        else:
            wait_for_space(
                win,
                "주문 코드와 라벨 코드를 비교하세요.\n"
                f"두 코드가 같으면 {('F' if key_mapping['f'] == 0 else 'J')}(정상), "
                f"한 자리라도 다르면 {('F' if key_mapping['f'] == 1 else 'J')}(결함)를 누르세요.\n"
                "경고는 참고 자료이며, 코드 자체를 확인해 응답하세요.\n"
                "가능한 빠르고 정확하게 응답하세요.\n\n"
                "연습을 시작하려면 스페이스",
            )

            practice_trials = []
            for index in range(PRACTICE_TRIALS):
                defect = index % 2
                practice_trials.append(
                    {
                        "condition": "PRACTICE",
                        "far_pct": 25,
                        "limit_s": 3.0,
                        "defect": defect,
                        "alarm": int(random.random() < 0.5),
                        "order_code": make_code(used_codes),
                    }
                )
                practice_trials[-1]["label_code"] = make_label(
                    practice_trials[-1]["order_code"], bool(defect)
                )
            constrained_shuffle(practice_trials)
            practice_correct = run_trials(practice_trials, None, 0, practice=True)
            practice_accuracy = practice_correct / PRACTICE_TRIALS
            if practice_accuracy < PRACTICE_PASS_RATE:
                wait_for_space(
                    win,
                    f"연습 정확도 {practice_accuracy:.0%}입니다.\n"
                    "응답 방법을 다시 확인한 뒤 연습을 한 번 더 진행합니다.\n\n"
                    "계속하려면 스페이스",
                )
                practice_trials = []
                for index in range(PRACTICE_TRIALS):
                    defect = index % 2
                    item = {
                        "condition": "PRACTICE",
                        "far_pct": 25,
                        "limit_s": 3.0,
                        "defect": defect,
                        "alarm": int(random.random() < 0.5),
                        "order_code": make_code(used_codes),
                    }
                    item["label_code"] = make_label(item["order_code"], bool(defect))
                    practice_trials.append(item)
                constrained_shuffle(practice_trials)
                practice_correct = run_trials(practice_trials, None, 0, practice=True)
                if practice_correct / PRACTICE_TRIALS < PRACTICE_PASS_RATE:
                    raise SystemExit(
                        "두 번째 연습에서도 기준에 미달했습니다. 본 시행은 시작하지 않았습니다."
                    )

            wait_for_space(
                win,
                "연습이 끝났습니다. 본 실험은 네 블록으로 진행되며 블록 사이에 휴식합니다.\n"
                "각 블록에서는 40회 응답합니다.\n\n"
                "본 실험을 시작하려면 스페이스",
            )

        file_mode = "a" if is_resume else "w"
        file_encoding = "utf-8" if is_resume else "utf-8-sig"
        with out_path.open(file_mode, newline="", encoding=file_encoding) as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fields)
            if not is_resume:
                writer.writeheader()
            csv_file.flush()
            for block_number, condition_id in enumerate(order, start=1):
                if block_number < resume_start_block:
                    continue
                block_trials = build_block_trials(condition_id, used_codes)
                run_trials(block_trials, writer, block_number, output_stream=csv_file)
                if block_number < len(order):
                    wait_for_space(
                        win,
                        f"{block_number}번째 블록이 끝났습니다.\n"
                        "1분간 휴식한 뒤 스페이스를 눌러 다음 블록을 시작하세요.",
                    )

        wait_for_space(win, "실험이 끝났습니다. 참여해 주셔서 감사합니다.\n\n종료하려면 스페이스")
        print(f"원자료 저장 완료: {out_path}")
    except KeyboardInterrupt:
        print("실험을 중단했습니다. 완료된 본 시행은 CSV에 보존되어 있습니다.")
    except Exception:
        error_text = traceback.format_exc()
        error_path = out_dir / f"{participant_id}_error.txt"
        error_path.write_text(error_text, encoding="utf-8")
        print(error_text, file=sys.stderr)
        try:
            wait_for_space(
                win,
                "실험 중 오류가 발생해 중단했습니다.\n"
                f"오류 기록: data/{error_path.name}\n"
                "완료한 시행은 CSV에 보존했습니다.\n\n"
                "스페이스를 눌러 닫으세요.",
            )
        except Exception:
            pass
    finally:
        tone.stop()
        win.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="물류 코드 검수 실험")
    parser.add_argument(
        "--sound-check",
        action="store_true",
        help="고정된 시스템 음량에서 이어폰 경고음을 확인합니다.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="기존 CSV의 완료된 블록을 보존하고 다음 미완료 블록부터 이어 실행합니다.",
    )
    args = parser.parse_args()
    if args.sound_check:
        run_sound_check()
    else:
        run_experiment(resume=args.resume)


if __name__ == "__main__":
    main()
