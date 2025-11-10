import os
import io
import base64
from pathlib import Path
import numpy as np
import pandas as pd

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table, Input, Output, State, callback
from dash.exceptions import PreventUpdate
import plotly.graph_objs as go

dash.register_page(__name__, path="/sggui")

# -------- Paths --------
NGSF_BASE = Path(os.environ.get("NGSF_DIR", "/Users/alonakosobokova/superfit/GUIsuperfit/NGSF"))
RESULTS_DIR = Path(os.environ.get("NGSF_RESULTS_DIR", "")) or (NGSF_BASE / "results")

navbar = dbc.NavbarSimple()

# -------- Helpers --------
def _under_root(root: Path, p) -> Path:
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return None
    p = Path(str(p))
    return p if p.is_absolute() else (root / p)

def find_latest_csv_in(folder: Path) -> Path | None:
    if not folder.exists():
        return None
    files = sorted(folder.glob("*.csv"), key=lambda q: q.stat().st_mtime, reverse=True)
    return files[0] if files else None

def read_csv_from_contents(contents: str) -> pd.DataFrame:
    _, content_string = contents.split(",", 1)
    decoded = base64.b64decode(content_string)
    return pd.read_csv(io.StringIO(decoded.decode("utf-8", errors="ignore")))

def ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    required = [
        "SPECTRUM","GALAXY","SN","CONST_SN","CONST_GAL","Z","A_v","Phase",
        "Band","Frac(SN)","Frac(gal)","CHI2/dof","CHI2/dof2","sn_name"
    ]
    for c in required:
        if c not in df.columns:
            df[c] = pd.NA
    order = [
        "SPECTRUM","GALAXY","SN","CONST_SN","CONST_GAL","Z","A_v","Phase",
        "Band","Frac(SN)","Frac(gal)","CHI2/dof","CHI2/dof2","sn_name"
    ]
    return df[[c for c in order if c in df.columns]]

def read_two_col_txt(path: Path) -> pd.DataFrame:
    try:
        df = pd.read_csv(path, delim_whitespace=True, header=None)
    except Exception:
        df = pd.read_csv(path, header=None)
    df = df.select_dtypes(include="number").iloc[:, :2]
    df.columns = ["wav", "flux"]
    return df.dropna()

def normalize_flux(df: pd.DataFrame) -> pd.DataFrame:
    med = np.nanmedian(df["flux"].to_numpy(dtype=float))
    if not np.isfinite(med) or med == 0:
        med = 1.0
    out = df.copy()
    out["flux"] = out["flux"] / med
    return out

def binspec(df: pd.DataFrame, start_w: float, end_w: float, step: float) -> pd.DataFrame:
    xs = np.arange(start_w, end_w, step, dtype=float)
    ys = np.interp(xs, df["wav"].to_numpy(), df["flux"].to_numpy(), left=np.nan, right=np.nan)
    return pd.DataFrame({"wav": xs, "flux": ys})

def _fmt_float(x, nd=3):
    try:
        v = float(x)
    except Exception:
        return "unknown"
    if np.isfinite(v):
        return f"{v:.{nd}f}"
    return "unknown"

def _fmt_pct(x):
    try:
        v = float(x) * 100.0
    except Exception:
        return "unknown"
    if np.isfinite(v):
        return f"{v:.1f}%"
    return "unknown"

# -------- Layout --------

bestfit_card = dbc.Card(
    [
        dbc.CardHeader(html.H4("Best Fit", className="mb-0")),
        dbc.CardBody(id="sggui-bestfit"),
    ],
    className="border-success",
    style={"borderWidth": "2px"},
)
controls = dbc.Card(
    dbc.CardBody(
        [ bestfit_card,
            dbc.Row(
                [
                    dbc.Col(dcc.Upload(id="sggui-upload-csv", children=html.Button("Upload run CSV"), multiple=False), width="auto"),
                    dbc.Col(dbc.Button("Load latest run", id="sggui-load-latest", color="primary"), width="auto"),
                    dbc.Col(html.Small(id="sggui-status", className="text-muted", style={"paddingTop": "8px"})),
                ],
                className="g-2",
            ),
            html.Hr(),
            html.Label("Show graphs:"),
            dcc.Checklist(
                id="sggui-plots",
                options=[
                    {"label": "Observation − Galaxy", "value": "omg"},
                    {"label": "Template", "value": "tem"},
                    {"label": "Galaxy", "value": "gal"},
                    {"label": "Observation", "value": "obs"},
                    {"label": "Normalized Template", "value": "ute"},
                ],
                value=["omg","tem","obs"],
                style={"columnCount": 2},
            ),
            html.Br(),
            html.Label("Binning (Å):"),
            dcc.Input(id="sggui-bin", type="number", value=10, style={"width": "120px"}),
        ]
    ),
    className="shadow-sm",
    style={"position": "sticky", "top": "80px"},
)

graph = dcc.Graph(id="sggui-graph", config={"displayModeBar": False, "responsive": True})

results_table = dash_table.DataTable(
    id="sggui-table",
    columns=[
        {"name": "SPECTRUM", "id": "SPECTRUM"},
        {"name": "GALAXY", "id": "GALAXY"},
        {"name": "SN", "id": "SN"},
        {"name": "CONST_SN", "id": "CONST_SN"},
        {"name": "CONST_GAL", "id": "CONST_GAL"},
        {"name": "Z", "id": "Z"},
        {"name": "A_v", "id": "A_v"},
        {"name": "Phase", "id": "Phase"},
        {"name": "Band", "id": "Band"},
        {"name": "Frac(SN)", "id": "Frac(SN)"},
        {"name": "Frac(gal)", "id": "Frac(gal)"},
        {"name": "CHI2/dof", "id": "CHI2/dof"},
        {"name": "CHI2/dof2", "id": "CHI2/dof2"},
    ],
    data=[],
    editable=False,
    row_selectable="single",
    selected_rows=[],
    style_header={"fontWeight": "bold", "textAlign": "center"},
    style_cell={"padding": "4px", "fontSize": "12px"},
    style_table={"width": "100%", "overflowX": "auto", "border": "thin lightgrey solid"},
)


layout = dbc.Container(
    [
        navbar,
        # Top row: controls + chart
        dbc.Row(
            [
                dbc.Col(controls, md=5, lg=5, xl=4),
                dbc.Col(dbc.Card(dbc.CardBody([graph]), className="shadow-sm"), md=7, lg=7, xl=8),
            ],
            className="mt-3 g-3",
        ),
        # Full-width row: Best Fit + Table
        dbc.Row(
            [
                dbc.Col(
                    [

                        results_table,
                    ],
                    width=12,
                )
            ],
            className="g-3",
        ),
        dcc.Store(id="sggui-results-path", storage_type="local"),
        dcc.Store(id="sggui-results-data", storage_type="memory"),
    ],
    fluid=True,
)

# -------- Callbacks --------
@callback(
    Output("sggui-results-data", "data"),
    Output("sggui-results-path", "data"),
    Output("sggui-status", "children"),
    Output("sggui-table", "data"),
    Output("sggui-table", "columns"),
    Output("sggui-table", "selected_rows"),
    Input("sggui-load-latest", "n_clicks"),
    Input("sggui-upload-csv", "contents"),
    State("sggui-upload-csv", "filename"),
    prevent_initial_call=True,
)
def load_results(n_clicks, uploaded_contents, filename):
    df = None
    src_path = None
    note = ""
    if uploaded_contents is not None:
        try:
            df = read_csv_from_contents(uploaded_contents)
            note = f'Loaded uploaded file "{filename}".'
            src_path = f"<uploaded:{filename}>"
        except Exception as e:
            return PreventUpdate, PreventUpdate, f"Failed to parse upload: {e}", PreventUpdate, PreventUpdate, PreventUpdate
    else:
        latest = find_latest_csv_in(RESULTS_DIR)
        if latest is None:
            return PreventUpdate, PreventUpdate, f"No CSV found in {RESULTS_DIR}", PreventUpdate, PreventUpdate, PreventUpdate
        try:
            df = pd.read_csv(latest)
            note = f"Loaded latest run: {latest.name}"
            src_path = str(latest)
        except Exception as e:
            return PreventUpdate, PreventUpdate, f"Failed to read {latest}: {e}", PreventUpdate, PreventUpdate, PreventUpdate

    df = ensure_columns(df)
    sort_cols = [c for c in ["CHI2/dof", "CHI2/dof2"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(by=sort_cols, ascending=True, kind="mergesort")

    table_cols = [c for c in df.columns if c != "sn_name"]
    columns = [{"name": c, "id": c} for c in table_cols]
    data = df[table_cols].to_dict("records")
    selected = [0] if len(data) > 0 else []
    return df.to_json(orient="split"), src_path, note, data, columns, selected

@callback(
    Output("sggui-graph", "figure"),
    Input("sggui-table", "derived_virtual_selected_rows"),
    State("sggui-table", "data"),
    State("sggui-results-data", "data"),
    State("sggui-plots", "value"),
    State("sggui-bin", "value"),
)
def plot_selected(sel_rows, table_data, json_data, plot_flags, bin_size):
    fig = go.Figure()
    fig.update_layout(
        template="plotly_white",
        xaxis=dict(title="Wavelength", tickformat=".0f"),
        yaxis=dict(title="Normalized Flux"),
        margin=dict(l=30, r=20, t=20, b=40),
        showlegend=True,
        legend=dict(x=0.88, y=0.98, bgcolor="rgba(255,255,255,0.6)"),
        uirevision="sggui",
    )
    if not sel_rows or not table_data or not json_data:
        return fig

    df_all = pd.read_json(json_data, orient="split")
    row = df_all.iloc[sel_rows[0]]

    obs_path = _under_root(NGSF_BASE, row.get("SPECTRUM"))
    gal_rel = None if pd.isna(row.get("GALAXY")) else str(row.get("GALAXY"))
    gal_path = (NGSF_BASE / "bank" / "binnings" / "10A" / "gal" / gal_rel) if gal_rel else None
    sn_path = _under_root(NGSF_BASE, row.get("sn_name"))

    if ("obs" in plot_flags or "omg" in plot_flags) and obs_path and obs_path.exists():
        obs = normalize_flux(read_two_col_txt(obs_path))
        if bin_size:
            obs = binspec(obs, obs["wav"].min(), obs["wav"].max(), bin_size)
        fig.add_trace(go.Scatter(x=obs["wav"], y=obs["flux"], mode="lines",
                                 name="Observation", line=dict(width=2, color="black")))

    if "gal" in plot_flags and gal_path and gal_path.exists():
        gal = read_two_col_txt(gal_path)
        const_gal = row.get("CONST_GAL")
        if pd.notna(const_gal):
            try:
                gal["flux"] = gal["flux"] * float(const_gal)
            except Exception:
                pass
        gal = normalize_flux(gal)
        if bin_size:
            gal = binspec(gal, gal["wav"].min(), gal["wav"].max(), bin_size)
        fig.add_trace(go.Scatter(x=gal["wav"], y=gal["flux"], mode="lines",
                                 name=f"Galaxy ({row.get('GALAXY')})", line=dict(width=2)))

    if ("tem" in plot_flags or "ute" in plot_flags) and sn_path and sn_path.exists():
        sn = read_two_col_txt(sn_path)
        label = "Template"
        if "ute" in plot_flags:
            sn = normalize_flux(sn)
            label = "Normalized Template"
        if bin_size:
            sn = binspec(sn, sn["wav"].min(), sn["wav"].max(), bin_size)
        fig.add_trace(go.Scatter(x=sn["wav"], y=sn["flux"], mode="lines", name=label, line=dict(width=2)))

    if "omg" in plot_flags and obs_path and gal_path and obs_path.exists() and gal_path.exists():
        obs = normalize_flux(read_two_col_txt(obs_path))
        gal = read_two_col_txt(gal_path)
        const_gal = row.get("CONST_GAL")
        if pd.notna(const_gal):
            try:
                gal["flux"] = gal["flux"] * float(const_gal)
            except Exception:
                pass
        gal = normalize_flux(gal)
        gal_interp = np.interp(obs["wav"], gal["wav"], gal["flux"], left=np.nan, right=np.nan)
        omg = pd.DataFrame({"wav": obs["wav"], "flux": obs["flux"] - gal_interp})
        if bin_size:
            omg = binspec(omg, omg["wav"].min(), omg["wav"].max(), bin_size)
        fig.add_trace(go.Scatter(x=omg["wav"], y=omg["flux"], mode="lines",
                                 name="Observation − Galaxy", line=dict(width=2)))
    return fig

@callback(
    Output("sggui-bestfit", "children"),
    Input("sggui-table", "derived_virtual_selected_rows"),
    State("sggui-results-data", "data"),
)
def update_bestfit(sel_rows, json_data):
    if not json_data:
        return ""
    df_all = pd.read_json(json_data, orient="split")
    idx = sel_rows[0] if sel_rows else 0
    if idx >= len(df_all):
        idx = 0
    row = df_all.iloc[idx]

    sn_type = row.get("SN", "unknown")
    host = row.get("GALAXY", "unknown")
    z = _fmt_float(row.get("Z"), nd=4)
    av = _fmt_float(row.get("A_v"), nd=2)
    frac_sn = _fmt_pct(row.get("Frac(SN)"))
    chi = _fmt_float(row.get("CHI2/dof"), nd=2)

    return html.Div(
        [
            html.P([html.Strong("Supernova Type: "), html.Span(str(sn_type))]),
            html.P([html.Strong("Host Galaxy: "), html.Span(str(host))]),
            html.P([html.Strong("Redshift (z): "), html.Span(z)]),
            html.P([html.Strong("Extinction (A_v): "), html.Span(av)]),
            html.P([html.Strong("SN Contribution: "), html.Span(frac_sn)]),
            html.P([html.Strong("Chi-squared: "), html.Span(chi)]),
        ],
        className="mb-0",
    )
