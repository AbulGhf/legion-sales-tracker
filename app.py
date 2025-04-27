from flask import Flask, jsonify, send_from_directory, request
import json
import requests
import time
from functools import wraps
from flask_cors import CORS

# Create the Flask application
app = Flask(__name__, static_url_path='/static', static_folder='static')
CORS(app)  # Enable CORS for all routes

# Load static data from file
try:
    with open('static_data.json', 'r') as f:
        STATIC_DATA = json.load(f)
    print(f"Loaded static data for {len(STATIC_DATA)} sales")
except Exception as e:
    print(f"Error loading static data: {str(e)}")
    STATIC_DATA = {}

# Load Fragmetric data for Solana addresses with proper case
try:
    with open('fragmetric.json', 'r') as f:
        FRAGMETRIC_DATA = json.load(f)
    print(f"Loaded Fragmetric data with {len(FRAGMETRIC_DATA)} entries")
    
    # Create a lookup map for Solana addresses (lowercase to original case)
    SOLANA_ADDRESS_MAP = {}
    for entry in FRAGMETRIC_DATA:
        if 'address' in entry and not entry['address'].startswith('0x'):
            SOLANA_ADDRESS_MAP[entry['address'].lower()] = entry['address']
    print(f"Created Solana address map with {len(SOLANA_ADDRESS_MAP)} entries")
except Exception as e:
    print(f"Error loading Fragmetric data: {str(e)}")
    FRAGMETRIC_DATA = []
    SOLANA_ADDRESS_MAP = {}

# Cache for active sales (Lit Protocol and Resolv)
cache = {
    'lit_deposits': None,
    'lit_deposits_timestamp': 0,
    'lit_total': None,
    'lit_total_timestamp': 0,
    'resolv_deposits': None,
    'resolv_deposits_timestamp': 0,
    'resolv_total': None,
    'resolv_total_timestamp': 0,
    'session_deposits': None,
    'session_deposits_timestamp': 0,
    'session_total': None,
    'session_total_timestamp': 0,
    'session_investors': None,  # Added for new endpoint
    'session_investors_timestamp': 0,  # Added for new endpoint
    'global_stats': None,
    'global_stats_timestamp': 0
}

# Cache expiry time (15 minutes in seconds)
CACHE_EXPIRY = 900  # 15 minutes

# Constants for Lit Protocol (Arbitrum)
LIT_ALCHEMY_API_KEY = "uuLBOZte0sf0z3XRVPPsPKMrfuQ1gqHv"
LIT_ALCHEMY_URL = f"https://arb-mainnet.g.alchemy.com/v2/{LIT_ALCHEMY_API_KEY}"
LIT_CONTRACTS = [
    "0xE193d30421D6e60D61De1b7e097a66B595eA9B11",
    "0x9A3475824A15933c207Dd8B661b9488169B25947",
    "0xDB0a5509318614CfFe600BcEa9bC6C001c28C270",
    "0x81A00dA473D1BfF1D1b894c8a9b4C88464F15F9D"
]
LIT_USDC_CONTRACT = "0xaf88d065e77c8cc2239327c5edb3a432268e5831"  # Arbitrum USDC contract

# Constants for Resolv Protocol (Ethereum)
RESOLV_ALCHEMY_API_KEY = "uuLBOZte0sf0z3XRVPPsPKMrfuQ1gqHv"  # Using the same API key
RESOLV_ALCHEMY_URL = f"https://eth-mainnet.g.alchemy.com/v2/{

RESOLV_ALCHEMY_API_KEY}"  # Ethereum endpoint
RESOLV_CONTRACTS = [
    "0xee6deedb6c1535E4912eE5db48E08b36FD2fAA8f",
    "0x5Fdab714fe8BB9d40C8B1e5f7c2BacD8E7f869d8"
]
RESOLV_USDC_CONTRACT = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"

# Constants for Session Protocol (Arbitrum)
SESSION_ALCHEMY_API_KEY = "uuLBOZte0sf0z3XRVPPsPKMrfuQ1gqHv"
SESSION_ALCHEMY_URL = f"https://arb-mainnet.g.alchemy.com/v2/{SESSION_ALCHEMY_API_KEY}"
SESSION_CONTRACTS = [
    "0x543Eb0BFB29803C28eC0A0Ed181683c915F44ED2",
    "0xD3472eD0F891ee9279ADFFC7e147bFCF8E72C790",
    "0x90cd2BBccdC85Ab75a14d2112ffa2A5cD42817A4"
]
SESSION_USDC_CONTRACT = "0xaf88d065e77c8cc2239327c5edb3a432268e5831"  # Arbitrum USDC contract

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

# Lit Protocol Functions
def get_lit_usdc_deposits():
    """Get all USDC transfers to the Lit Protocol sale contracts"""
    
    all_transfers = []
    
    for contract_address in LIT_CONTRACTS:
        page_key = None
        contract_transfers = []
        
        print(f"Fetching USDC transfers to Lit Protocol contract: {contract_address}")
        
        while True:
            params = {
                "fromBlock": "0x0",
                "toBlock": "latest",
                "toAddress": contract_address,
                "contractAddresses": [LIT_USDC_CONTRACT],
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
            
            response = requests.post(LIT_ALCHEMY_URL, json=payload)
            data = response.json()
            
            if "error" in data:
                print(f"Error fetching transfers: {data['error']['message']}")
                break
            
            if "result" in data and "transfers" in data["result"]:
                transfers = data["result"]["transfers"]
                contract_transfers.extend(transfers)
                
                # Check if there are more pages
                if "pageKey" in data["result"]:
                    page_key = data["result"]["pageKey"]
                    print(f"Fetched {len(transfers)} transfers for contract, getting next page...")
                else:
                    print(f"Fetched {len(transfers)} transfers for contract, no more pages.")
                    break
            else:
                break
        
        print(f"Total transfers fetched for contract {contract_address}: {len(contract_transfers)}")
        all_transfers.extend(contract_transfers)
    
    print(f"Total transfers fetched across all contracts: {len(all_transfers)}")
    return all_transfers

def aggregate_lit_deposits(transfers):
    """Aggregate deposits by address for Lit Protocol"""
    
    deposits_by_address = {}
    
    for transfer in transfers:
        # Check if it's a USDC transfer
        if transfer.get("asset") in ["USDC", "USD Coin"]:
            from_address = transfer["from"].lower()
            amount = float(transfer["value"])
            
            if from_address in deposits_by_address:
                deposits_by_address[from_address]["amount"] += amount
            else:
                deposits_by_address[from_address] = {
                    "address": from_address,
                    "amount": amount
                }
    
    # Convert to a list for JSON
    deposits_list = list(deposits_by_address.values())
    
    # Sort by amount in descending order
    deposits_list.sort(key=lambda x: x["amount"], reverse=True)
    
    return deposits_list

def get_recent_lit_transactions(limit=10):
    """Get recent USDC transfers to the Lit Protocol sale contracts"""
    
    # Get the transfers
    transfers = get_lit_usdc_deposits()
    
    # Convert to our format
    transactions = []
    for transfer in transfers:
        # Extract timestamp if available
        timestamp = transfer.get("metadata", {}).get("blockTimestamp", "")
        
        tx = {
            "from": transfer["from"],
            "amount": float(transfer["value"]),
            "hash": transfer.get("hash", ""),
            "timestamp": timestamp,
            "sale": "lit"  # Add sale identifier
        }
        transactions.append(tx)
    
    # Sort by timestamp (most recent first)
    if transactions and 'timestamp' in transactions[0] and transactions[0]['timestamp']:
        transactions.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Return the limited number
    return transactions[:limit]

# Resolv Protocol Functions
def get_resolv_usdc_deposits():
    """Get all USDC transfers to the Resolv Protocol sale contracts"""
    
    all_transfers = []
    
    # Fetch transfers for each contract
    for contract in RESOLV_CONTRACTS:
        page_key = None
        print(f"Fetching USDC transfers to Resolv Protocol contract: {contract}")
        
        while True:
            params = {
                "fromBlock": "0x0",
                "toBlock": "latest",
                "toAddress": contract,
                "contractAddresses": [RESOLV_USDC_CONTRACT],
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
            
            response = requests.post(RESOLV_ALCHEMY_URL, json=payload)
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
                    print(f"Fetched {len(transfers)} transfers, no more pages.")
                    break
            else:
                break
    
    print(f"Total transfers fetched: {len(all_transfers)}")
    return all_transfers

def aggregate_resolv_deposits(transfers):
    """Aggregate deposits by address for Resolv Protocol"""
    
    deposits_by_address = {}
    
    for transfer in transfers:
        # Check if it's a USDC transfer
        if transfer.get("asset") in ["USDC", "USD Coin"]:
            from_address = transfer["from"].lower()
            amount = float(transfer["value"])
            
            if from_address in deposits_by_address:
                deposits_by_address[from_address]["amount"] += amount
            else:
                deposits_by_address[from_address] = {
                    "address": from_address,
                    "amount": amount
                }
    
    # Convert to a list for JSON
    deposits_list = list(deposits_by_address.values())
    
    # Sort by amount in descending order
    deposits_list.sort(key=lambda x: x["amount"], reverse=True)
    
    return deposits_list

def get_recent_resolv_transactions(limit=10):
    """Get recent USDC transfers to the Resolv Protocol sale contract"""
    
    # Get the transfers
    transfers = get_resolv_usdc_deposits()
    
    # Convert to our format
    transactions = []
    for transfer in transfers:
        # Extract timestamp if available
        timestamp = transfer.get("metadata", {}).get("blockTimestamp", "")
        
        tx = {
            "from": transfer["from"],
            "amount": float(transfer["value"]),
            "hash": transfer.get("hash", ""),
            "timestamp": timestamp,
            "sale": "resolv"  # Add sale identifier
        }
        transactions.append(tx)
    
    # Sort by timestamp (most recent first)
    if transactions and 'timestamp' in transactions[0] and transactions[0]['timestamp']:
        transactions.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Return the limited number
    return transactions[:limit]

# Session Protocol Functions
def get_session_usdc_deposits():
    """Get all USDC transfers to the Session Protocol sale contracts"""
    
    all_transfers = []
    
    for contract_address in SESSION_CONTRACTS:
        page_key = None
        contract_transfers = []
        
        print(f"Fetching USDC transfers to Session Protocol contract: {contract_address}")
        
        while True:
            params = {
                "fromBlock": "0x0",
                "toBlock": "latest",
                "toAddress": contract_address,
                "contractAddresses": [SESSION_USDC_CONTRACT],
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
            
            response = requests.post(SESSION_ALCHEMY_URL, json=payload)
            data = response.json()
            
            if "error" in data:
                print(f"Error fetching transfers: {data['error']['message']}")
                break
            
            if "result" in data and "transfers" in data["result"]:
                transfers = data["result"]["transfers"]
                contract_transfers.extend(transfers)
                
                # Check if there are more pages
                if "pageKey" in data["result"]:
                    page_key = data["result"]["pageKey"]
                    print(f"Fetched {len(transfers)} transfers for contract, getting next page...")
                else:
                    print(f"Fetched {len(transfers)} transfers for contract, no more pages.")
                    break
            else:
                break
        
        print(f"Total transfers fetched for contract {contract_address}: {len(contract_transfers)}")
        all_transfers.extend(contract_transfers)
    
    print(f"Total transfers fetched across all contracts: {len(all_transfers)}")
    return all_transfers

def aggregate_session_deposits(transfers):
    """Aggregate deposits by address for Session Protocol"""
    
    deposits_by_address = {}
    
    for transfer in transfers:
        # Check if it's a USDC transfer
        if transfer.get("asset") in ["USDC", "USD Coin"]:
            from_address = transfer["from"].lower()
            amount = float(transfer["value"])
            
            if from_address in deposits_by_address:
                deposits_by_address[from_address]["amount"] += amount
            else:
                deposits_by_address[from_address] = {
                    "address": from_address,
                    "amount": amount
                }
    
    # Convert to a list for JSON
    deposits_list = list(deposits_by_address.values())
    
    # Sort by amount in descending order
    deposits_list.sort(key=lambda x: x["amount"], reverse=True)
    
    return deposits_list

def get_recent_session_transactions(limit=10):
    """Get recent USDC transfers to the Session Protocol sale contracts"""
    
    # Get the transfers
    transfers = get_session_usdc_deposits()
    
    # Convert to our format
    transactions = []
    for transfer in transfers:
        # Extract timestamp if available
        timestamp = transfer.get("metadata", {}).get("blockTimestamp", "")
        
        tx = {
            "from": transfer["from"],
            "amount": float(transfer["value"]),
            "hash": transfer.get("hash", ""),
            "timestamp": timestamp,
            "sale": "session",  # Add sale identifier
            "is_live": True     # Flag to indicate this is a live sale
        }
        transactions.append(tx)
    
    # Sort by timestamp (most recent first)
    if transactions and 'timestamp' in transactions[0] and transactions[0]['timestamp']:
        transactions.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Return the limited number
    return transactions[:limit]

# Route handlers
@app.route('/')
def welcome():
    return send_from_directory('static', 'welcome.html')

@app.route('/dashboard')
def dashboard():
    # Create response object
    response = send_from_directory('static', 'index.html')
    
    # Set cookie to indicate the app is initialized
    response.set_cookie('app_initialized', 'true', max_age=3600)  # Cookie expires after 1 hour
    
    return response

# HTML pages for each sale
@app.route('/<path:filename>')
def serve_static(filename):
    if filename.endswith(('.jpg', '.png', '.gif')):
        return send_from_directory('static', filename)
    elif filename.endswith('.html'):
        return send_from_directory('static', filename)
    else:
        return send_from_directory('static', f'{filename}.html')

@app.route('/api/lit/total-investment', methods=['GET'])
def lit_total_investment():
    """Get total investment for Lit Protocol sale"""
    if 'lit' in STATIC_DATA:
        return jsonify({"total": STATIC_DATA['lit']['total']})
    return jsonify({"error": "Lit Protocol data not found"}), 404

@app.route('/api/lit/deposits', methods=['GET'])
def lit_deposits():
    """Get all deposits for Lit Protocol sale"""
    if 'lit' in STATIC_DATA:
        return jsonify({
            "deposits": STATIC_DATA['lit']['deposits'],
            "count": STATIC_DATA['lit']['count']
        })
    return jsonify({"error": "Lit Protocol data not found"}), 404

@app.route('/api/lit/stats', methods=['GET'])
def lit_stats():
    """Get statistics for Lit Protocol sale"""
    if 'lit' in STATIC_DATA:
        deposits_list = STATIC_DATA['lit']['deposits']
        total_investment = STATIC_DATA['lit']['total']
        total_investors = STATIC_DATA['lit']['count']
        
        if deposits_list:
            highest_allocation = max(deposits_list, key=lambda x: x["amount"])
            lowest_allocation = min(deposits_list, key=lambda x: x["amount"])
            average_allocation = total_investment / total_investors if total_investors > 0 else 0
            
            # Top 5 investors
            top_investors = sorted(deposits_list, key=lambda x: x["amount"], reverse=True)[:5]
        else:
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
    return jsonify({"error": "Lit Protocol data not found"}), 404

# API Endpoints for Resolv Protocol (with caching)
@app.route('/api/resolv/total-investment', methods=['GET'])
def resolv_total_investment():
    """Get total investment for Resolv Protocol sale"""
    if 'resolv' in STATIC_DATA:
        return jsonify({"total": STATIC_DATA['resolv']['total']})
    return jsonify({"error": "Resolv Protocol data not found"}), 404

@app.route('/api/resolv/deposits', methods=['GET'])
def resolv_deposits():
    """Get all deposits for Resolv Protocol sale"""
    if 'resolv' in STATIC_DATA:
        return jsonify({
            "deposits": STATIC_DATA['resolv']['deposits'],
            "count": STATIC_DATA['resolv']['count']
        })
    return jsonify({"error": "Resolv Protocol data not found"}), 404

@app.route('/api/resolv/stats', methods=['GET'])
def resolv_stats():
    """Return key statistics for Resolv Protocol sale"""
    if 'resolv' not in STATIC_DATA:
        return jsonify({"error": "Resolv Protocol data not found"}), 404
    
    deposits_list = STATIC_DATA['resolv']['deposits']
    
    # Calculate stats
    if deposits_list:
        total_investment = sum(item["amount"] for item in deposits_list)
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
    
    response_data = {
        "total_investment": total_investment,
        "total_investors": total_investors,
        "highest_allocation": highest_allocation,
        "lowest_allocation": lowest_allocation,
        "average_allocation": average_allocation,
        "top_investors": top_investors
    }
    
    return jsonify(response_data)

# Session Protocol Functions
@app.route('/api/session/total-investment', methods=['GET'])
@cached('session_total', 'session_total_timestamp')
def session_total_investment():
    """Get total investment for Session Protocol sale"""
    transfers = get_session_usdc_deposits()
    deposits_list = aggregate_session_deposits(transfers)
    total = sum(deposit["amount"] for deposit in deposits_list)
    return jsonify({"total": total, "is_live": True})

@app.route('/api/session/deposits', methods=['GET'])
@cached('session_deposits', 'session_deposits_timestamp')
def session_deposits():
    """Get all deposits for Session Protocol sale"""
    transfers = get_session_usdc_deposits()
    deposits_list = aggregate_session_deposits(transfers)
    
    return jsonify({
        "deposits": deposits_list,
        "count": len(deposits_list),
        "is_live": True
    })

@app.route('/api/session/stats', methods=['GET'])
def session_stats():
    """Return key statistics for Session Protocol sale"""
    transfers = get_session_usdc_deposits()
    deposits_list = aggregate_session_deposits(transfers)
    
    # Calculate stats
    if deposits_list:
        total_investment = sum(item["amount"] for item in deposits_list)
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
    
    response_data = {
        "total_investment": total_investment,
        "total_investors": total_investors,
        "highest_allocation": highest_allocation,
        "lowest_allocation": lowest_allocation,
        "average_allocation": average_allocation,
        "top_investors": top_investors,
        "is_live": True
    }
    
    return jsonify(response_data)

# New endpoint for Session investors with pagination
@app.route('/api/session/investors', methods=['GET'])
def session_investors():
    """Get paginated list of investors for Session Protocol sale"""
    page = request.args.get('page', default=1, type=int)
    limit = request.args.get('limit', default=10, type=int)
    
    # Limit values for safety
    limit = min(limit, 500)  # Max 500 per page
    page = max(page, 1)      # Min page 1
    
    # Check if we have valid cached full deposits list
    current_time = time.time()
    if (cache['session_deposits'] is not None and 
        current_time - cache['session_deposits_timestamp'] < CACHE_EXPIRY):
        print("Using cached deposits list for pagination")
        deposits_list = cache['session_deposits']
    else:
        # Fetch live Session data
        try:
            transfers = get_session_usdc_deposits()
            deposits_list = aggregate_session_deposits(transfers)
            # Update cache
            cache['session_deposits'] = deposits_list
            cache['session_deposits_timestamp'] = current_time
        except Exception as e:
            print(f"Error fetching Session investors: {str(e)}")
            return jsonify({"error": f"Failed to fetch Session investors: {str(e)}"}), 500
    
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

# Generic API Endpoints for all sales
@app.route('/api/<string:sale_name>/total-investment', methods=['GET'])
def sale_total_investment(sale_name):
    if sale_name == 'lit':
        return lit_total_investment()
    elif sale_name == 'resolv':
        return resolv_total_investment()
    elif sale_name == 'fragmetric':
        return fragmetric_total_investment()
    elif sale_name == 'session':
        return session_total_investment()
    
    if sale_name in STATIC_DATA:
        return jsonify({"total": STATIC_DATA[sale_name]['total']})
    else:
        return jsonify({"error": f"Sale {sale_name} not found"}), 404

# Updated live feed endpoint to include both Lit, Resolv, and Fragmetric transactions
@app.route('/api/live-feed', methods=['GET'])
def live_feed():
    """Return the most recent transactions for the live feed"""
    # Removed cookie check to ensure we always try to fetch transactions
    
    # Get optional limit parameter
    limit = request.args.get('limit', default=10, type=int)
    limit = min(limit, 20)  # Max 20 transactions
    
    # Get optional sale parameter
    sale_filter = request.args.get('sale', default=None, type=str)
    
    if sale_filter == 'session':
        # Fetch live Session Protocol transactions
        try:
            transactions = get_recent_session_transactions(limit)
            # Make sure each transaction has all required fields
            for tx in transactions:
                # Ensure hash is present and valid
                if not tx.get("hash") or tx["hash"] == "":
                    tx["hash"] = "0x0000000000000000000000000000000000000000000000000000000000000000"  # Placeholder
                
                # Ensure all transactions have the is_live flag
                tx["is_live"] = True
                
                # Add sale name for proper logo display
                tx["sale"] = "session"
                
            return jsonify({
                "transactions": transactions,
                "count": len(transactions)
            })
        except Exception as e:
            print(f"Error fetching Session transactions: {str(e)}")
            return jsonify({"error": f"Failed to load Session transactions: {str(e)}"}), 500
    elif sale_filter == 'lit' or sale_filter == 'resolv' or sale_filter == 'fragmetric':
        # Use existing code for other sales
        # ... [existing code for other sale filters]
        pass
    else:
        # Combined feed with live and static data
        transactions = []
        
        # Add Session transactions (live data) first - they should be most recent
        try:
            session_txs = get_recent_session_transactions(limit)
            for tx in session_txs:
                # Make sure we have a valid hash
                if not tx.get("hash") or tx["hash"] == "":
                    tx["hash"] = "0x0000000000000000000000000000000000000000000000000000000000000000"  # Placeholder
                
                # Ensure all transactions have the is_live flag
                tx["is_live"] = True
                
                # Add sale name for proper logo display
                tx["sale"] = "session"
                
            transactions.extend(session_txs)
        except Exception as e:
            print(f"Error loading Session transactions for live feed: {str(e)}")
        
        # Add static data for other sales
        # Add Lit transactions
        if 'lit' in STATIC_DATA:
            for deposit in STATIC_DATA['lit']['deposits']:
                tx = {
                    "from": deposit["address"],
                    "amount": deposit["amount"],
                    "hash": "0x0000000000000000000000000000000000000000000000000000000000000000",  # Placeholder hash
                    "timestamp": "0",  # Placeholder timestamp
                    "sale": "lit",
                    "is_live": False
                }
                transactions.append(tx)
        
        # Add Resolv transactions
        if 'resolv' in STATIC_DATA:
            for deposit in STATIC_DATA['resolv']['deposits']:
                tx = {
                    "from": deposit["address"],
                    "amount": deposit["amount"],
                    "hash": "0x0000000000000000000000000000000000000000000000000000000000000000",  # Placeholder hash
                    "timestamp": "0",  # Placeholder timestamp
                    "sale": "resolv",
                    "is_live": False
                }
                transactions.append(tx)
                
        # Add Fragmetric transactions from fragmetric.json
        try:
            with open('fragmetric.json', 'r') as f:
                fragmetric_data = json.load(f)
                
            for item in fragmetric_data:
                tx = {
                    "from": item["address"],
                    "amount": item["usdc_balance"],
                    "hash": "0x0000000000000000000000000000000000000000000000000000000000000000",  # Placeholder hash
                    "timestamp": "0",  # Placeholder timestamp
                    "sale": "fragmetric",
                    "is_live": False
                }
                transactions.append(tx)
        except Exception as e:
            print(f"Error loading Fragmetric data for live feed: {str(e)}")
        
        # Sort by timestamp first if available, otherwise by amount
        transactions_with_timestamp = [tx for tx in transactions if tx.get("timestamp") and tx["timestamp"] != "0"]
        transactions_without_timestamp = [tx for tx in transactions if not tx.get("timestamp") or tx["timestamp"] == "0"]
        
        if transactions_with_timestamp:
            transactions_with_timestamp.sort(key=lambda x: x["timestamp"], reverse=True)
        
        if transactions_without_timestamp:
            transactions_without_timestamp.sort(key=lambda x: x["amount"], reverse=True)
        
        # Combine the sorted lists, prioritizing transactions with timestamps
        sorted_transactions = transactions_with_timestamp + transactions_without_timestamp
        transactions = sorted_transactions[:limit]  # Limit after combining
    
    return jsonify({
        "transactions": transactions,
        "count": len(transactions)
    })

@app.route('/api/<string:sale_name>/deposits', methods=['GET'])
def sale_deposits(sale_name):
    if sale_name == 'lit':
        return lit_deposits()
    elif sale_name == 'resolv':
        return resolv_deposits()
    elif sale_name == 'fragmetric':
        return fragmetric_deposits()
    elif sale_name == 'session':
        return session_deposits()
    
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
    
    if sale_name in STATIC_DATA:
        # For all sales, use static data
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
    
    if sale_name == 'lit':
        return lit_stats()
    elif sale_name == 'resolv':
        return resolv_stats()
    elif sale_name == 'fragmetric':
        return fragmetric_stats()
    elif sale_name == 'session':
        return session_stats()
    
    if sale_name in STATIC_DATA:
        # For all sales, use static data
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
    
    response_data = {
        "total_investment": total_investment,
        "total_investors": total_investors,
        "highest_allocation": highest_allocation,
        "lowest_allocation": lowest_allocation,
        "average_allocation": average_allocation,
        "top_investors": top_investors
    }
    
    return jsonify(response_data)

def get_all_individual_investments():
    """Get all individual investments across all sales for accurate median calculation"""
    all_investments = []
    
    # Get investments from static data
    for sale_name, sale_data in STATIC_DATA.items():
        if 'deposits' in sale_data:
            for deposit in sale_data['deposits']:
                all_investments.append(deposit["amount"])
    
    # Add Fragmetric data from fragmetric.json
    try:
        with open('fragmetric.json', 'r') as f:
            fragmetric_data = json.load(f)
            
        for item in fragmetric_data:
            all_investments.append(item['usdc_balance'])
    except Exception as e:
        print(f"Error loading Fragmetric data for investments: {str(e)}")
    
    # Add Session data (live)
    try:
        transfers = get_session_usdc_deposits()
        deposits_list = aggregate_session_deposits(transfers)
        
        for deposit in deposits_list:
            all_investments.append(deposit["amount"])
    except Exception as e:
        print(f"Error loading Session data for investments: {str(e)}")
    
    return all_investments

# Global stats endpoint with caching and improved integration
@app.route('/api/global-stats', methods=['GET'])
@cached('global_stats', 'global_stats_timestamp')
def global_stats():
    """Return aggregated statistics for all sales combined"""
    # Reset cache to ensure fresh data
    cache['global_stats'] = None
    cache['global_stats_timestamp'] = 0
    
    # Get all individual investments from all sales
    investments = get_all_individual_investments()
    
    # Calculate statistics
    total_investment = sum(investments)
    total_investors = len(investments)
    average_investment = total_investment / total_investors if total_investors > 0 else 0
    
    # Calculate median investment (true median from all individual investments)
    median_investment = 0
    if investments:
        sorted_investments = sorted(investments)
        mid = len(sorted_investments) // 2
        median_investment = sorted_investments[mid] if len(sorted_investments) % 2 == 1 else (sorted_investments[mid-1] + sorted_investments[mid]) / 2
    
    # Calculate largest investment
    largest_investment = max(investments) if investments else 0
    
    # For investors in multiple sales, we need to track unique addresses
    investor_sales_count = {}
    
    # Collect unique investors and count their sales participation
    for source, data in STATIC_DATA.items():
        if not data or 'deposits' not in data:
            continue
        
        for deposit in data['deposits']:
            address = deposit.get('address', '').lower()
            if not address:
                continue
                
            if address not in investor_sales_count:
                investor_sales_count[address] = set()
            
            investor_sales_count[address].add(source)
    
    # Try to add Fragmetric data if available
    try:
        with open('fragmetric.json', 'r') as f:
            fragmetric_data = json.load(f)
            for deposit in fragmetric_data:
                address = deposit.get('address', '').lower()
                if not address:
                    continue
                    
                if address not in investor_sales_count:
                    investor_sales_count[address] = set()
                
                investor_sales_count[address].add('fragmetric')
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error processing Fragmetric data: {e}")
    
    # Add Session data (live)
    try:
        transfers = get_session_usdc_deposits()
        deposits_list = aggregate_session_deposits(transfers)
        
        for deposit in deposits_list:
            address = deposit.get('address', '').lower()
            if not address:
                continue
                
            if address not in investor_sales_count:
                investor_sales_count[address] = set()
            
            investor_sales_count[address].add('session')
    except Exception as e:
        print(f"Error processing Session data for global stats: {e}")
    
    # Calculate total sales participation (sum of all investors across all sales)
    total_sales_participation = sum(len(sales) for sales in investor_sales_count.values())
    
    # Calculate average sales per investor
    average_sales_per_investor = total_sales_participation / len(investor_sales_count) if investor_sales_count else 0
    
    # Find investors in multiple sales
    multi_sale_investors = sum(1 for sales in investor_sales_count.values() if len(sales) > 1)
    
    # Log the values for debugging
    print(f"API global_stats: total_investors={total_investors}, avg_investment={average_investment:.2f}, median={median_investment}")
    
    return jsonify({
        "total_investment": total_investment,
        "total_investors": total_investors,
        "average_investment": average_investment,
        "median_investment": median_investment,
        "largest_investment": largest_investment,
        "average_sales_per_investor": average_sales_per_investor,
        "multi_sale_investors": multi_sale_investors
    })

# Top investors endpoint with modified ranking that preserves ranks during search
@app.route('/api/top-investors', methods=['GET'])
def top_investors():
    """Return aggregated data for top investors across all sales"""
    # Get optional pagination parameters
    page = request.args.get('page', default=1, type=int)
    limit = request.args.get('limit', default=100, type=int)
    sort = request.args.get('sort', default='total', type=str)  # 'total' or 'sales'
    search = request.args.get('search', default='', type=str)  # For address search
    
    # Limit values for safety
    limit = min(limit, 500)  # Max 500 per page
    page = max(page, 1)      # Min page 1
    
    # Initialize dict to store aggregated investor data
    investors = {}
    
    # Process all sales from static data
    for sale_name, sale_data in STATIC_DATA.items():
        if 'deposits' in sale_data:
            for deposit in sale_data['deposits']:
                address = deposit['address'].lower()
                amount = deposit['amount']
                
                if address not in investors:
                    investors[address] = {
                        'address': address,
                        'total_invested': 0,
                        'sales_participated': 0,
                        'sales': {}
                    }
                
                # If this is the first time we're seeing this address for this sale
                if sale_name not in investors[address]['sales']:
                    investors[address]['sales_participated'] += 1
                    investors[address]['sales'][sale_name] = amount
                else:
                    # Add to existing amount for this sale
                    investors[address]['sales'][sale_name] += amount
                
                # Update total invested amount
                investors[address]['total_invested'] += amount
    
    # Add Fragmetric data from fragmetric.json
    try:
        with open('fragmetric.json', 'r') as f:
            fragmetric_data = json.load(f)
            
        for item in fragmetric_data:
            address = item['address'].lower()
            amount = item['usdc_balance']
            
            if address not in investors:
                investors[address] = {
                    'address': address,
                    'total_invested': 0,
                    'sales_participated': 0,
                    'sales': {}
                }
            
            # If this is the first time we're seeing this address for fragmetric
            if 'fragmetric' not in investors[address]['sales']:
                investors[address]['sales_participated'] += 1
                investors[address]['sales']['fragmetric'] = amount
            else:
                # Add to existing amount for fragmetric
                investors[address]['sales']['fragmetric'] += amount
            
            # Update total invested amount
            investors[address]['total_invested'] += amount
    except Exception as e:
        print(f"Error loading Fragmetric data for top investors: {str(e)}")
                
    # Add Session data
    try:
        transfers = get_session_usdc_deposits()
        deposits_list = aggregate_session_deposits(transfers)
        
        for deposit in deposits_list:
            address = deposit['address'].lower()
            amount = deposit['amount']
            
            if address not in investors:
                investors[address] = {
                    'address': address,
                    'total_invested': 0,
                    'sales_participated': 0,
                    'sales': {}
                }
            
            # If this is the first time we're seeing this address for session
            if 'session' not in investors[address]['sales']:
                investors[address]['sales_participated'] += 1
                investors[address]['sales']['session'] = amount
            else:
                # Add to existing amount for session
                investors[address]['sales']['session'] += amount
            
            # Update total invested amount
            investors[address]['total_invested'] += amount
    except Exception as e:
        print(f"Error loading Session data for top investors: {str(e)}")
                
    # Convert to list for sorting
    investors_list = list(investors.values())
    
    # Sort the list
    if sort == 'sales':
        investors_list.sort(key=lambda x: (x['sales_participated'], x['total_invested']), reverse=True)
    else:  # Default sort by total invested
        investors_list.sort(key=lambda x: x['total_invested'], reverse=True)
    
    # Add global rank to all investors BEFORE applying search filter
    for i, investor in enumerate(investors_list):
        investor['rank'] = i + 1
    
    # Store original total before applying search
    total_investors_original = len(investors_list)
    
    # Apply search filter AFTER assigning global ranks
    if search:
        investors_list = [
            investor for investor in investors_list
            if search.lower() in investor['address'].lower()
        ]
    
    # Calculate pagination
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_investors = investors_list[start_idx:end_idx]
    
    return jsonify({
        "investors": paginated_investors,
        "page": page,
        "limit": limit,
        "total_investors": len(investors_list),
        "total_investors_original": total_investors_original,
        "total_pages": (len(investors_list) + limit - 1) // limit
    })

# Endpoint to get data for a specific investor
@app.route('/api/investor/<string:address>', methods=['GET'])
def investor_detail(address):
    """Return detailed data for a specific investor"""
    address = address.lower()
    investor_data = {
        'address': address,
        'total_invested': 0,
        'sales_participated': 0,
        'sales': []
    }
    
    # Process all sales from static data
    for sale_name, sale_data in STATIC_DATA.items():
        if 'deposits' in sale_data:
            for deposit in sale_data['deposits']:
                if deposit['address'].lower() == address:
                    # Add to sales list
                    investor_data['sales'].append({
                        'sale': sale_name,
                        'amount': deposit['amount']
                    })
                    investor_data['total_invested'] += deposit['amount']
    
    # Add Fragmetric data from fragmetric.json
    try:
        with open('fragmetric.json', 'r') as f:
            fragmetric_data = json.load(f)
            
        for item in fragmetric_data:
            if item['address'].lower() == address:
                # Add to sales list
                investor_data['sales'].append({
                    'sale': 'fragmetric',
                    'amount': item['usdc_balance']
                })
                investor_data['total_invested'] += item['usdc_balance']
                break  # Found the investor in fragmetric data, no need to continue
    except Exception as e:
        print(f"Error loading Fragmetric data for investor detail: {str(e)}")
    
    # Add Session data
    try:
        transfers = get_session_usdc_deposits()
        deposits_list = aggregate_session_deposits(transfers)
        
        for deposit in deposits_list:
            if deposit['address'].lower() == address:
                # Add to sales list
                investor_data['sales'].append({
                    'sale': 'session',
                    'amount': deposit['amount']
                })
                investor_data['total_invested'] += deposit['amount']
                break  # Found the investor in Session data, no need to continue
    except Exception as e:
        print(f"Error loading Session data for investor detail: {str(e)}")
    
    # Remove duplicates and aggregate by sale
    sales_dict = {}
    for sale in investor_data['sales']:
        sale_name = sale['sale']
        if sale_name in sales_dict:
            sales_dict[sale_name] += sale['amount']
        else:
            sales_dict[sale_name] = sale['amount']
    
    # Convert back to list and sort by amount
    investor_data['sales'] = [
        {'sale': sale, 'amount': amount}
        for sale, amount in sales_dict.items()
    ]
    investor_data['sales'].sort(key=lambda x: x['amount'], reverse=True)
    
    # Update sales participated count
    investor_data['sales_participated'] = len(investor_data['sales'])
    
    return jsonify(investor_data)

@app.route('/api/investor/<address>')
def get_investor_details(address):
    try:
        # Get all deposits for this investor from static data
        investor_data = {
            'total_investment': 0,
            'current_value': 0,
            'profit_loss': 0,
            'roi': 0
        }
        
        # Check static data first
        if 'silencio' in STATIC_DATA:
            for deposit in STATIC_DATA['silencio']['deposits']:
                if deposit['address'].lower() == address.lower():
                    investor_data['total_investment'] += deposit['amount']
        
        # Get current token price directly without making an HTTP request
        try:
            # Call CoinGecko API directly
            api_url = f"https://api.coingecko.com/api/v3/coins/silencio?x_cg_demo_api_key=CG-4Fnx2x1Ga65oHP6HufVGevXh"
            response = requests.get(api_url)
            
            if response.status_code == 200:
                data = response.json()
                current_price = data.get('market_data', {}).get('current_price', {}).get('usd', 0)
            else:
                print(f"Error fetching token price: {response.status_code}")
                current_price = 0
        except Exception as e:
            print(f"Error fetching token price: {str(e)}")
            current_price = 0
            
        if not current_price:
            return jsonify({'error': 'Failed to fetch current token price'}), 500
            
        # Calculate current value and profit/loss
        sale_price = 0.0006  # Fixed sale price for Silencio
        total_tokens = investor_data['total_investment'] / sale_price
        current_value = total_tokens * current_price
        profit_loss = current_value - investor_data['total_investment']
        roi = (profit_loss / investor_data['total_investment'] * 100) if investor_data['total_investment'] > 0 else 0
        
        return jsonify({
            'total_investment': investor_data['total_investment'],
            'current_value': current_value,
            'profit_loss': profit_loss,
            'roi': roi
        })
        
    except Exception as e:
        print(f"Error fetching investor details: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/fragmetric/data', methods=['GET'])
def fragmetric_data():
    """Get all data for Fragmetric from fragmetric.json file"""
    try:
        with open('fragmetric.json', 'r') as f:
            fragmetric_data = json.load(f)
            
        # Transform the data to match the expected format
        deposits = [{"address": item["address"], "amount": item["usdc_balance"]} for item in fragmetric_data]
        total_investment = sum(deposit["amount"] for deposit in deposits)
        
        return jsonify({
            "deposits": deposits,
            "count": len(deposits),
            "total": total_investment
        })
    except Exception as e:
        return jsonify({"error": f"Failed to load Fragmetric data: {str(e)}"}), 500

@app.route('/api/fragmetric/total-investment', methods=['GET'])
def fragmetric_total_investment():
    """Get total investment for Fragmetric sale"""
    try:
        with open('fragmetric.json', 'r') as f:
            fragmetric_data = json.load(f)
            
        total_investment = sum(item["usdc_balance"] for item in fragmetric_data)
        return jsonify({"total": total_investment})
    except Exception as e:
        return jsonify({"error": f"Failed to load Fragmetric data: {str(e)}"}), 500

@app.route('/api/fragmetric/deposits', methods=['GET'])
def fragmetric_deposits():
    """Get all deposits for Fragmetric sale"""
    try:
        with open('fragmetric.json', 'r') as f:
            fragmetric_data = json.load(f)
            
        # Transform the data to match the expected format
        deposits = [{"address": item["address"], "amount": item["usdc_balance"]} for item in fragmetric_data]
        
        return jsonify({
            "deposits": deposits,
            "count": len(deposits)
        })
    except Exception as e:
        return jsonify({"error": f"Failed to load Fragmetric data: {str(e)}"}), 500

@app.route('/api/fragmetric/stats', methods=['GET'])
def fragmetric_stats():
    # Check if we have the static data
    if 'fragmetric' not in STATIC_DATA:
        return jsonify({'error': 'No Fragmetric data available'}), 404
        
    # Calculate statistics from deposits
    deposits = STATIC_DATA['fragmetric']['deposits']
    
    if not deposits:
        return jsonify({
            'average': 0,
            'median': 0,
            'highest': 0,
            'lowest': 0,
            'total': 0,
            'num_investors': 0
        })
    
    # Extract amounts
    amounts = [d['amount'] for d in deposits]
    sorted_amounts = sorted(amounts)
    
    stats = {
        'average': sum(amounts) / len(amounts),
        'median': sorted_amounts[len(sorted_amounts) // 2] if len(sorted_amounts) % 2 != 0 else 
                 (sorted_amounts[len(sorted_amounts) // 2 - 1] + sorted_amounts[len(sorted_amounts) // 2]) / 2,
        'highest': max(amounts),
        'lowest': min(amounts),
        'total': sum(amounts),
        'num_investors': len(amounts)
    }
    
    return jsonify(stats)

# Add a new endpoint to proxy CoinGecko API requests
@app.route('/api/proxy/coingecko/coins/<coin_id>', methods=['GET'])
def proxy_coingecko(coin_id):
    try:
        # Get CoinGecko API key from request or use the default one
        api_key = request.args.get('api_key', 'CG-4Fnx2x1Ga65oHP6HufVGevXh')
        
        # Make the request to CoinGecko
        api_url = f"https://api.coingecko.com/api/v3/coins/{coin_id}?x_cg_demo_api_key={api_key}"
        response = requests.get(api_url)
        
        # Return the response data
        return jsonify(response.json()), response.status_code
    except Exception as e:
        print(f"Error proxying CoinGecko API request: {str(e)}")
        return jsonify({'error': 'Failed to fetch data from CoinGecko API'}), 500

# Add a simpler endpoint for just price data
@app.route('/api/proxy/coingecko/price/<coin_id>', methods=['GET'])
def proxy_coingecko_price(coin_id):
    try:
        # Get CoinGecko API key from request or use the default one
        api_key = request.args.get('api_key', 'CG-4Fnx2x1Ga65oHP6HufVGevXh')
        
        # Make the request to CoinGecko
        api_url = f"https://api.coingecko.com/api/v3/coins/{coin_id}?x_cg_demo_api_key={api_key}"
        response = requests.get(api_url)
        
        if response.status_code != 200:
            return jsonify({'error': 'Failed to fetch price data'}), response.status_code
            
        data = response.json()
        
        # Extract only the price-related data
        price_data = {
            'current_price': data.get('market_data', {}).get('current_price', {}).get('usd', 0),
            'ath': data.get('market_data', {}).get('ath', {}).get('usd', 0),
            'atl': data.get('market_data', {}).get('atl', {}).get('usd', 0)
        }
        
        return jsonify(price_data)
    except Exception as e:
        print(f"Error proxying CoinGecko price API request: {str(e)}")
        return jsonify({'error': 'Failed to fetch price data from CoinGecko API'}), 500

@app.route('/fragmetric.json')
def serve_fragmetric_json():
    """Directly serve the fragmetric.json file"""
    return send_from_directory('.', 'fragmetric.json')

@app.route('/api/all-investments', methods=['GET'])
def all_investments():
    """Get all individual investments data for debugging statistics"""
    investments = get_all_individual_investments()
    
    # Calculate statistics
    investments.sort()
    total = sum(investments)
    count = len(investments)
    
    # Calculate median properly
    if count > 0:
        mid = count // 2
        median = investments[mid] if count % 2 == 1 else (investments[mid-1] + investments[mid]) / 2
    else:
        median = 0
        
    average = total / count if count > 0 else 0
    
    response_data = {
        "total_investment": total,
        "count": count,
        "average": average,
        "median": median,
        "min": min(investments) if investments else 0,
        "max": max(investments) if investments else 0,
        "investments": investments
    }
    
    return jsonify(response_data)

# New endpoint to get the original cased version of a Solana address
@app.route('/api/original-address', methods=['GET'])
def get_original_address():
    """Get the original case-sensitive version of a Solana address"""
    address = request.args.get('address', '').lower()
    
    # Check if we have this address in our map
    if address in SOLANA_ADDRESS_MAP:
        return jsonify({
            'original_address': SOLANA_ADDRESS_MAP[address],
            'found': True
        })
    
    # If not found, check Fragmetric data again (in case it was updated)
    try:
        with open('fragmetric.json', 'r') as f:
            fragmetric_data = json.load(f)
        
        for entry in fragmetric_data:
            if 'address' in entry and entry['address'].lower() == address:
                return jsonify({
                    'original_address': entry['address'],
                    'found': True
                })
    except Exception as e:
        print(f"Error checking Fragmetric data for address: {str(e)}")
    
    # Return not found
    return jsonify({
        'found': False,
        'message': 'Address not found in original case format'
    })

if __name__ == "__main__":
    # Load static data before starting the server
    print("Loading static data...")
    try:
        with open('static_data.json', 'r') as f:
            STATIC_DATA = json.load(f)
        print(f"Loaded static data for {len(STATIC_DATA)} sales")
    except Exception as e:
        print(f"Error loading static data: {str(e)}")
        STATIC_DATA = {}
        
    # Start the server
    app.run(debug=True, host='0.0.0.0', port=5000)
