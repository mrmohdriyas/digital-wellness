import dash_bootstrap_components as dbc
from dash import Dash, dcc, html, Input, Output, State
from pymongo import MongoClient
from dash.exceptions import PreventUpdate
from datetime import datetime
from typing import Optional
import json
import re

# MongoDB Manager Class
class MongoDBManager:
    def __init__(self, uri="mongodb://localhost:27017/"):
        self.client = MongoClient(uri)

    def get_collection_names(self, database_name):
        db = self.client[database_name]
        return [name for name in db.list_collection_names() if not name.endswith(('.chunks', '.files'))]

    def update_mongodb(self, database_name, collection_name, new_data):
        db = self.client[database_name]
        collection = db[collection_name]
        collection.insert_one(new_data)

# Helper function to convert screen time (hrs and mins) to seconds
def parse_screen_time(hours: int, minutes: int) -> int:
    return (hours * 3600) + (minutes * 60)

# Layout Manager Class
class LayoutManager:
    def __init__(self, mongo_manager: MongoDBManager):
        self.mongo_manager = mongo_manager

    def build_layout(self):
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

            # Input for Date
            dbc.Row([
                dbc.Col([
                    html.Label("Enter Date"),
                    dcc.Input(id="date-input", type="text", placeholder="YYYY-MM-DD", value=str(datetime.now().date()), style={'width': '100%'})
                ], width=6)
            ], className="mb-3"),

            # Input for Apps Details
            dbc.Row([
                dbc.Col([
                    html.Label("Enter App Name"),
                    dcc.Input(id="app-name", type="text", placeholder="App Name (e.g., Brave)", style={'width': '100%'})
                ], width=4),
                dbc.Col([
                    html.Label("Screen Time (hours)"),
                    dcc.Input(id="screen-time-hours", type="number", min=0, placeholder="Hours", style={'width': '100%'})
                ], width=2),
                dbc.Col([
                    html.Label("Screen Time (minutes)"),
                    dcc.Input(id="screen-time-minutes", type="number", min=0, placeholder="Minutes", style={'width': '100%'})
                ], width=2),
                dbc.Col([
                    html.Label("Notifications"),
                    dcc.Input(id="notifications", type="number", min=0, placeholder="Notifications", style={'width': '100%'})
                ], width=2),
                dbc.Col([
                    html.Label("Opens"),
                    dcc.Input(id="opens", type="number", min=0, placeholder="Opens", style={'width': '100%'})
                ], width=2)
            ], className="mb-3"),

            dbc.Row([
                dbc.Col([
                    dbc.Button("Add App", id="add-app-btn", color="primary", n_clicks=0),
                ], width=2)
            ], className="mb-3"),

            # Display the list of apps added
            dbc.Row([
                dbc.Col([
                    html.Label("Apps Added:"),
                    html.Ul(id="apps-list")
                ], width=12)
            ], className="mb-3"),

            dbc.Row([
                dbc.Col([
                    dbc.Button("Submit Data", id="submit-btn", color="primary", n_clicks=0),
                ], width=12)
            ]),

            dbc.Row([
                dbc.Col([
                    html.Div(id="output-message")
                ], width=12)
            ])
        ])

# App Initialization
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
mongo_manager = MongoDBManager()  # Create an instance of the MongoDB manager
layout_manager = LayoutManager(mongo_manager)  # Pass MongoDBManager to LayoutManager

app.layout = layout_manager.build_layout()

# Store apps data in memory
apps_data = []

# Callback to handle app addition
@app.callback(
    Output("apps-list", "children"),
    [Input("add-app-btn", "n_clicks")],
    [State("app-name", "value"), State("screen-time-hours", "value"),
     State("screen-time-minutes", "value"), State("notifications", "value"),
     State("opens", "value")]
)
def add_app(n_clicks, app_name, hours, minutes, notifications, opens):
    if n_clicks == 0 or not app_name or (hours is None and minutes is None):
        raise PreventUpdate

    # Convert screen time to seconds
    screen_time_seconds = parse_screen_time(hours or 0, minutes or 0)

    # Create app data dictionary
    app_data = {
        "name": app_name,
        "screenTime": screen_time_seconds,
        "notifications": notifications or 0,
        "opens": opens or 0
    }

    # Add the app data to the global list
    apps_data.append(app_data)

    # Display the added apps
    return [html.Li(f"{app['name']}: {app['screenTime']} seconds, {app['notifications']} notifications, {app['opens']} opens") for app in apps_data]

# Callback to handle data submission
@app.callback(
    Output("output-message", "children"),
    [Input("submit-btn", "n_clicks")],
    [State("date-input", "value"), State("collection-dropdown", "value")]
)
def update_collection(n_clicks, date_input, collection_name):
    if n_clicks == 0:
        raise PreventUpdate
    
    if not collection_name:
        return "Error: Please select a collection."

    if not date_input:
        return "Error: Please enter a valid date."

    # Calculate total screen time for summary
    total_screen_time_seconds = sum(app["screenTime"] for app in apps_data)

    # Prepare the data structure for insertion
    new_data = {
        "date": date_input,
        "summary": {
            "screenTime": total_screen_time_seconds,
            "notifications": sum(app["notifications"] for app in apps_data),
            "unlocks": sum(app["opens"] for app in apps_data),
        },
        "apps": {app["name"]: {
            "screenTime": app["screenTime"],
            "notifications": app["notifications"],
            "opens": app["opens"]
        } for app in apps_data}
    }

    # Insert the parsed data into MongoDB
    try:
        mongo_manager.update_mongodb("digital_wellness", collection_name, new_data)
        return f"Success: Data inserted into {collection_name}."
    except Exception as e:
        return f"Error: {str(e)}"

# Run the Dash app
if __name__ == "__main__":
    app.run_server(debug=True)
