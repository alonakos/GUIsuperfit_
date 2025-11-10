import os
import json
import base64
import io
import subprocess
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, callback
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import pandas as pd
import plotly.graph_objects as go
import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, callback
from dash.dependencies import Input, Output, State, ALL, MATCH
from dash.exceptions import PreventUpdate

# Page registration
dash.register_page(__name__, path="/sfgui")

BASE_DIR = Path("/Users/alonakosobokova/superfit/GUIsuperfit/NGSF")
UPLOAD_DIR = BASE_DIR

navbar = dbc.NavbarSimple(
)

sn_categories = {
    "IA": ["Ia 02es-like", "Ia-02cx like", "Ia-CSM-(ambigious)", "Ia 91T-like", "Ia-CSM", "Ia-norm", "Ia 91bg-like", "Ia-rapid"],
    "IB": ["Ib", "Ca-Ib"],
    "II": ["IIb-flash", "II", "IIb", "II-flash", "ILRT"],
    "SLSN": ["SLSN-II", "SLSN-IIn", "SLSN-I", "SLSN-Ib", "SLSN-IIb"],
    "Other": [
        "computed", "TDE He", "Ca-Ia", "super_chandra", "IIn", "FBOT", "Ibn", "TDE H",
        "SN - Imposter", "TDE H+He", "Ic", "Ia-pec", "Ic-BL", "Ic-pec"
    ],
}
sn_options = [{"label": k, "value": k} for k in sn_categories.keys()]
for v in sn_categories.values():
    sn_options.extend([{"label": f"  {x}", "value": x} for x in v])

_sn_subtype_options = [{"label": s, "value": s} for subs in sn_categories.values() for s in subs]
_default_subtypes = ["Ia-norm", "Ia 91bg-like"]
_default_cats = ["IA"]

galaxy_options = [
    {"label": "E", "value": "E"},
    {"label": "S0", "value": "S0"},
    {"label": "Sa", "value": "Sa"},
    {"label": "Sb", "value": "Sb"},
    {"label": "Sc", "value": "Sc"},
    {"label": "SB1", "value": "SB1"},
    {"label": "SB2", "value": "SB2"},
    {"label": "SB3", "value": "SB3"},
    {"label": "SB4", "value": "SB4"},
    {"label": "SB5", "value": "SB5"},
    {"label": "SB6", "value": "SB6"},
]

known_redshift_tab = dbc.Card(
    dbc.CardBody(
        dbc.Row(
            [
                dbc.Col(html.Label("z"), width="auto"),
                dbc.Col(dbc.Input(id="sfgui-z-known", type="number", size="sm"), width=5),
            ],
            className="align-items-center",
        )
    ),
    className="mt-1",
)
redshift_range_tab = dbc.Card(
    dbc.CardBody(
        dbc.Row(
            [
                dbc.Col(html.Label("z1"), width="auto"),
                dbc.Col(dbc.Input(id="sfgui-z1", type="number", size="sm"), width=2),
                dbc.Col(html.Label("z2"), width="auto"),
                dbc.Col(dbc.Input(id="sfgui-z2", type="number", size="sm"), width=2),
                dbc.Col(html.Label("dz"), width="auto"),
                dbc.Col(dbc.Input(id="sfgui-dz", type="number", size="sm"), width=2),
            ],
            className="align-items-center",
        )
    ),
    className="mt-1",
)
z_tabs = dbc.Tabs(
    [
        dbc.Tab(known_redshift_tab, label="Known redshift"),
        dbc.Tab(redshift_range_tab, label="Redshift range"),
    ]
)

uploader = html.Div(
    [
        dcc.Upload(
            id="sfgui-upload",
            children=html.Div(["Drag and Drop or ", html.A("Select spectrum .dat")]),
            style={
                "width": "100%",
                "height": "60px",
                "lineHeight": "60px",
                "borderWidth": "1px",
                "borderStyle": "dashed",
                "borderRadius": "5px",
                "textAlign": "center",
                "margin": "2px",
            },
            accept=".dat,.txt",
            multiple=False,
        ),
        html.Small(id="sfgui-upload-status"),
    ]
)

def _sn_accordion():
    content = []
    for category, subs in sn_categories.items():
        content.append(
            html.Div(
                [
                    html.Div(
                        dbc.Checkbox(
                            id={"type": "sn-cat-toggle", "category": category},
                            value=(category in _default_cats),
                            label=html.Strong(category),
                        ),
                        style={"marginBottom": "5px"},
                    ),
                    dbc.Checklist(
                        id={"type": "sn-subtypes", "category": category},
                        options=[{"label": s, "value": s} for s in subs],
                        value=(subs if category in _default_cats else [s for s in subs if s in _default_subtypes]),
                        inline=True,
                    ),
                    html.Hr(),
                ],
                style={"marginBottom": "10px"},
            )
        )

    hidden_bridge = dcc.Checklist(
        id="sfgui-sn-types",
        options=_sn_subtype_options,
        value=_default_subtypes,
        style={"display": "none"},
    )

    return html.Div(
        [
            html.Label("Supernova types", style={"fontWeight": "bold"}),
            html.Div(content),
            hidden_bridge,
            html.Hr(),
        ]
    )

# ---------- controls left column ----------
sn_checklist = dbc.Card(
    dbc.CardBody(
        [
            _sn_accordion(),
            html.Label("Epoch Range Slider"),
            dcc.RangeSlider(
                id="sfgui-epoch-range",
                min=-100,
                max=700,
                step=5,
                value=[-30, 171],
                marks={i: str(i) for i in range(-100, 701, 100)},
                allowCross=False,
                pushable=5,
                tooltip={"placement": "bottom", "always_visible": False},
            ),
            html.Small(id="sfgui-epoch-label"),
            html.Hr(),
            html.Label("Galaxies"),
            dbc.Checklist(id="sfgui-galaxies", options=galaxy_options, value=["E", "S0", "Sa", "Sb", "Sc"], inline=True),
            html.Div(
                [
                    dbc.Row(
                        [
                            dbc.Col(dbc.Input(id="sfgui-a-hi", type="number", placeholder="A_hi"), width=4),
                            dbc.Col(dbc.Input(id="sfgui-a-lo", type="number", placeholder="A_lo"), width=4),
                            dbc.Col(dbc.Input(id="sfgui-a-int", type="number", placeholder="A_i"), width=4),
                        ]
                    )
                ],
                className="mt-2",
            ),
        ]
    ),
    className="mt-2",
)

spectrum_graph = dcc.Graph(
    id="sfgui-graph",
    config={"displayModeBar": False, "responsive": True},
    style={"height": "60vh"},  
)

wavelength_slider = html.Div(
    [
        html.Label("Wavelength Range Slider"),
        dcc.RangeSlider(
            id="sfgui-wave-range",
            min=3000,
            max=10000,
            value=[3000, 10000],
            step=10,
            marks={i: str(i) for i in range(3000, 10001, 1000)},
            allowCross=False,
            updatemode="mouseup",         
            tooltip={"placement": "bottom", "always_visible": False},
        ),
        html.Small(id="sfgui-wave-label"),
    ],
    className="mt-2",
)


btn_generate = dbc.Button("Generate JSON", color="secondary", id="sfgui-generate", className="mr-1")
btn_run = dbc.Button("Run Fit", color="primary", id="sfgui-run", className="mr-1")
btn_clear = dbc.Button("Clear", color="danger", id="sfgui-clear", className="mr-1")

json_output = html.Pre(id="sfgui-json", style={"whiteSpace": "pre-wrap", "maxHeight": "35vh", "overflowY": "auto"})
download_json = dcc.Download(id="sfgui-download")


store_filename = dcc.Store(id="sfgui-store-fn", storage_type="session")
store_df = dcc.Store(id="sfgui-store-df", storage_type="session")
store_wave_bounds = dcc.Store(id="sfgui-store-wave", storage_type="session")


layout = html.Div(
    [
        navbar,
        store_filename,
        store_df,
        store_wave_bounds,
        dbc.Container(
            [
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                uploader,
                                z_tabs,
                                sn_checklist,
                                html.Div([btn_run, btn_generate, btn_clear, download_json], className="mt-2"),
                                dbc.Card([dbc.CardHeader("Parameters JSON"), dbc.CardBody(dcc.Loading(json_output))], className="mt-3"),
                            ],
                            md=5,
                        ),
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardBody(
                                            [
                                                spectrum_graph,
                                                wavelength_slider,
                                            ]
                                        )
                                    ]
                                )
                            ],
                            md=7,
                        ),
                    ],
                    className="mt-3",
                ),
            ],
            fluid=True,
        ),
    ]
)

def _build_params(filename, z_known, z1, z2, dz, sn_types, epoch_range, galaxies, a_hi, a_lo, a_int):
    return {
        "object_to_fit": filename if filename else "spectrum.dat",
        "use_exact_z": 1 if z_known is not None else 0,
        "z_exact": float(z_known) if z_known is not None else 0.05,
        "z_range_begin": float(z1) if z1 is not None else 0.0,
        "z_range_end": float(z2) if z2 is not None else 0.1,
        "z_int": float(dz) if dz is not None else 0.01,
        "resolution": 10,
        "lower_lam": 3000,
        "upper_lam": 10000,
        "saving_results_path": str(BASE_DIR),
        "pkg_dir": str(BASE_DIR),
        "temp_gal_tr": galaxies or ["E", "S0", "Sa", "Sb", "Sc"],
        "temp_sn_tr": sn_types or ["Ia", "Ib", "Ic", "II"],
        "mask_galaxy_lines": False,
        "mask_telluric": False,
        "error_spectrum": "sg",
        "minimum_overlap": 0.5,
        "epoch_low": int(epoch_range[0]) if epoch_range else -20,
        "epoch_high": int(epoch_range[1]) if epoch_range else 300,
        "Alam_low": float(a_lo) if a_lo is not None else 0.0,
        "Alam_high": float(a_hi) if a_hi is not None else 3.0,
        "Alam_interval": float(a_int) if a_int is not None else 0.1,
        "show_plot": False,
        "show_plot_png": True,
        "how_many_plots": 5,
    }

def _parse_dat(contents, filename):
    _, content_string = contents.split(",")
    data = base64.b64decode(content_string)
    text = data.decode("utf-8", errors="ignore")
    buf = io.StringIO(text)
    try:
        df = pd.read_csv(buf, delim_whitespace=True, comment="#", header=None, names=["wavelength", "flux"])
    except Exception:
        buf.seek(0)
        df = pd.read_csv(buf, sep=",", comment="#", header=None, names=["wavelength", "flux"])
    df = df.dropna()
    dest = UPLOAD_DIR / filename
    with open(dest, "wb") as f:
        f.write(data)
    return df

@callback(
    Output("sfgui-upload-status", "children"),
    Output("sfgui-store-fn", "data"),
    Output("sfgui-store-df", "data"),
    Output("sfgui-store-wave", "data"),
    Input("sfgui-upload", "contents"),
    State("sfgui-upload", "filename"),
    prevent_initial_call=True,
)
def upload_file(contents, filename):
    if contents is None:
        raise PreventUpdate
    if not filename:
        return "No file selected", None, None, None
    df = _parse_dat(contents, filename)
    if df.empty:
        return "File parsed as empty", None, None, None
    wmin = float(df["wavelength"].min())
    wmax = float(df["wavelength"].max())
    status = f'File "{filename}" uploaded successfully to {UPLOAD_DIR}'
    return status, filename, df.to_json(orient="split"), {"min": wmin, "max": wmax}

@callback(
    Output("sfgui-wave-range", "min"),
    Output("sfgui-wave-range", "max"),
    Output("sfgui-wave-range", "value"),
    Output("sfgui-wave-label", "children"),
    Input("sfgui-store-wave", "data"),
    prevent_initial_call=True,
)
def init_wave_slider(bounds):
    if not bounds:
        raise PreventUpdate
    mn = max(3000, int(round(bounds["min"])))
    mx = min(10000, int(round(bounds["max"])))
    val = [mn, mx]
    return mn, mx, val, f"Wavelength range [{val[0]}, {val[1]}]"

@callback(
    Output("sfgui-epoch-label", "children"),
    Input("sfgui-epoch-range", "value"),
)
def epoch_label(v):
    if not v:
        raise PreventUpdate
    return f"Epoch range [{v[0]}, {v[1]}]"

@callback(
    Output("sfgui-graph", "figure"),
    Input("sfgui-store-df", "data"),
    Input("sfgui-wave-range", "value"),
    State("sfgui-store-fn", "data"),
)
def update_graph(df_json, wave_range, filename):
    fig = go.Figure()
    fig.update_layout(
        template="plotly_white",
        xaxis=dict(title="Wavelength", tickformat=".0f"),
        yaxis=dict(title="Normalized Flux"),
        margin=dict(l=30, r=20, t=20, b=40),
        showlegend=True,
        legend=dict(x=0.88, y=0.98, bgcolor="rgba(255,255,255,0.6)"),
        uirevision="spectrum",   # <-- add
    )

    if not df_json:
        return fig

    # Load and normalize flux by median, robust to zeros/NaNs
    df = pd.read_json(df_json, orient="split")
    med = pd.to_numeric(df["flux"], errors="coerce").median()
    if pd.isna(med) or med == 0:
        med = 1.0
    df = df.copy()
    df["flux"] = df["flux"] / med

    # Apply wavelength window if provided
    if wave_range:
        df = df[(df["wavelength"] >= wave_range[0]) & (df["wavelength"] <= wave_range[1])]

    # Plot single normalized spectrum
    fig.add_trace(
        go.Scatter(
            x=df["wavelength"],
            y=df["flux"],
            mode="lines",
            name=filename or "spectrum",
            line=dict(width=2, color="black"),
        )
    )

    return fig

@callback(
    Output("sfgui-json", "children"),
    Output("sfgui-download", "data"),
    Input("sfgui-generate", "n_clicks"),
    State("sfgui-z-known", "value"),
    State("sfgui-z1", "value"),
    State("sfgui-z2", "value"),
    State("sfgui-dz", "value"),
    State("sfgui-sn-types", "value"),
    State("sfgui-epoch-range", "value"),
    State("sfgui-galaxies", "value"),
    State("sfgui-a-hi", "value"),
    State("sfgui-a-lo", "value"),
    State("sfgui-a-int", "value"),
    State("sfgui-store-fn", "data"),
    prevent_initial_call=True,
)
def generate_json(n, z_known, z1, z2, dz, sn_types, epoch_range, galaxies, a_hi, a_lo, a_int, filename):
    if not n:
        raise PreventUpdate
    params = _build_params(filename, z_known, z1, z2, dz, sn_types, epoch_range, galaxies, a_hi, a_lo, a_int)
    text = json.dumps(params, indent=4)
    with open(BASE_DIR / "parameters.json", "w") as f:
        f.write(text)
    return text, dict(content=text, filename="parameters.json")

@callback(
    Output("sfgui-json", "children", allow_duplicate=True), 
    Input("sfgui-run", "n_clicks"),
    State("sfgui-z-known", "value"),
    State("sfgui-z1", "value"),
    State("sfgui-z2", "value"),
    State("sfgui-dz", "value"),
    State("sfgui-sn-types", "value"),
    State("sfgui-epoch-range", "value"),
    State("sfgui-galaxies", "value"),
    State("sfgui-a-hi", "value"),
    State("sfgui-a-lo", "value"),
    State("sfgui-a-int", "value"),
    State("sfgui-store-fn", "data"),
    prevent_initial_call=True,
)
def run_fit(n, z_known, z1, z2, dz, sn_types, epoch_range, galaxies, a_hi, a_lo, a_int, filename):
    if not n:
        raise PreventUpdate
    params = _build_params(filename, z_known, z1, z2, dz, sn_types, epoch_range, galaxies, a_hi, a_lo, a_int)
    json_string = json.dumps(params)
    try:
        os.chdir(str(BASE_DIR))
        result = subprocess.run(["python", "run.py", json_string], capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return "Error: Process timed out after 3 minutes"
    except Exception as e:
        return f"Error: {e}"
    if result.returncode == 0:
        return f"SUCCESS!"
    return f"FAILED!Errors:\n{result.stderr}"

@callback(
    Output("sfgui-z-known", "value"),
    Output("sfgui-z1", "value"),
    Output("sfgui-z2", "value"),
    Output("sfgui-dz", "value"),
    Output("sfgui-sn-types", "value", allow_duplicate=True),
    Output("sfgui-epoch-range", "value", allow_duplicate=True),
    Output("sfgui-galaxies", "value", allow_duplicate=True),
    Output("sfgui-a-hi", "value", allow_duplicate=True),
    Output("sfgui-a-lo", "value", allow_duplicate=True),
    Output("sfgui-a-int", "value", allow_duplicate=True),
    Output("sfgui-store-fn", "data", allow_duplicate=True),
    Output("sfgui-store-df", "data", allow_duplicate=True),
    Output("sfgui-store-wave", "data", allow_duplicate=True),
    Output("sfgui-upload-status", "children", allow_duplicate=True),
    Output("sfgui-json", "children", allow_duplicate=True),
    Input("sfgui-clear", "n_clicks"),
    prevent_initial_call=True,
)
def clear_all(n):
    if not n:
        raise PreventUpdate
    return (
        None, None, None, None,
        ["Ia-norm", "Ia 91bg-like"],
        [-30, 171],
        ["E", "S0", "Sa", "Sb", "Sc"],
        None, None, None,
        None, None, None, ""
    )

@callback(
    Output({"type": "sn-subtypes", "category": MATCH}, "value"),
    Input({"type": "sn-cat-toggle", "category": MATCH}, "value"),
    State({"type": "sn-subtypes", "category": MATCH}, "options"),
)
def _cat_controls_subtypes(cat_checked, options):
    if not options:
        raise PreventUpdate
    all_vals = [o["value"] for o in options]
    return all_vals if cat_checked else []


@callback(
    Output("sfgui-sn-types", "value", allow_duplicate=True),
    Input({"type": "sn-subtypes", "category": ALL}, "value"),
    prevent_initial_call=True,  
)
def _aggregate_selected(all_values):
    final = sorted({s for lst in (all_values or []) for s in (lst or [])})
    return final
