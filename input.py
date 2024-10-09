import dash_bootstrap_components as dbc
from dash import Dash, dcc, html, Input, Output, State, ALL
from dash import ctx
from pymongo import MongoClient
from dash.exceptions import PreventUpdate
from datetime import datetime
from typing import List, Dict, Optional

class MongoDBManager:
    def __init__(self, uri: str = "mongodb://localhost:27017/"):
        self.client = MongoClient(uri)

    def get_collection_names(self, database_name: str) -> List[str]:
        db = self.client[database_name]
        return [name for name in db.list_collection_names() if not name.endswith(('.chunks', '.files'))]

    def update_mongodb(self, database_name: str, collection_name: str, new_data: Dict):
        db = self.client[database_name]
        collection = db[collection_name]
        collection.insert_one(new_data)

class LayoutManager:
    def __init__(self, mongo_manager: MongoDBManager):
        self.mongo_manager = mongo_manager

    def build_layout(self) -> dbc.Container:
        return dbc.Container([
            dbc.Row([ 
                dbc.Col([
                    html.Label("Select Collection"),
                    dcc.Dropdown(
                        id="collection-dropdown",
                        options=[{'label': name, 'value': name} for name in self.mongo_manager.get_collection_names("digital_wellness")],
                        placeholder="Select a collection"
                    ),
                ], width=6)
            ], className="mb-3"),

            dbc.Row([ 
                dbc.Col([
                    html.Label("Enter Date"),
                    dcc.Input(id="date-input", type="text", placeholder="YYYY-MM-DD", value=str(datetime.now().date()), style={'width': '100%'})
                ], width=6)
            ], className="mb-3"),

            dbc.Row([
                dbc.Col([
                    html.Label("Enter App Name"),
                    dcc.Input(id="app-name", type="text", placeholder="App Name (e.g., Brave)", style={'width': '100%'})
                ], width=4),
                dbc.Col([
                    html.Label("Screen Time (hours)"),
                    dcc.Input(id="screen-time-hours", type="number", min=0, step=1, placeholder="Hours", style={'width': '100%'})
                ], width=2),
                dbc.Col([
                    html.Label("Screen Time (minutes)"),
                    dcc.Input(id="screen-time-minutes", type="number", min=0, step=1, placeholder="Minutes", style={'width': '100%'})
                ], width=2),
                dbc.Col([
                    html.Label("Screen Time (seconds)"),
                    dcc.Input(id="screen-time-seconds", type="number", min=0, step=1, placeholder="Seconds", style={'width': '100%'})
                ], width=2),
                dbc.Col([
                    html.Label("Opens"),
                    dcc.Input(id="opens", type="number", min=0, step=1, placeholder="Opens", style={'width': '100%'})
                ], width=2)
            ], className="mb-3"),

            dbc.Row([
                dbc.Col([
                    dbc.Button("Add App", id="add-app-btn", color="primary", n_clicks=0),
                ], width=2)
            ], className="mb-3"),

            dbc.Row([
                dbc.Col([
                    html.Label("Apps Added:"),
                    html.Ul(id="apps-list")
                ], width=12)
            ], className="mb-3"),

            dbc.Row([dbc.Col([dbc.Button("Submit Data", id="submit-btn", color="primary", n_clicks=0)], width=12)]),

            dbc.Row([dbc.Col([html.Div(id="output-message")], width=12)])
        ])

class DataManager:
    def __init__(self):
        self.apps_data = []

    def parse_screen_time(self, hours: int, minutes: int, seconds: int) -> int:
        return (hours * 3600) + (minutes * 60) + seconds

    def add_app(self, app_name: str, hours: int, minutes: int, seconds: int, opens: int) -> None:
        screen_time_seconds = self.parse_screen_time(hours or 0, minutes or 0, seconds or 0)
        app_data = {
            "name": app_name,
            "screenTime": screen_time_seconds,
            "opens": opens or 0
        }
        self.apps_data.append(app_data)

    def get_apps_data(self) -> List[Dict]:
        return self.apps_data

    def remove_app(self, index: int) -> None:
        if 0 <= index < len(self.apps_data):
            del self.apps_data[index]

    def prepare_submission_data(self, date_input: str) -> Dict:
        total_screen_time_seconds = sum(app["screenTime"] for app in self.apps_data)
        return {
            "date": date_input,
            "summary": {
                "screenTime": total_screen_time_seconds,
                "unlocks": sum(app["opens"] for app in self.apps_data),
            },
            "apps": {app["name"]: {
                "screenTime": app["screenTime"],
                "opens": app["opens"]
            } for app in self.apps_data}
        }

class DigitalWellnessApp:
    def __init__(self):
        self.mongo_manager = MongoDBManager()
        self.layout_manager = LayoutManager(self.mongo_manager)
        self.data_manager = DataManager()
        self.app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
        self.app.layout = self.layout_manager.build_layout()
        self._init_callbacks()

    def _init_callbacks(self):
        @self.app.callback(
            Output("apps-list", "children"),
            [Input("add-app-btn", "n_clicks"), Input({"type": "remove-app-btn", "index": ALL}, "n_clicks")],
            [State("app-name", "value"), State("screen-time-hours", "value"),
            State("screen-time-minutes", "value"), State("screen-time-seconds", "value"),
            State("opens", "value")]
        )
        def add_app_callback(add_clicks, remove_clicks, app_name, hours, minutes, seconds, opens):
            triggered = ctx.triggered_id

            if not triggered:
                raise PreventUpdate

            # Handle removing an app
            if isinstance(triggered, dict) and triggered['type'] == 'remove-app-btn':
                index = triggered['index']
                if remove_clicks[index] > 0:
                    self.data_manager.remove_app(index)

            # Handle adding an app
            elif add_clicks > 0:
                # Validate app_name
                if not app_name:
                    return [html.Li("Error: App name cannot be empty.")]

                # Validate hours, minutes, seconds, and opens
                try:
                    # Ensure inputs are integers
                    hours = int(hours) if hours is not None else 0
                    minutes = int(minutes) if minutes is not None else 0
                    seconds = int(seconds) if seconds is not None else 0
                    opens = int(opens) if opens is not None else 0

                    if not (0 <= hours <= 24):
                        return [html.Li("Error: Hours must be between 0 and 24.")]
                    if not (0 <= minutes <= 59):
                        return [html.Li("Error: Minutes must be between 0 and 59.")]
                    if not (0 <= seconds <= 59):
                        return [html.Li("Error: Seconds must be between 0 and 59.")]
                    if opens < 0:
                        return [html.Li("Error: Opens must be a non-negative integer.")]
                except ValueError:
                    return [html.Li("Error: Hours, minutes, seconds, and opens must be valid integers.")]

                # Add app to the data manager if validation passes
                self.data_manager.add_app(app_name, hours, minutes, seconds, opens)

            # Update the app list display
            apps_data = self.data_manager.get_apps_data()
            return [
                html.Li([
                    dbc.Button("Remove", id={"type": "remove-app-btn", "index": i}, color="danger", size="sm", className="me-2"),
                    f"{app['name']}: {app['screenTime']} seconds, {app['opens']} opens"
                ]) for i, app in enumerate(apps_data)
            ]

        @self.app.callback(
            Output("output-message", "children"),
            [Input("submit-btn", "n_clicks")],
            [State("date-input", "value"), State("collection-dropdown", "value")]
        )
        def submit_data_callback(n_clicks, date_input, collection_name):
            if n_clicks == 0:
                raise PreventUpdate

            if not collection_name:
                return "Error: Please select a collection."

            if not date_input:
                return "Error: Please enter a valid date."

            try:
                new_data = self.data_manager.prepare_submission_data(date_input)
                self.mongo_manager.update_mongodb("digital_wellness", collection_name, new_data)
                return "Data submitted successfully!"
            except Exception as e:
                return f"Error: {str(e)}"

    def run(self):
        self.app.run_server(debug=True)

if __name__ == "__main__":
    app = DigitalWellnessApp()
    app.run()
