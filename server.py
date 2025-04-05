from flask import Flask, send_from_directory, render_template
import os

app = Flask(__name__, static_folder='static')

# List of all sales
SALES = [
    'almanak', 'giza', 'skate', 'pulse', 'fuel', 'electron', 'nil', 'corn',
    'enclave', 'silencio', 'lit', 'resolv', 'session', 'fragmetric', 'hyperlane',
    'eoracle', 'overlay'
]

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/welcome')
def welcome():
    return send_from_directory('static', 'welcome.html')

@app.route('/top-investors')
def top_investors():
    return send_from_directory('static', 'top-investors.html')

# Route for all sales pages
@app.route('/<sale>')
def sale_page(sale):
    if sale in SALES:
        return send_from_directory('static', f'{sale}.html')
    return "Page not found", 404

# Serve static files
@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

if __name__ == '__main__':
    app.run(debug=True) 