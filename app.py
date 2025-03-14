from flask import Flask, jsonify, send_from_directory, request
import json
import requests
import time
from functools import wraps
from flask_cors import CORS

# Create the Flask application
app = Flask(__name__, static_url_path='', static_folder='static')
CORS(app)  # Enable CORS for all routes

# Load static data from file
try:
    with open('static_data.json', 'r') as f:
        STATIC_DATA = json.load(f)
    print(f"Loaded static data for {len(STATIC_DATA)} sales")
except Exception as e:
    print(f"Error loading static data: {str(e)}")
    STATIC_DATA = {}

# Cache for active sales (currently only Skate)
cache = {
    'skate_deposits': None,
    'skate_deposits_timestamp': 0,
    'skate_total': None,
    'skate_total_timestamp': 0
}

# Cache expiry time (15 minutes in seconds)
CACHE_EXPIRY = 900  # 15 minutes

# Constants for Skate Chain (Arbitrum) - only active sale
SKATE_ALCHEMY_API_KEY = "uuLBOZte0sf0z3XRVPPsPKMrfuQ1gqHv"
SKATE_ALCHEMY_URL = f"https://arb-mainnet.g.alchemy.com/v2/{SKATE_ALCHEMY_API_KEY}"
SKATE_CONTRACT = "0xd4f787fc73cb2d12559d0a3158cb8b4d491fbe7a"
SKATE_USDC_CONTRACT = "0xaf88d065e77c8cc2239327c5edb3a432268e5831"

# Cache decorator
def cached(cache_key, timestamp_key):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check if we have valid cached data
            current_time = time.time()
            if (cache[cache_key] is not None and 
                current_time - cache[timestamp_key] < CACHE_EXPIRY):
                print(f"Serving cached data for {cache_key}")
                return cache[cache_key]
            
            # Otherwise, execute the function and cache the result
            result = f(*args, **kwargs)
            cache[cache_key] = result
            cache[timestamp_key] = current_time
            print(f"Caching new data for {cache_key}")
            return result
        return decorated_function
    return decorator

# Skate Chain Functions - keep only the active sale functions
def get_skate_usdc_deposits():
    """Get all USDC transfers to the Skate sale contract"""
    
    all_transfers = []
    page_key = None
    
    while True:
        params = {
            "fromBlock": "0x0",
            "toBlock": "latest",
            "toAddress": SKATE_CONTRACT,
            "contractAddresses": [SKATE_USDC_CONTRACT],
            "category": ["erc20"],
            "withMetadata": True,
            "excludeZeroValue": True,
            "maxCount": "0x64"  # Hex for 100
        }
        
        if page_key:
            params["pageKey"] = page_key
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "alchemy_getAssetTransfers",
            "params": [params]
        }
        
        response = requests.post(SKATE_ALCHEMY_URL, json=payload)
        data = response.json()
        
        if "error" in data:
            print(f"Error fetching transfers: {data['error']['message']}")
            break
        
        if "result" in data and "transfers" in data["result"]:
            transfers = data["result"]["transfers"]
            all_transfers.extend(transfers)
            
            # Check if there are more pages
            if "pageKey" in data["result"]:
                page_key = data["result"]["pageKey"]
                print(f"Fetched {len(transfers)} transfers, getting next page...")
            else:
                break
        else:
            break
    
    return all_transfers

def aggregate_skate_deposits(transfers):
    """Aggregate deposits by address for Skate"""
    
    deposits_by_address = {}
    
    for transfer in transfers:
        # Check if it's a USDC transfer
        if transfer.get("asset") in ["USDC", "USD Coin"]:
            from_address = transfer["from"].lower()
            amount = float(transfer["value"])
            
            if from_address in deposits_by_address:
                deposits_by_address[from_address] += amount
            else:
                deposits_by_address[from_address] = amount
    
    # Convert to a list of dicts for JSON
    deposits_list = [
        {"address": address, "amount": amount}
        for address, amount in deposits_by_address.items()
    ]
    
    # Sort by amount in descending order
    deposits_list.sort(key=lambda x: x["amount"], reverse=True)
    
    return deposits_list

# Route handlers
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

# HTML pages for each sale
@app.route('/<string:sale_name>.html')
def sale_page(sale_name):
    return send_from_directory('static', f'{sale_name}.html')

# API Endpoints for Skate (with caching)
@app.route('/api/skate/total-investment', methods=['GET'])
@cached('skate_total', 'skate_total_timestamp')
def skate_total_investment():
    # Get all deposits and sum them up
    transfers = get_skate_usdc_deposits()
    deposits_list = aggregate_skate_deposits(transfers)
    total = sum(deposit["amount"] for deposit in deposits_list)
    return jsonify({"total": total})

@app.route('/api/skate/deposits', methods=['GET'])
@cached('skate_deposits', 'skate_deposits_timestamp')
def skate_deposits():
    transfers = get_skate_usdc_deposits()
    deposits_list = aggregate_skate_deposits(transfers)
    
    return jsonify({
        "deposits": deposits_list,
        "count": len(deposits_list)
    })

# Generic API Endpoints for all sales
@app.route('/api/<string:sale_name>/total-investment', methods=['GET'])
def sale_total_investment(sale_name):
    if sale_name == 'skate':
        return skate_total_investment()
    
    if sale_name in STATIC_DATA:
        return jsonify({"total": STATIC_DATA[sale_name]['total']})
    else:
        return jsonify({"error": f"Sale {sale_name} not found"}), 404

def get_recent_skate_transactions(limit=10):
    """Get recent USDC transfers to the Skate sale contract"""
    
    # Get the transfers
    transfers = get_skate_usdc_deposits()
    
    # Convert to our format
    transactions = []
    for transfer in transfers:
        # Extract timestamp if available
        timestamp = transfer.get("metadata", {}).get("blockTimestamp", "")
        
        tx = {
            "from": transfer["from"],
            "amount": float(transfer["value"]),
            "hash": transfer.get("hash", ""),
            "timestamp": timestamp
        }
        transactions.append(tx)
    
    # Sort by timestamp (most recent first)
    if transactions and 'timestamp' in transactions[0] and transactions[0]['timestamp']:
        transactions.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Return the limited number
    return transactions[:limit]

# New endpoint for the live feed
@app.route('/api/live-feed', methods=['GET'])
def live_feed():
    """Return the most recent transactions for the live feed"""
    # Get optional limit parameter
    limit = request.args.get('limit', default=10, type=int)
    limit = min(limit, 20)  # Max 20 transactions
    
    # Get recent transactions for Skate (the active sale)
    transactions = get_recent_skate_transactions(limit)
    
    return jsonify({
        "transactions": transactions,
        "count": len(transactions)
    })

@app.route('/api/<string:sale_name>/deposits', methods=['GET'])
def sale_deposits(sale_name):
    if sale_name == 'skate':
        return skate_deposits()
    
    if sale_name in STATIC_DATA:
        return jsonify({
            "deposits": STATIC_DATA[sale_name]['deposits'],
            "count": STATIC_DATA[sale_name]['count']
        })
    else:
        return jsonify({"error": f"Sale {sale_name} not found"}), 404

# New endpoint for getting detailed investor data for a specific sale
@app.route('/api/<string:sale_name>/investors', methods=['GET'])
def sale_investors(sale_name):
    # Get optional pagination parameters
    page = request.args.get('page', default=1, type=int)
    limit = request.args.get('limit', default=100, type=int)
    
    # Limit values for safety
    limit = min(limit, 500)  # Max 500 per page
    page = max(page, 1)      # Min page 1
    
    if sale_name == 'skate':
        # For Skate, fetch real-time data
        transfers = get_skate_usdc_deposits()
        deposits_list = aggregate_skate_deposits(transfers)
    elif sale_name in STATIC_DATA:
        # For concluded sales, use static data
        deposits_list = STATIC_DATA[sale_name]['deposits']
    else:
        return jsonify({"error": f"Sale {sale_name} not found"}), 404
    
    # Calculate pagination
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_deposits = deposits_list[start_idx:end_idx]
    
    return jsonify({
        "investors": paginated_deposits,
        "page": page,
        "limit": limit,
        "total_investors": len(deposits_list),
        "total_pages": (len(deposits_list) + limit - 1) // limit
    })

# New endpoint for sale statistics including highest and lowest allocations
@app.route('/api/<string:sale_name>/stats', methods=['GET'])
def sale_stats(sale_name):
    """Return key statistics for a sale including highest and lowest allocations"""
    if sale_name == 'skate':
        # For Skate, fetch real-time data
        transfers = get_skate_usdc_deposits()
        deposits_list = aggregate_skate_deposits(transfers)
    elif sale_name in STATIC_DATA:
        # For concluded sales, use static data
        deposits_list = STATIC_DATA[sale_name]['deposits']
    else:
        return jsonify({"error": f"Sale {sale_name} not found"}), 404
    
    # Calculate stats
    if deposits_list:
        total_investment = sum(deposit["amount"] for deposit in deposits_list)
        total_investors = len(deposits_list)
        highest_allocation = max(deposits_list, key=lambda x: x["amount"])
        lowest_allocation = min(deposits_list, key=lambda x: x["amount"])
        average_allocation = total_investment / total_investors if total_investors > 0 else 0
        
        # Top 5 investors
        top_investors = sorted(deposits_list, key=lambda x: x["amount"], reverse=True)[:5]
    else:
        total_investment = 0
        total_investors = 0
        highest_allocation = {"address": "", "amount": 0}
        lowest_allocation = {"address": "", "amount": 0}
        average_allocation = 0
        top_investors = []
    
    return jsonify({
        "total_investment": total_investment,
        "total_investors": total_investors,
        "highest_allocation": highest_allocation,
        "lowest_allocation": lowest_allocation,
        "average_allocation": average_allocation,
        "top_investors": top_investors
    })

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)