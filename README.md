# GUIsuperfit

A two-page Dash interface for running and inspecting Superfit spectrum fitting results.

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
