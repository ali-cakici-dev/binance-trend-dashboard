import numpy as np
from datetime import datetime, timedelta
import pymongo
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go

LINE_TICKNESS_CONSTANT = 1.2
LINE_TICKNESS_HISTORY = 15

client = pymongo.MongoClient('mongodb://localhost:27017/')
db = client['binance-trend-notifier']
collection = db['symbols']

app = dash.Dash(__name__)

app.layout = html.Div(children=[
    html.H1(children='Live Symbol Performance Visualization'),
    dcc.Location(id='url', refresh=False),
    dcc.Graph(id='live-update-graph'),
    dcc.Interval(
        id='interval-component',
        interval=1 * 60000,  # in milliseconds
        n_intervals=0
    )
])

@app.callback(Output('live-update-graph', 'figure'),
              [Input('interval-component', 'n_intervals')])
def update_graph_live(n):
    end_time = datetime.now().utcnow()
    start_time = end_time - timedelta(hours=1)

    cursor = collection.find({"timestamp": {"$gte": start_time, "$lt": end_time}}).sort("timestamp", 1)

    data = {}
    timestamp_index = {}

    for document in cursor:
        symbol = document['symbol']
        price = document['price']
        timestamp = document['timestamp'].replace(second=0, microsecond=0)
        if symbol not in data:
            data[symbol] = []
        data[symbol].append((timestamp, price))
        timestamp_index[timestamp] = []

    symbol_cumulative_changes = {}
    avg_changes = {}

    for timestamp in sorted(timestamp_index.keys()):
        avg_changes[timestamp] = 0

    all_cumulative_changes = []
    for symbol, prices in data.items():
        cumulative_change = [1]
        for i in range(1, len(prices)):
            pct_change = ((prices[i][1] - prices[i - 1][1]) / prices[i - 1][1]) + 1
            cumulative_change.append(cumulative_change[-1] * pct_change)
            avg_changes[prices[i][0]] += pct_change
        symbol_cumulative_changes[symbol] = [(prices[i][0], cumulative_change[i]) for i in range(len(cumulative_change))]
        all_cumulative_changes.extend(cumulative_change)
    for timestamp in timestamp_index.keys():
        avg_changes[timestamp] /= len(data)

    avg_cumulative_changes = [1]
    timestamps = sorted(list(avg_changes.keys()))
    for i in range(1, len(timestamps)):
        avg_cumulative_changes.append(avg_cumulative_changes[-1] * avg_changes[timestamps[i]])

    fig = go.Figure()

    percentile_95 = np.percentile(np.abs(all_cumulative_changes), 98)

    for symbol, changes in symbol_cumulative_changes.items():
        timestamps, cumulative_changes = zip(*changes)
        if cumulative_changes[-1] >= percentile_95:
            fig.add_trace(go.Scatter(
                x=[ts.strftime('%Y-%m-%d %H:%M') for ts in timestamps],
                y=cumulative_changes,
                mode='lines+markers',
                name=symbol,
                line=dict(width=2)
            ))
    print("symbol_cumulative_changes", symbol_cumulative_changes.keys())
    btcusdt_changes = symbol_cumulative_changes['BTCUSDT']
    btcusdt_timestamps, btcusdt_cumulative_changes = zip(*btcusdt_changes)
    fig.add_trace(go.Scatter(
        x=[ts.strftime('%Y-%m-%d %H:%M') for ts in btcusdt_timestamps],
        y=btcusdt_cumulative_changes,
        mode='lines+markers',
        name='BTCUSDT',
        line=dict(color='red', width=2)
    ))

    fig.add_trace(go.Scatter(
        x=[ts.strftime('%Y-%m-%d %H:%M') for ts in timestamps],
        y=avg_cumulative_changes,
        mode='lines',
        line=dict(color='blue', width=2),
        name='Average Cumulative Change'
    ))

    fig.update_layout(
        title='Cumulative Symbol Performance Over Time',
        xaxis_title='Time',
        yaxis_title='Cumulative Price Change',
        hovermode='closest',
        height=800
    )

    return fig

if __name__ == '__main__':
    app.run_server(debug=True)
