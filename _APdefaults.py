import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    print("[ERROR] 'websockets' library missing. Run: pip install websockets")
    sys.exit(1)

# FSUIPC7 WebSocket Settings
FSUIPC_WS_URI = "ws://localhost:2048/fsuipc/"
SUBPROTOCOLS = ["fsuipc"]
OFFSET_WASM_RPN = int("0x7C50", 16)  # 31824
GROUP_NAME = "A310ControlGroup"
VAR_NAME = "rpn_buffer"


async def main():
    print("Connecting to FSUIPC7 WebSocket Server...")
    try:
        async with websockets.connect(
            FSUIPC_WS_URI, subprotocols=SUBPROTOCOLS, open_timeout=5
        ) as ws:
            print("-> [CONNECTED] Handshake successful!")

            # Step 1: Declare Group Offset
            payload_declare = {
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
            await ws.send(json.dumps(payload_declare))
            res_raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
            parsed = json.loads(res_raw)

            if not parsed.get("success", False):
                print("[ERROR] Group declaration failed.")
                return

            await asyncio.sleep(0.2)

            # Step 2: Dispatch RPN Command (Speed=293, Alt=30000, Heading=0)
            rpn_code = (
                "293 (>L:A310_Airspeed_Dial) "
                "30000 (>L:A310_Altitude_Dial) 30000 (>K:AP_ALT_VAR_SET_ENGLISH) "
                "0 (>L:A310_Heading_Dial) 0 (>K:HEADING_BUG_SET)"
            )

            payload_write = {
                "command": "offsets.write",
                "name": GROUP_NAME,
                "offsets": [
                    {
                        "name": VAR_NAME,
                        "value": rpn_code,
                    }
                ],
            }
            await ws.send(json.dumps(payload_write))
            await asyncio.wait_for(ws.recv(), timeout=3.0)
            print("-> [SUCCESS] Dispatched AP Targets: Speed=293kt | Alt=FL300 | Hdg=000°")

    except Exception as err:
        print(f"[CRITICAL ERROR] Connection or dispatch failed: {err}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    # Persistent window input prompt intentionally omitted for clean auto-close
