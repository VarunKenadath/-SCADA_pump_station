"""
Simple SCADA demo - Water pump station
--------------------------------------
Single-file demo showing the core SCADA loop:
  1. A simulated PLC (Modbus TCP server) holding live process values
  2. A control/physics loop updating those values (the "plant")
  3. A SCADA poller (Modbus TCP client) reading them and printing an HMI view + alarms

Run:
    pip install pymodbus
    python pump_station_scada.py

Modbus holding registers exposed by the "PLC":
    0 - Reservoir level (%)        scaled x10   (875 = 87.5%)
    1 - Pump 1 run state           0 = stopped, 1 = running
    2 - Pump 2 run state           0 = stopped, 1 = running
    3 - Flow rate (L/s)
    4 - Chlorine residual (mg/L)   scaled x100  (45 = 0.45 mg/L)
    5 - Pump 1 runtime (minutes)   used for duty rotation
    6 - Pump 2 runtime (minutes)
"""

import threading
import time
import random
from pymodbus.server import StartTcpServer
from pymodbus.datastore import (
    ModbusSlaveContext,
    ModbusServerContext,
    ModbusSequentialDataBlock,
)
from pymodbus.client import ModbusTcpClient

HOST, PORT = "127.0.0.1", 5020

# Shared datastore - this is the "PLC memory" both threads talk to.
# Initial values: level 50.0%, pumps off, flow 0, chlorine 0.50 mg/L, runtimes 0.
store = ModbusSlaveContext(
    hr=ModbusSequentialDataBlock(0, [500, 0, 0, 0, 50, 0, 0])
)
context = ModbusServerContext(slaves=store, single=True)


def plc_simulation():
    """Physics + control logic running 'inside the PLC' once per second."""
    tick = 0
    while True:
        time.sleep(1)
        tick += 1
        regs = store.getValues(3, 0, count=7)   # 3 = read holding registers
        level = regs[0] / 10.0
        p1, p2 = regs[1], regs[2]
        chlorine = regs[4] / 100.0
        rt1, rt2 = regs[5], regs[6]

        # ---- Duty / standby control logic ----
        # Lead pump = whichever has fewer runtime minutes (rotation).
        lead_is_p1 = rt1 <= rt2

        if level < 30 and not p1 and not p2:
            if lead_is_p1:
                p1 = 1
            else:
                p2 = 1
        if level < 20:                          # lag pump kicks in
            p1, p2 = 1, 1
        if level > 90:                          # both off when full
            p1, p2 = 0, 0

        # ---- Physics: pumps fill, downstream demand drains ----
        level += (p1 + p2) * 1.5 - 1.0
        level = max(0.0, min(100.0, level))

        # Chlorine decays; dosing tops it up when water is moving.
        chlorine += (p1 + p2) * 0.02 - 0.01
        chlorine = max(0.0, min(2.0, chlorine))

        flow = (p1 + p2) * 25 + random.randint(-2, 2)

        # Accumulate runtime every 60 ticks (~1 minute).
        if tick % 60 == 0:
            rt1 += p1
            rt2 += p2

        store.setValues(3, 0, [
            int(level * 10),
            p1, p2,
            max(0, flow),
            int(chlorine * 100),
            rt1, rt2,
        ])


def hmi_poller():
    """SCADA client - polls the PLC, displays values, raises alarms."""
    time.sleep(2)                               # let the server start
    client = ModbusTcpClient(HOST, port=PORT)
    client.connect()

    while True:
        try:
            rr = client.read_holding_registers(address=0, count=7, slave=1)
        except Exception as e:
            print(f"[COMMS ALARM] {e}")
            time.sleep(2)
            continue

        if rr is None or rr.isError():
            print("[COMMS ALARM] Lost connection to PLC")
            time.sleep(2)
            continue

        level = rr.registers[0] / 10.0
        p1, p2 = rr.registers[1], rr.registers[2]
        flow = rr.registers[3]
        cl = rr.registers[4] / 100.0
        rt1, rt2 = rr.registers[5], rr.registers[6]

        alarms = []
        if level > 95: alarms.append("HIGH-HIGH LEVEL")
        if level < 15: alarms.append("LOW-LOW LEVEL")
        if cl < 0.20:  alarms.append("LOW CHLORINE RESIDUAL")

        print(f"\n--- HMI {time.strftime('%H:%M:%S')} ---")
        print(f"  Reservoir level : {level:5.1f} %")
        print(f"  Pump 1 / Pump 2 : {'RUN' if p1 else 'stop'} / {'RUN' if p2 else 'stop'}")
        print(f"  Flow rate       : {flow} L/s")
        print(f"  Chlorine        : {cl:.2f} mg/L")
        print(f"  Runtime hrs P1/P2: {rt1/60:.1f} / {rt2/60:.1f}")
        if alarms:
            print(f"  !! ALARMS       : {', '.join(alarms)}")

        time.sleep(2)


if __name__ == "__main__":
    threading.Thread(target=plc_simulation, daemon=True).start()
    threading.Thread(target=hmi_poller, daemon=True).start()
    print(f"Starting simulated PLC on {HOST}:{PORT} ...  (Ctrl+C to stop)")
    StartTcpServer(context=context, address=(HOST, PORT))
