import asyncio
import csv
import json
import os
import random
import sys
import time
from datetime import datetime
import websockets

# FSUIPC7 WebSocket Verified Settings
FSUIPC_WS_URI = "ws://localhost:2048/fsuipc/"
SUBPROTOCOLS = ["fsuipc"]

# FSUIPC WASM RPN Offset Settings
OFFSET_WASM_RPN = int("0x7C50", 16)  # 31824
GROUP_NAME = "A310ControlGroup"
VAR_NAME = "rpn_buffer"

# iniBuilds A310 Flight Profile & Target Settings (FL120 - FL240)
TARGET_LVAR = "A310_Airspeed_Dial"
MIN_SPEED_KTS = 250
MAX_SPEED_KTS = 315
MIN_SPEED_DELTA = 12       # Minimum change required per event
SEC_PER_KNOT_DELTA = 1.2   # ~30s transition for a 25kt shift
MIN_PAD_SEC = 15           # Buffer hold time after target speed is reached
MAX_PAD_SEC = 150


async def declare_rpn_group(ws) -> bool:
    """Declares the 0x7C50 WASM string buffer group with FSUIPC WebSocket server."""
    payload = {
        "command": "offsets.declare",
        "name": GROUP_NAME,
        "offsets": [
            {
                "name": VAR_NAME,
                "address": OFFSET_WASM_RPN,
                "type": "string",
                "size": 256,
            }
        ],
    }
    try:
        await ws.send(json.dumps(payload))
        res_raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
        res = json.loads(res_raw)
        return res.get("success", False)
    except Exception as err:
        print(f"[ERROR] Group declaration failed: {err}")
        return False


async def send_rpn_command(ws, rpn_code: str):
    """Dispatches RPN Calculator Code via declared FSUIPC offset group."""
    payload = {
        "command": "offsets.write",
        "name": GROUP_NAME,
        "offsets": [
            {
                "name": VAR_NAME,
                "value": rpn_code,
            }
        ],
    }
    try:
        await ws.send(json.dumps(payload))
        # Drain the ACK response frame from FSUIPC to keep socket buffer clean
        await asyncio.wait_for(ws.recv(), timeout=2.0)
    except Exception as err:
        print(f"[ERROR] Failed to dispatch RPN command: {err}")


async def main():
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_filename = os.path.join(SCRIPT_DIR, f"ap_speed_log_{timestamp_str}.csv")

    headers = ["Timestamp", "AP_Target_Speed_Kts", "Speed_Delta_Kts", "Event_Count"]

    csv_file = open(csv_filename, mode='w', newline='', buffering=1)
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(headers)

    print("=====================================================")
    print("  MSFS2020 Dynamic Speed Disruptor (A310 / WebSocket)")
    print("=====================================================")
    print(f"Connecting to FSUIPC7 at {FSUIPC_WS_URI}...")

    ws = None
    for attempt in range(1, 6):
        try:
            ws = await websockets.connect(
                FSUIPC_WS_URI, subprotocols=SUBPROTOCOLS, open_timeout=5
            )
            print("-> [CONNECTED] FSUIPC7 WebSocket Handshake successful!")
            break
        except Exception as e:
            print(f"   [Attempt {attempt}/5] Waiting for server... ({e})")
            await asyncio.sleep(2.0)

    if ws is None:
        print("\n[CONNECTION FAILED]")
        print("Ensure FSUIPC7 and MSFS2020 are running.")
        csv_file.close()
        input("\nPress Enter to exit...")
        return

    # Register Offset Group
    print("-> Registering WASM RPN Offset Group (0x7C50)...")
    if not await declare_rpn_group(ws):
        print("[CRITICAL ERROR] Failed to declare offset group with FSUIPC.")
        csv_file.close()
        await ws.close()
        input("\nPress Enter to exit...")
        return
    print("-> Offset Group registered successfully!")

    # Startup pause setup
    STARTUP_DELAY_SEC = 60
    print(
        f"\n[STARTUP PAUSE] Holding for {STARTUP_DELAY_SEC} seconds to allow cockpit setup..."
    )

    try:
        for remaining in range(STARTUP_DELAY_SEC, 0, -1):
            sys.stdout.write(
                f"\r  Disruptor active in: {remaining:2d}s (Press Ctrl+C to cancel)... "
            )
            sys.stdout.flush()
            await asyncio.sleep(1)
        print("\n")
    except asyncio.CancelledError:
        print("\n\n[CANCELLED] Script aborted during setup pause.")
        csv_file.close()
        await ws.close()
        return

    # Initial state setup
    current_target_speed = 293
    await send_rpn_command(ws, f"{current_target_speed} (>L:{TARGET_LVAR})")

    event_count = 0
    csv_writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3], current_target_speed, 0, event_count])
    csv_file.flush()

    print(f"[DISRUPTOR ACTIVE]")
    print(f"  Target Variable : L:{TARGET_LVAR}")
    print(f"  Initial AP Speed: {current_target_speed} kts")
    print("\nPress Ctrl+C in this window to stop.\n")

    try:
        while True:
            # 1. Pick a new target speed with a meaningful delta
            new_speed = current_target_speed
            while abs(new_speed - current_target_speed) < MIN_SPEED_DELTA:
                new_speed = random.randint(MIN_SPEED_KTS, MAX_SPEED_KTS)

            speed_delta = abs(new_speed - current_target_speed)

            # 2. Dynamic interval: transition time + random buffer
            transition_time = speed_delta * SEC_PER_KNOT_DELTA
            random_buffer = random.randint(MIN_PAD_SEC, MAX_PAD_SEC)
            total_interval = round(transition_time + random_buffer, 1)

            # 3. Dispatch RPN to A310 FCU
            rpn_cmd = f"{new_speed} (>L:{TARGET_LVAR})"
            await send_rpn_command(ws, rpn_cmd)

            now = datetime.now().strftime("%H:%M:%S")
            event_count += 1
            csv_writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3], new_speed, speed_delta, event_count])
            csv_file.flush()

            print(
                f"[{now}] Event #{event_count}: Target Speed -> {new_speed} kts (Δ {speed_delta} kts) | Holding {total_interval}s"
            )

            current_target_speed = new_speed

            # 4. Non-blocking hold loop
            await asyncio.sleep(total_interval)

    except (KeyboardInterrupt, asyncio.CancelledError):
        print(f"\n\n[STOPPED] Disruptor closed after {event_count} speed changes.")
    finally:
        csv_file.close()
        await ws.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as err:
        print(f"\n\n[CRITICAL ERROR] Script crashed: {err}")
        input("\nPress Enter to exit...")
