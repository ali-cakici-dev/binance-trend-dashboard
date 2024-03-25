import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import pymongo
from datetime import datetime, timedelta
import numpy as np

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
    start_time = end_time - timedelta(hours=2)

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
    print(timestamp_index)
    symbol_pct_changes = {}
    for symbol, prices in data.items():
        pct_changes = []
        for i in range(1, len(prices)):
            pct_change = ((prices[i][1] - prices[i - 1][1]) / prices[i - 1][1]) * 100
            pct_changes.append((prices[i][0], pct_change))
            timestamp_index[prices[i][0]].append(pct_change)
        symbol_pct_changes[symbol] = pct_changes

    avg_pct_changes = {timestamp: np.mean(changes) for timestamp, changes in timestamp_index.items()}
    print(avg_pct_changes)
    last_avg_change = avg_pct_changes[max(avg_pct_changes.keys())]
    symbols_with_line_thickness = []
    last_changes = [changes[-1][1] for changes in symbol_pct_changes.values() if changes]

    if last_changes:
        deviations = [abs(change - last_avg_change) for change in last_changes]
        threshold = np.percentile(deviations, 98)
    else:
        threshold = float('inf')

    fig = go.Figure()
    if last_changes:
        for symbol, changes in symbol_pct_changes.items():
            last_10_changes = changes[-LINE_TICKNESS_HISTORY:] if len(changes) >= LINE_TICKNESS_HISTORY else changes
            performance_score = sum(change[1] > avg_pct_changes[change[0]] for change in last_10_changes)

            line_width = int(max(1, int((LINE_TICKNESS_CONSTANT ** performance_score)/2)))
            if abs(changes[-1][1] - last_avg_change) > threshold:
                symbols_with_line_thickness.append((symbol, line_width, changes, performance_score))
        symbols_with_line_thickness.sort(key=lambda x: x[1], reverse=True)
        c = 0
        for symbol, line_width, changes, performance_score in symbols_with_line_thickness:
            c += 1
            timestamps, pct_changes = zip(*changes)
            fig.add_trace(go.Scatter(
                x=[ts.strftime('%Y-%m-%d %H:%M') for ts in timestamps],
                y=pct_changes,
                mode='lines+markers',
                line=dict(width=line_width),
                name=symbol+ " " + str(c) + " " + str(performance_score)
            ))

        avg_timestamps = sorted(avg_pct_changes.keys())
        avg_changes = [avg_pct_changes[ts] for ts in avg_timestamps]
        fig.add_trace(go.Scatter(
            x=[ts.strftime('%Y-%m-%d %H:%M') for ts in avg_timestamps],
            y=avg_changes,
            mode='lines',
            line=dict(color='blue', width=2),
            name='Average Percentage Change'
        ))

        fig.update_layout(
            title='Symbols Performance Relative to Market Average (Last 10 Bars, Filtered by 95th Percentile)',
            xaxis_title='Time',
            yaxis_title='Price Change (%)',
            hovermode='closest',
            height=800, )# Set y-axis range
        fig.update_yaxes(range=[-3, 3])

        return fig


if __name__ == '__main__':
    app.run_server(debug=True)
