from flask import Flask, send_from_directory, render_template
import os

app = Flask(__name__, static_folder='static')

# List of all sales
SALES = [
    'almanak', 'giza', 'skate', 'pulse', 'fuel', 'electron', 'nil', 'corn',
    'enclave', 'silencio', 'lit', 'resolv', 'session', 'fragmetric',
    'eoracle', 'overlay', 'ten'
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

@app.route('/sales-roi')
def sales_roi():
    return send_from_directory('static', 'sales-roi.html')

# Route for all sales pages
@app.route('/<sale>')
def sale_page(sale):
    print(f"Requested sale: {sale}")
    print(f"SALES list: {SALES}")
    print(f"Is '{sale}' in SALES: {sale in SALES}")
    
    # First check if it's a known sale
    if sale in SALES:
        try:
            file_path = f'{sale}.html'
            print(f"Trying to serve: {file_path}")
            return send_from_directory('static', file_path)
        except Exception as e:
            print(f"Error serving {sale}.html: {e}")
            return f"Error loading {sale} page", 404
    
    # If not a sale, try to serve as static file
    try:
        return send_from_directory('static', sale)
    except Exception as e:
        print(f"Error serving static file {sale}: {e}")
        return f"Page not found: {sale}", 404

# Serve static files with extensions
@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

if __name__ == '__main__':
    app.run(debug=True) 