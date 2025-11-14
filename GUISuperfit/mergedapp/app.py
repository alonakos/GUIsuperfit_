import dash
import dash_bootstrap_components as dbc
from dash import dcc, html
from dash.dependencies import Input, Output
from dash.exceptions import PreventUpdate

app = dash.Dash(__name__, use_pages=True, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server  # for deployment 


navbar = dbc.NavbarSimple(brand="Superfit", brand_href="#", sticky="top")

# Navbar
navbar = dbc.NavbarSimple(
    brand="Superfit",
    brand_href="/sfgui",
    sticky="top",
)

# Tabs for page navigation
tabs = dcc.Tabs(
    id="tabs",
    value="tab-sfgui",  # default page path
    children=[
        dcc.Tab(label="Input", value="tab-sfgui"),
        dcc.Tab(label="Output", value="tab-sggui"),
    ],
    persistence=True,
    persistence_type="session",
)

# Layout
app.layout = html.Div(
    [
        navbar,
        tabs,
    dcc.Location(id="url"),
        dcc.Store(id="run-flag", storage_type="session"),
        dash.page_container,
    ]
)

PATH_FOR_TAB = {
    "tab-sfgui": "/sfgui",
    "tab-sggui": "/sggui",
}

TAB_FOR_PATH = {
    "/": "tab-sfgui",
    "/sfgui": "tab-sfgui",
    None: "tab-sfgui",
    "/sggui": "tab-sggui",
}


@app.callback(
    Output("url", "pathname", allow_duplicate=True),
    Output("tabs", "value", allow_duplicate=True),
    Input("tabs", "value"),
    Input("url", "pathname"),
    prevent_initial_call=True,
)
def sync_navigation(tab_value, pathname):
    ctx = dash.callback_context
    if not ctx.triggered_id:
        raise PreventUpdate

    triggered = ctx.triggered_id

    if triggered == "tabs":
        new_path = PATH_FOR_TAB.get(tab_value)
        if not new_path:
            raise PreventUpdate
        return new_path, dash.no_update

    if triggered == "url":
        new_tab = TAB_FOR_PATH.get(pathname)
        if not new_tab:
            return dash.no_update, dash.no_update
        target_path = PATH_FOR_TAB.get(new_tab)
        if target_path and pathname != target_path:
            return target_path, new_tab
        return dash.no_update, new_tab

    raise PreventUpdate

if __name__ == "__main__":
    app.run(debug=True, port=8050)

