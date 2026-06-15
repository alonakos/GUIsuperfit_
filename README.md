# GUIsuperfit

A two-page Dash interface for running and inspecting Superfit spectrum fitting results.
<img width="1904" height="941" alt="Screenshot 2026-06-15 at 10 32 50 AM" src="https://github.com/user-attachments/assets/19ac4481-ff02-479a-8e2b-ffabf9f1a137" />
<img width="1720" height="949" alt="Screenshot 2026-06-15 at 10 33 54 AM" src="https://github.com/user-attachments/assets/e4311825-b3d0-4065-928e-862630ef664a" />



## Overview

This application provides:
- **Input Page (sfgui):** Upload a spectrum `.dat` file, configure parameters, and run Superfit.
- **Output Page (sggui):** Visualize the fit results and review generated CSV outputs stored under `NGSF`.

The tool uses the **Superfit** package together with modern Dash UI components.

---

## Requirements


If you do not have `uv` installed:
```bash
pip install uv
 or
curl -LsSf https://astral.sh/uv/install.sh | sh

git clone git@github.com:alonakos/GUIsuperfit.git
cd GUIsuperfit

uv venv .venv
source .venv/bin/activate


uv pip install .


python GUISuperfit/mergedapp/app.py

Open 
http://127.0.0.1:8050/
