# Pump Station SCADA Demo

A single-file Python demo of a basic SCADA system for a water pump station. Built as a learning / portfolio piece for a water utility OT engineering role.

The whole stack — simulated PLC, plant physics, control logic, and HMI poller — runs on your laptop in one process, talking over real Modbus TCP.

---

## What is a PLC and what is SCADA?

**PLC (Programmable Logic Controller)** is the industrial computer that sits in the field next to the equipment. It reads sensors (level, flow, pressure), runs control logic on a fast scan cycle, and switches outputs (pumps, valves) on and off. The PLC at a pump station is what *actually* makes the pump start. It works on its own even with no network.

**SCADA (Supervisory Control and Data Acquisition)** is the layer above the PLC. It does not control equipment directly. Its jobs are:

- **Polling** — read data from many PLCs over the network
- **Historian** — log values to a database for trends and reporting
- **HMI (Human-Machine Interface)** — a dashboard so operators can see plant state
- **Alarming** — raise warnings when values cross safe limits
- **Supervisory control** — let operators send setpoints down to PLCs

Short version: **PLC = local muscle, SCADA = control-room eyes and brain.**

---

## What this demo does

It runs three things at once in one Python process:

| Component | Role | How |
|---|---|---|
| Simulated PLC | Holds the live process values in memory | `pymodbus` Modbus TCP **server** on `127.0.0.1:5020` |
| Plant + control logic | Updates values every second (physics + duty/standby control) | Background thread writing to the PLC's registers |
| SCADA poller / HMI | Reads values every 2 s, prints them, raises alarms | `pymodbus` Modbus TCP **client** |

The two halves talk over the same Modbus TCP protocol that's genuinely used in water utilities — so the structure mirrors a real system, just collapsed onto one machine.

### The process being simulated

A raw water reservoir feeds a small treatment plant via two pumps (duty + standby):

- Reservoir level rises when pumps run, drops from downstream demand
- Pump 1 starts when level falls below 30%
- Pump 2 (lag pump) kicks in if level keeps falling below 20%
- Both stop when level reaches 90%
- The pump with fewer runtime hours is chosen as lead (duty rotation)
- Chlorine residual decays over time and is topped up while water moves
- Alarms: high-high level, low-low level, low chlorine residual, comms loss

### Modbus register map exposed by the "PLC"

| Address | Meaning | Scaling |
|---|---|---|
| 0 | Reservoir level (%) | × 10 |
| 1 | Pump 1 run state | 0 / 1 |
| 2 | Pump 2 run state | 0 / 1 |
| 3 | Flow rate (L/s) | raw |
| 4 | Chlorine residual (mg/L) | × 100 |
| 5 | Pump 1 runtime (min) | raw |
| 6 | Pump 2 runtime (min) | raw |

Scaling is normal in real PLCs — Modbus holding registers are 16-bit integers, so floats are sent as `value × 10` or `× 100` and the SCADA side scales back.

---

## Running it

Requires Python 3.9+ and `pymodbus`.

```bash
pip install pymodbus
python pump_station_scada.py
```

You'll see HMI output every 2 seconds:

```
--- HMI 14:03:12 ---
  Reservoir level :  28.4 %
  Pump 1 / Pump 2 : RUN / stop
  Flow rate       : 24 L/s
  Chlorine        : 0.51 mg/L
  Runtime hrs P1/P2: 0.2 / 0.0
```

When level crosses a threshold or chlorine drops, you'll see an alarm line appended.

Stop with `Ctrl+C`.

---

## SCADA concepts demonstrated

- **Field/supervisory split** — server is the PLC, client is SCADA. They communicate only over Modbus TCP, no shared variables. This mirrors real architecture.
- **Polling + scaling** — SCADA reads registers on a fixed cycle and converts scaled integers back to engineering units.
- **Duty/standby with rotation** — runtime-hour-based lead selection, exactly how real water pump stations balance wear.
- **Threshold alarming** — high/low level and water quality limits; chlorine residual is regulated in real water networks.
- **Comms-loss handling** — the poller catches a dropped or errored read and reports it instead of crashing.

---

## Ideas to extend

- Swap the Modbus PLC for an **OPC UA** server using `asyncua` — newer water assets typically use OPC UA.
- Add a **historian**: write each poll cycle to SQLite or InfluxDB.
- Build a real **dashboard** with Streamlit or Dash showing a P&ID-style schematic, live trends, and an alarm banner.
- Add **operator setpoints** — let the SCADA side write back to the PLC (e.g. change the low-level setpoint) using `write_register`.
- Run a **second site** and federate the two — multi-site is a real water utility problem.
- Add **role-based access** on the HMI (operator vs engineer).
