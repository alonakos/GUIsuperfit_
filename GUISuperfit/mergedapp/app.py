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
    brand_href="/",
    sticky="top",
)

# Tabs for page navigation
tabs = dcc.Tabs(
    id="tabs",
    value="/sfgui",  # default page path
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
        dash.page_container,
    ]
)

@app.callback(Output("url", "pathname"), Input("tabs", "value"), prevent_initial_call=True)
def route(tab_value):
    if tab_value == "tab-sfgui":
        return "/sfgui"
    if tab_value == "tab-sggui":
        return "/sggui"
    raise PreventUpdate

if __name__ == "__main__":
    app.run(debug=True, port=8050)


