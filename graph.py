
import plotly.graph_objects as go
from pymongo import MongoClient
from datetime import datetime, timedelta
import numpy as np

client = MongoClient('mongodb://localhost:27017/')
db = client['binance-trend-notifier']
collection = db['symbols']

end_time = datetime.now()
start_time = end_time - timedelta(days=1)

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

symbol_pct_changes = {}
for symbol, prices in data.items():
    pct_changes = []
    for i in range(1, len(prices)):
        pct_change = ((prices[i][1] - prices[i - 1][1]) / prices[i - 1][1]) * 100
        pct_changes.append((prices[i][0], pct_change))
        timestamp_index[prices[i][0]].append(pct_change)
    symbol_pct_changes[symbol] = pct_changes

avg_pct_changes = {timestamp: np.mean(changes) for timestamp, changes in timestamp_index.items()}

last_avg_change = avg_pct_changes[max(avg_pct_changes.keys())]
last_changes = [changes[-1][1] for changes in symbol_pct_changes.values() if changes]

if last_changes:
    deviations = [abs(change - last_avg_change) for change in last_changes]
    threshold = np.percentile(deviations, 95)
else:
    threshold = float('inf')

fig = go.Figure()

if last_changes:
    for symbol, changes in symbol_pct_changes.items():
        last_10_changes = changes[-10:] if len(changes) >= 10 else changes
        performance_score = sum(change[1] > avg_pct_changes[change[0]] for change in last_10_changes)

        line_width = max(1, 1 + 1.3 ** performance_score)

        if changes and abs(changes[-1][1] - last_avg_change) > threshold:
            timestamps, pct_changes = zip(*changes)
            fig.add_trace(go.Scatter(
                x=[ts.strftime('%Y-%m-%d %H:%M') for ts in timestamps],
                y=pct_changes,
                mode='lines+markers',
                line=dict(width=line_width),
                name=symbol
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

    fig.update_layout(title='Symbols Performance Relative to Market Average (Last 10 Bars, Filtered by 95th Percentile)',
                      xaxis_title='Time',
                      yaxis_title='Price Change (%)',
                      hovermode='closest')

    fig.show()