import os
import json
import base64
import io
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, callback
from dash.dependencies import Input, Output, State, ALL
from dash.exceptions import PreventUpdate
import pandas as pd
import plotly.graph_objects as go


dash.register_page(__name__, path="/sfgui")

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = PACKAGE_ROOT.parent
DEFAULT_NGSF_DIR = PROJECT_ROOT / "NGSF"

BASE_DIR = Path(os.environ.get("NGSF_DIR", str(DEFAULT_NGSF_DIR))).resolve()
UPLOAD_DIR = Path(os.environ.get("NGSF_UPLOAD_DIR", str(BASE_DIR))).resolve()
RESULTS_DIR = Path(os.environ.get("NGSF_RESULTS_DIR", str(BASE_DIR / "results"))).resolve()

LOWER_LAM = 3000
UPPER_LAM = 10000
DEFAULT_EPOCH_RANGE = [-30, 171]

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

navbar = dbc.NavbarSimple()

sn_categories = {
    "IA": ["Ia 02es-like", "Ia-02cx like", "Ia-CSM-(ambigious)", "Ia 91T-like", "Ia-CSM",
           "Ia-norm", "Ia 91bg-like", "Ia-rapid"],
    "IB": ["Ib", "Ca-Ib"],
    "II": ["IIb-flash", "II", "IIb", "II-flash", "ILRT"],
    "SLSN": ["SLSN-II", "SLSN-IIn", "SLSN-I", "SLSN-Ib", "SLSN-IIb"],
    "Other": [
        "computed", "TDE He", "Ca-Ia", "super_chandra", "IIn", "FBOT", "Ibn", "TDE H",
        "SN - Imposter", "TDE H+He", "Ic", "Ia-pec", "Ic-BL", "Ic-pec",
    ],
}

_category_names = list(sn_categories.keys())
_CATEGORY_COUNT = len(_category_names)

_all_subtypes = [s for subs in sn_categories.values() for s in subs]
_sn_subtype_options = [{"label": s, "value": s} for s in _all_subtypes]
_default_subtypes = ["Ia-norm", "Ia 91bg-like"]
_default_cats = ["IA"]

_DISABLED_CHECKLIST_STYLE = {"pointerEvents": "none", "opacity": 0.5}
_ENABLED_CHECKLIST_STYLE = {"pointerEvents": "auto", "opacity": 1.0}


def _sn_state(disabled: bool):
    style = _DISABLED_CHECKLIST_STYLE if disabled else _ENABLED_CHECKLIST_STYLE
    return [disabled] * _CATEGORY_COUNT, [style.copy() for _ in range(_CATEGORY_COUNT)]


galaxy_options = [
    {"label": g, "value": g}
    for g in ["E", "S0", "Sa", "Sb", "Sc", "SB1", "SB2", "SB3", "SB4", "SB5", "SB6"]
]

known_redshift_tab = dbc.Card(
    dbc.CardBody(
        dbc.Row(
            [
                dbc.Col(html.Label("z"), width="auto"),
                dbc.Col(
                    dbc.Input(
                        id="sfgui-z-known",
                        type="number",
                        size="sm",
                        persistence=True,
                        persistence_type="session",
                    ),
                    width=5,
                ),
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
                dbc.Col(
                    dbc.Input(
                        id="sfgui-z1",
                        type="number",
                        size="sm",
                        persistence=True,
                        persistence_type="session",
                    ),
                    width=2,
                ),
                dbc.Col(html.Label("z2"), width="auto"),
                dbc.Col(
                    dbc.Input(
                        id="sfgui-z2",
                        type="number",
                        size="sm",
                        persistence=True,
                        persistence_type="session",
                    ),
                    width=2,
                ),
                dbc.Col(html.Label("dz"), width="auto"),
                dbc.Col(
                    dbc.Input(
                        id="sfgui-dz",
                        type="number",
                        size="sm",
                        persistence=True,
                        persistence_type="session",
                    ),
                    width=2,
                ),
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
    content = [
        html.Div(
            [
                html.Div(
                    dbc.Checkbox(
                        id={"type": "sn-cat-toggle", "category": category},
                        value=(category in _default_cats),
                        label=html.Strong(category),
                        persistence=True,
                        persistence_type="session",
                        disabled=True,
                    ),
                    style={"marginBottom": "5px"},
                ),
                dcc.Checklist(
                    id={"type": "sn-subtypes", "category": category},
                    options=[{"label": s, "value": s} for s in subs],
                    value=(
                        subs
                        if category in _default_cats
                        else [s for s in subs if s in _default_subtypes]
                    ),
                    persistence=True,
                    persistence_type="session",
                    inputStyle={"marginRight": "6px"},
                    labelStyle={
                        "display": "inline-block",
                        "marginRight": "18px",
                        "marginBottom": "6px",
                    },
                    style=_DISABLED_CHECKLIST_STYLE.copy(),
                ),
                html.Hr(),
            ],
            style={"marginBottom": "10px"},
        )
        for category, subs in sn_categories.items()
    ]

    hidden_bridge = dcc.Checklist(
        id="sfgui-sn-types",
        options=_sn_subtype_options,
        value=_default_subtypes,
        style={"display": "none"},
        persistence=True,
        persistence_type="session",
    )

    toggle_row = html.Div(
        [
            html.Label("Supernova types", style={"fontWeight": "bold"}, className="mb-0"),
            dbc.Button(
                "Select All",
                id="sfgui-sn-select",
                size="sm",
                color="link",
                className="p-0",
                disabled=True,
            ),
        ],
        className="d-flex justify-content-between align-items-center mb-2",
    )

    return html.Div([toggle_row, html.Div(content), hidden_bridge, html.Hr()])


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
                value=DEFAULT_EPOCH_RANGE,
                marks={i: str(i) for i in range(-100, 701, 100)},
                allowCross=False,
                pushable=5,
                tooltip={"placement": "bottom", "always_visible": False},
                persistence=True,
                persistence_type="session",
            ),
            html.Small(id="sfgui-epoch-label"),
            html.Hr(),
            html.Label("Galaxies"),
            dbc.Checklist(
                id="sfgui-galaxies",
                options=galaxy_options,
                value=["E", "S0", "Sa", "Sb", "Sc"],
                inline=True,
                persistence=True,
                persistence_type="session",
            ),
            html.Div(
                dbc.Row(
                    [
                        dbc.Col(
                            dbc.Input(
                                id="sfgui-a-hi",
                                type="number",
                                placeholder="A_hi",
                                persistence=True,
                                persistence_type="session",
                            ),
                            width=4,
                        ),
                        dbc.Col(
                            dbc.Input(
                                id="sfgui-a-lo",
                                type="number",
                                placeholder="A_lo",
                                persistence=True,
                                persistence_type="session",
                            ),
                            width=4,
                        ),
                        dbc.Col(
                            dbc.Input(
                                id="sfgui-a-int",
                                type="number",
                                placeholder="A_i",
                                persistence=True,
                                persistence_type="session",
                            ),
                            width=4,
                        ),
                    ]
                ),
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
            min=LOWER_LAM,
            max=UPPER_LAM,
            value=[LOWER_LAM, UPPER_LAM],
            step=10,
            marks={i: str(i) for i in range(LOWER_LAM, UPPER_LAM + 1, 1000)},
            allowCross=False,
            updatemode="mouseup",
            tooltip={"placement": "bottom", "always_visible": False},
            persistence=True,
            persistence_type="session",
        ),
        html.Small(id="sfgui-wave-label"),
    ],
    className="mt-2",
)

btn_generate = dbc.Button(
    "Generate JSON",
    color="secondary",
    id="sfgui-generate",
    className="me-2",
    disabled=True,
)
btn_run = dbc.Button("Run Fit", color="primary", id="sfgui-run", disabled=True)
btn_run_loader = dcc.Loading(
    id="sfgui-run-loader",
    type="circle",
    parent_style={"display": "inline-block", "marginRight": "0.5rem"},
    children=btn_run,
)
btn_clear = dbc.Button("Clear", color="danger", id="sfgui-clear", className="mr-1")

json_status = html.Div(id="sfgui-json-status", className="text-muted small mb-2")
json_output = html.Pre(
    id="sfgui-json",
    style={"whiteSpace": "pre-wrap", "maxHeight": "35vh", "overflowY": "auto"},
)
run_status = html.Div(id="sfgui-run-status")
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
                                html.Div(
                                    [
                                        btn_run_loader,
                                        btn_generate,
                                        btn_clear,
                                        download_json,
                                    ],
                                    className="mt-2",
                                ),
                                dbc.Card(
                                    [dbc.CardHeader("Run Status"), dbc.CardBody(run_status)],
                                    className="mt-3",
                                ),
                                dbc.Card(
                                    [
                                        dbc.CardHeader("Parameters JSON"),
                                        dbc.CardBody([json_status, json_output]),
                                    ],
                                    className="mt-3",
                                ),
                            ],
                            md=5,
                        ),
                        dbc.Col(
                            dbc.Card(dbc.CardBody([spectrum_graph, wavelength_slider])),
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


def _build_params(
    filename,
    z_known,
    z1,
    z2,
    dz,
    sn_types,
    epoch_range,
    galaxies,
    a_hi,
    a_lo,
    a_int,
):
    return {
        "object_to_fit": filename if filename else "spectrum.dat",
        "use_exact_z": 1 if z_known is not None else 0,
        "z_exact": float(z_known) if z_known is not None else 0.05,
        "z_range_begin": float(z1) if z1 is not None else 0.0,
        "z_range_end": float(z2) if z2 is not None else 0.1,
        "z_int": float(dz) if dz is not None else 0.01,
        "resolution": 10,
        "lower_lam": LOWER_LAM,
        "upper_lam": UPPER_LAM,
        "saving_results_path": f"{RESULTS_DIR}{os.sep}",
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
    _, content_string = contents.split(",", 1)
    data = base64.b64decode(content_string)
    text = data.decode("utf-8", errors="ignore")
    buf = io.StringIO(text)

    try:
        df = pd.read_csv(buf, delim_whitespace=True, comment="#", header=None)
    except Exception:
        buf.seek(0)
        df = pd.read_csv(buf, sep=",", comment="#", header=None)

    if df.shape[1] < 2:
        df = pd.DataFrame(columns=["wavelength", "flux"])
    else:
        df = df.iloc[:, :2]
        df.columns = ["wavelength", "flux"]

    df["wavelength"] = pd.to_numeric(df["wavelength"], errors="coerce")
    df["flux"] = pd.to_numeric(df["flux"], errors="coerce")
    df = df.dropna()

    if not df.empty:
        df = (
            df.sort_values("wavelength")
            .groupby("wavelength", as_index=False)["flux"]
            .mean()
            .reset_index(drop=True)
        )

    dest = UPLOAD_DIR / filename
    with open(dest, "wb") as f:
        f.write(data)

    return df


@callback(
    Output("sfgui-upload-status", "children"),
    Output("sfgui-store-fn", "data"),
    Output("sfgui-store-df", "data"),
    Output("sfgui-store-wave", "data"),
    Output("sfgui-generate", "disabled"),
    Output("sfgui-run", "disabled"),
    Output({"type": "sn-cat-toggle", "category": ALL}, "disabled"),
    Output({"type": "sn-subtypes", "category": ALL}, "style"),
    Output("sfgui-sn-select", "disabled"),
    Input("sfgui-upload", "contents"),
    State("sfgui-upload", "filename"),
    prevent_initial_call=True,
)
def upload_file(contents, filename):
    if contents is None:
        raise PreventUpdate

    disabled_list, disabled_styles = _sn_state(disabled=True)

    if not filename:
        return "No file selected", None, None, None, True, True, disabled_list, disabled_styles, True

    df = _parse_dat(contents, filename)
    if df.empty:
        return "File parsed as empty", None, None, None, True, True, disabled_list, disabled_styles, True

    wmin = float(df["wavelength"].min())
    wmax = float(df["wavelength"].max())
    status = html.Span(
        [
            dbc.Badge("Spectrum uploaded", color="success", className="me-2"),
            html.Span(filename, className="fw-semibold"),
        ]
    )
    enabled_list, enabled_styles = _sn_state(disabled=False)

    return (
        status,
        filename,
        df.to_json(orient="split", double_precision=15),
        {"min": wmin, "max": wmax},
        False,
        False,
        enabled_list,
        enabled_styles,
        False,
    )


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
    try:
        mn = int(round(float(bounds["min"])))
        mx = int(round(float(bounds["max"])))
    except (KeyError, TypeError, ValueError):
        mn, mx = LOWER_LAM, UPPER_LAM
    if mn >= mx:
        mn, mx = LOWER_LAM, UPPER_LAM
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
        legend=dict(
            x=0.02,
            y=0.98,
            xanchor="left",
            yanchor="top",
            bgcolor="rgba(255,255,255,0.75)",
            bordercolor="rgba(0,0,0,0.15)",
            borderwidth=1,
            font=dict(size=11),
        ),
        uirevision="spectrum",
    )

    if not df_json:
        return fig
    
    def smooth_flux(df, window=5):
        if df is None or df.empty:
            return df
        smoothed = df.copy()
        smoothed["flux"] = smoothed["flux"].rolling(window, center=True, min_periods=1).mean()
        return smoothed

    df = pd.read_json(df_json, orient="split")
    df = smooth_flux(df, window=7)   



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
    Output("sfgui-json-status", "children"),
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
def generate_json(
    n,
    z_known,
    z1,
    z2,
    dz,
    sn_types,
    epoch_range,
    galaxies,
    a_hi,
    a_lo,
    a_int,
    filename,
):
    if not n:
        raise PreventUpdate

    params = _build_params(
        filename,
        z_known,
        z1,
        z2,
        dz,
        sn_types,
        epoch_range,
        galaxies,
        a_hi,
        a_lo,
        a_int,
    )
    text = json.dumps(params, indent=4)

    base_name = Path(filename).stem if filename else "spectrum"
    safe_base = "".join(
        c if c.isalnum() or c in ("-", "_") else "_" for c in base_name
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_name = f"parameters_{safe_base}_{timestamp}.json"

    with open(RESULTS_DIR / json_name, "w") as f:
        f.write(text)

    status = html.Span(
        [
            dbc.Badge("Parameters saved", color="info", className="me-2"),
            html.Span(json_name, className="text-muted"),
        ]
    )
    return text, status, dict(content=text, filename=json_name)


@callback(
    Output("sfgui-run-status", "children"),
    Output("run-flag", "data", allow_duplicate=True),
    Output("sfgui-run-loader", "children", allow_duplicate=True),
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
def run_fit(
    n,
    z_known,
    z1,
    z2,
    dz,
    sn_types,
    epoch_range,
    galaxies,
    a_hi,
    a_lo,
    a_int,
    filename,
):
    if not n:
        raise PreventUpdate

    params = _build_params(
        filename,
        z_known,
        z1,
        z2,
        dz,
        sn_types,
        epoch_range,
        galaxies,
        a_hi,
        a_lo,
        a_int,
    )
    json_string = json.dumps(params)

    try:
        os.chdir(str(BASE_DIR))
        result = subprocess.run(
            [sys.executable, "run.py", json_string],
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        alert = dbc.Alert(
            "Fit timed out after 10 minutes. Try loosening parameters or running on a faster machine.",
            color="warning",
            className="mb-0",
        )
        return alert, None, dash.no_update
    except Exception as e:
        alert = dbc.Alert(
            f"Error while running fit: {e}", color="danger", className="mb-0"
        )
        return alert, None, dash.no_update

    if result.returncode == 0:
        alert = dbc.Alert(
            "Fit completed successfully.", color="success", className="mb-0"
        )
        return alert, {"action": "run", "ts": time.time()}, dash.no_update

    alert = dbc.Alert(
        [
            html.Strong("Fit failed."),
            html.Pre(result.stderr or "", className="mb-0 mt-2 text-wrap"),
        ],
        color="danger",
        className="mb-0",
    )
    return alert, None, dash.no_update


@callback(
    Output("sfgui-z-known", "value"),
    Output("sfgui-z1", "value"),
    Output("sfgui-z2", "value"),
    Output("sfgui-dz", "value"),
    Output("sfgui-sn-types", "value", allow_duplicate=True),
    Output({"type": "sn-cat-toggle", "category": ALL}, "value", allow_duplicate=True),
    Output({"type": "sn-subtypes", "category": ALL}, "value", allow_duplicate=True),
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
    Output("sfgui-json-status", "children", allow_duplicate=True),
    Output("sfgui-run-status", "children", allow_duplicate=True),
    Output("sfgui-sn-select", "children", allow_duplicate=True),
    Output({"type": "sn-cat-toggle", "category": ALL}, "disabled", allow_duplicate=True),
    Output({"type": "sn-subtypes", "category": ALL}, "style", allow_duplicate=True),
    Output("sfgui-sn-select", "disabled", allow_duplicate=True),
    Output("sfgui-generate", "disabled", allow_duplicate=True),
    Output("sfgui-run", "disabled", allow_duplicate=True),
    Output("sfgui-wave-range", "value", allow_duplicate=True),
    Output("run-flag", "data", allow_duplicate=True),
    Input("sfgui-clear", "n_clicks"),
    prevent_initial_call=True,
)
def clear_all(n):
    if not n:
        raise PreventUpdate

    disabled_list, disabled_styles = _sn_state(disabled=True)
    default_cat_states = [False] * _CATEGORY_COUNT
    default_sub_values = [[] for _ in range(_CATEGORY_COUNT)]

    return (
        None,
        None,
        None,
        None,
        [],
        default_cat_states,
        default_sub_values,
        DEFAULT_EPOCH_RANGE,
        [],
        None,
        None,
        None,
        None,
        None,
        None,
        "",
        "",
        "",
        "Select All",
        disabled_list,
        disabled_styles,
        True,
        True,
        True,
        [LOWER_LAM, UPPER_LAM],
        {"action": "clear", "ts": time.time()},
    )


@callback(
    Output({"type": "sn-cat-toggle", "category": ALL}, "value", allow_duplicate=True),
    Output({"type": "sn-subtypes", "category": ALL}, "value", allow_duplicate=True),
    Output("sfgui-sn-types", "value", allow_duplicate=True),
    Output("sfgui-sn-select", "children", allow_duplicate=True),
    Input({"type": "sn-cat-toggle", "category": ALL}, "value"),
    Input("sfgui-sn-select", "n_clicks"),
    Input({"type": "sn-subtypes", "category": ALL}, "value"),
    State({"type": "sn-subtypes", "category": ALL}, "options"),
    prevent_initial_call=True,
)
def _sync_sn_selections(cat_states, select_clicks, sub_values, options_list):
    ctx = dash.callback_context
    if not ctx.triggered_id:
        raise PreventUpdate

    options_list = list(options_list or [])
    count = len(options_list)
    cat_states = list(cat_states or [False] * count)

    if not sub_values:
        sub_values = [[] for _ in range(count)]
    else:
        sub_values = [list(v or []) for v in sub_values]
        if len(sub_values) < count:
            sub_values.extend([[] for _ in range(count - len(sub_values))])
        elif len(sub_values) > count:
            sub_values = sub_values[:count]

    def _aggregate(sub_lists):
        return sorted({s for group in (sub_lists or []) for s in (group or [])})

    triggered_id = ctx.triggered_id

    if triggered_id == "sfgui-sn-select":
        if not count:
            raise PreventUpdate

        all_selected = True
        for opts, vals in zip(options_list, sub_values):
            option_values = [o["value"] for o in (opts or [])]
            if not option_values:
                continue
            if len(vals) != len(option_values) or set(vals) != set(option_values):
                all_selected = False
                break

        select_all = not all_selected
        new_cat_values = [select_all and bool(opts) for opts in options_list]
        new_sub_values = [
            [o["value"] for o in (opts or [])] if select_all else []
            for opts in options_list
        ]
        combined = _aggregate(new_sub_values)
        button_label = "Deselect All" if len(combined) == len(_all_subtypes) else "Select All"
        return new_cat_values, new_sub_values, combined, button_label

    if isinstance(triggered_id, dict):
        trig_type = triggered_id.get("type")

        if trig_type == "sn-cat-toggle":
            category = triggered_id.get("category")
            if category not in _category_names:
                raise PreventUpdate
            idx = _category_names.index(category)
            if idx >= count:
                raise PreventUpdate

            target_options = [o["value"] for o in (options_list[idx] or [])]
            is_active = bool(cat_states[idx])
            sub_values[idx] = target_options if is_active else []
            combined = _aggregate(sub_values)
            button_label = "Deselect All" if len(combined) == len(_all_subtypes) else "Select All"

            normalized_cat = []
            for i, opts in enumerate(options_list):
                has_all = bool(opts) and set(sub_values[i]) == {
                    o["value"] for o in (opts or [])
                }
                normalized_cat.append(has_all)

            return normalized_cat, sub_values, combined, button_label

        if trig_type == "sn-subtypes":
            normalized_cat = []
            for opts, vals in zip(options_list, sub_values):
                option_values = {o["value"] for o in (opts or [])}
                normalized_cat.append(
                    bool(option_values) and set(vals or []) == option_values
                )

            combined = _aggregate(sub_values)
            button_label = "Deselect All" if len(combined) == len(_all_subtypes) else "Select All"

            if normalized_cat == cat_states:
                cat_output = [dash.no_update] * count
            else:
                cat_output = normalized_cat

            return cat_output, sub_values, combined, button_label

    raise PreventUpdate
