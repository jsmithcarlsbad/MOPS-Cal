# Coil driver — Mermaid review diagrams

Open this file in Cursor / VS Code and use **Markdown: Open Preview** (`Ctrl+Shift+V`) to render Mermaid.  
Requires the **Markdown Preview Mermaid Support** extension (`bierner.markdown-mermaid`), listed in `.vscode/extensions.json`.

These are **block diagrams** for design review, not a formal netlist. Values (e.g. **200 Ω**, **50 Ω**) are placeholders — match your BOM.

---

## Power and one DRV8871 (unipolar-style control)

```mermaid
flowchart TB
  subgraph Supply["12 V brick"]
    V12["+12 V VM"]
    PGND["PGND / GND"]
  end

  subgraph DRV["DRV8871 (one axis module)"]
    IN1["IN1 ← PWM GPIO"]
    IN2["IN2 ← fixed LO"]
    HB["H-bridge"]
    OUT1["OUT1"]
    OUT2["OUT2"]
    IN1 --> HB
    IN2 --> HB
    HB --> OUT1
    HB --> OUT2
  end

  V12 --> DRV
  DRV --> PGND
  OUT1 --> NET["To load network"]
  OUT2 --> PGND
```

*Wiring of OUT1/OUT2 to load depends on your breakout — some tie one output to PGND.*

---

## Per-axis analog path (COIL_DRIVER order + your D_SER / D_FB)

```mermaid
flowchart LR
  subgraph LoadPath["Series path (current I)"]
    direction LR
    OUT["Bridge output"]
    DSER["D_SER Schottky<br/>A from bridge, K out"]
    RSER["R_series<br/>e.g. 200 Ω"]
    RC["RC low-pass<br/>R∥C to GND"]
    INP["INA3221 IN+"]
    RSH["R_SHUNT<br/>e.g. 0.1 Ω"]
    INM["INA3221 IN−"]
    L["Helmholtz coil L"]
    RRET["R_return<br/>e.g. 50 Ω"]
    GND["GND"]

    OUT --> DSER --> RSER --> RC --> INP --> RSH --> INM --> L --> RRET --> GND
  end
```

---

## Flyback diode across coil (parallel branch)

Mermaid has no true “two-terminal in parallel” primitive; treat this as a **wiring intent** sketch.

```mermaid
flowchart LR
  subgraph Parallel["Same two nodes: coil ‖ D_FB"]
    direction TB
    N1["Node A: coil + / shunt load side"]
    N2["Node B: coil −"]
    N1 --- W["Coil winding"]
    W --- N2
    N1 --- K["D_FB cathode K"]
    K --- A["D_FB anode A"]
    A --- N2
  end

  N2 --> RRET["R_return → GND"]
```

*Polarity must match DC direction: **K** toward the more positive coil terminal, **A** toward the return side so freewheel current circulates when the bridge stops sourcing.*

---

## INA3221 — three channels on one I²C device

```mermaid
flowchart TB
  subgraph INA["TI INA3221"]
    CH0["CH0: IN+0 / IN−0 / bus 0"]
    CH1["CH1: IN+1 / IN−1 / bus 1"]
    CH2["CH2: IN+2 / IN−2 / bus 2"]
  end

  subgraph Pico["Raspberry Pi Pico 2 W"]
    I2C["I2C0 SDA/SCL<br/>typ. GP4 / GP5"]
  end

  I2C <--> INA

  Xpath["X-axis shunt"] --> CH0
  Ypath["Y-axis shunt"] --> CH1
  Zpath["Z-axis shunt"] --> CH2
```

---

## Pico ↔ DRV8871 GPIO (default `config.py`)

```mermaid
flowchart LR
  subgraph X["Axis X"]
    GP10["GP10 PWM → IN1"]
    GP11["GP11 LO → IN2"]
  end

  subgraph Y["Axis Y"]
    GP12["GP12 PWM → IN1"]
    GP13["GP13 LO → IN2"]
  end

  subgraph Z["Axis Z"]
    GP14["GP14 PWM → IN1"]
    GP15["GP15 LO → IN2"]
  end

  Pico["RP2040"] --> X
  Pico --> Y
  Pico --> Z
```

---

## Full axis — single diagram (conceptual)

```mermaid
flowchart TB
  V12["+12 V VM"] --> DRV["DRV8871"]
  PGND["PGND"] --> DRV

  DRV -->|OUT| DSER["D_SER"]
  DSER --> RSER["R_series"]
  RSER --> RC["RC filter"]
  RC --> SHP["INA IN+"]
  SHP --> RSH["R_shunt"]
  RSH --> SHM["INA IN−"]
  SHM --> COIL["Coil L"]
  COIL --> RRET["R_return"]
  RRET --> PGND

  COIL -.->|parallel| DFB["D_FB across L"]

  Pico["Pico PWM/GPIO"] -.->|control| DRV
  Pico <-.->|I2C| INA["INA3221"]
  SHP & SHM -.-> INA
```
