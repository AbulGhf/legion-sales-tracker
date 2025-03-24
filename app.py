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

# Cache for active sales (now only Lit Protocol)
cache = {
    'lit_deposits': None,
    'lit_deposits_timestamp': 0,
    'lit_total': None,
    'lit_total_timestamp': 0,
    'lit_tier1_deposits': None,
    'lit_tier1_deposits_timestamp': 0,
    'lit_tier2_deposits': None,
    'lit_tier2_deposits_timestamp': 0,
    'lit_tier3_deposits': None,
    'lit_tier3_deposits_timestamp': 0,
    'global_stats': None,
    'global_stats_timestamp': 0
}

# Cache expiry time (15 minutes in seconds)
CACHE_EXPIRY = 900  # 15 minutes

# Constants for Lit Protocol (Arbitrum)
LIT_ALCHEMY_API_KEY = "uuLBOZte0sf0z3XRVPPsPKMrfuQ1gqHv"
LIT_ALCHEMY_URL = f"https://arb-mainnet.g.alchemy.com/v2/{LIT_ALCHEMY_API_KEY}"
LIT_TIER1_CONTRACT = "0x5fdab714fe8bb9d40c8b1e5f7c2bacd8e7f869d8"
LIT_TIER2_CONTRACT = "0x61a9c4fae2cf5f9fd88799a8423800cf33f951ef"
LIT_TIER3_CONTRACT = "0x81ee48c2bb20b21bb20c95b24a36010f1dd9bce7"
LIT_USDC_CONTRACT = "0xaf88d065e77c8cc2239327c5edb3a432268e5831"  # Arbitrum USDC contract

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
def get_lit_usdc_deposits(contract_address=None):
    """Get all USDC transfers to the Lit Protocol sale contracts"""
    
    all_transfers = []
    page_key = None
    
    # If a specific contract is provided, only fetch for that contract
    # Otherwise, fetch for all three tier contracts
    if contract_address:
        target_contracts = [contract_address]
    else:
        target_contracts = [LIT_TIER1_CONTRACT, LIT_TIER2_CONTRACT, LIT_TIER3_CONTRACT]
    
    for target_contract in target_contracts:
        contract_transfers = []
        contract_page_key = None
        
        print(f"Fetching USDC transfers to Lit Protocol contract: {target_contract}")
        
        while True:
            params = {
                "fromBlock": "0x0",
                "toBlock": "latest",
                "toAddress": target_contract,
                "contractAddresses": [LIT_USDC_CONTRACT],
                "category": ["erc20"],
                "withMetadata": True,
                "excludeZeroValue": True,
                "maxCount": "0x64"  # Hex for 100
            }
            
            if contract_page_key:
                params["pageKey"] = contract_page_key
            
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
                
                # Add contract tier info to each transfer
                for transfer in transfers:
                    if target_contract == LIT_TIER1_CONTRACT:
                        transfer["tier"] = 1
                    elif target_contract == LIT_TIER2_CONTRACT:
                        transfer["tier"] = 2
                    elif target_contract == LIT_TIER3_CONTRACT:
                        transfer["tier"] = 3
                
                contract_transfers.extend(transfers)
                
                # Check if there are more pages
                if "pageKey" in data["result"]:
                    contract_page_key = data["result"]["pageKey"]
                    print(f"Fetched {len(transfers)} transfers for tier contract, getting next page...")
                else:
                    print(f"Fetched {len(transfers)} transfers for tier contract, no more pages.")
                    break
            else:
                break
        
        print(f"Total transfers fetched for contract {target_contract}: {len(contract_transfers)}")
        all_transfers.extend(contract_transfers)
    
    print(f"Total transfers fetched across all contracts: {len(all_transfers)}")
    return all_transfers

def aggregate_lit_deposits(transfers, tier=None):
    """Aggregate deposits by address for Lit Protocol, optionally filtering by tier"""
    
    deposits_by_address = {}
    
    for transfer in transfers:
        # If tier is specified, only include transfers from that tier
        if tier is not None and transfer.get("tier") != tier:
            continue
            
        # Check if it's a USDC transfer
        if transfer.get("asset") in ["USDC", "USD Coin"]:
            from_address = transfer["from"].lower()
            amount = float(transfer["value"])
            tier_value = transfer.get("tier", 0)  # Default to 0 if no tier
            
            if from_address in deposits_by_address:
                deposits_by_address[from_address]["amount"] += amount
                if tier_value not in deposits_by_address[from_address]["tiers"]:
                    deposits_by_address[from_address]["tiers"].append(tier_value)
            else:
                deposits_by_address[from_address] = {
                    "address": from_address,
                    "amount": amount,
                    "tiers": [tier_value]
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
            "tier": transfer.get("tier", 0)
        }
        transactions.append(tx)
    
    # Sort by timestamp (most recent first)
    if transactions and 'timestamp' in transactions[0] and transactions[0]['timestamp']:
        transactions.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Return the limited number
    return transactions[:limit]

# Route handlers
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

# HTML pages for each sale
@app.route('/<string:sale_name>.html')
def sale_page(sale_name):
    return send_from_directory('static', f'{sale_name}.html')

# API Endpoints for Lit Protocol (with caching)
@app.route('/api/lit/total-investment', methods=['GET'])
@cached('lit_total', 'lit_total_timestamp')
def lit_total_investment():
    # Get all deposits and sum them up
    transfers = get_lit_usdc_deposits()
    deposits_list = aggregate_lit_deposits(transfers)
    total = sum(item["amount"] for item in deposits_list)
    return jsonify({"total": total})

@app.route('/api/lit/deposits', methods=['GET'])
@cached('lit_deposits', 'lit_deposits_timestamp')
def lit_deposits():
    transfers = get_lit_usdc_deposits()
    deposits_list = aggregate_lit_deposits(transfers)
    
    return jsonify({
        "deposits": deposits_list,
        "count": len(deposits_list)
    })

# API Endpoints for Lit Protocol Tier 1 (with caching)
@app.route('/api/lit/tier1/deposits', methods=['GET'])
@cached('lit_tier1_deposits', 'lit_tier1_deposits_timestamp')
def lit_tier1_deposits():
    transfers = get_lit_usdc_deposits(LIT_TIER1_CONTRACT)
    deposits_list = aggregate_lit_deposits(transfers, tier=1)
    
    return jsonify({
        "deposits": deposits_list,
        "count": len(deposits_list)
    })

# API Endpoints for Lit Protocol Tier 2 (with caching)
@app.route('/api/lit/tier2/deposits', methods=['GET'])
@cached('lit_tier2_deposits', 'lit_tier2_deposits_timestamp')
def lit_tier2_deposits():
    transfers = get_lit_usdc_deposits(LIT_TIER2_CONTRACT)
    deposits_list = aggregate_lit_deposits(transfers, tier=2)
    
    return jsonify({
        "deposits": deposits_list,
        "count": len(deposits_list)
    })

# API Endpoints for Lit Protocol Tier 3 (with caching)
@app.route('/api/lit/tier3/deposits', methods=['GET'])
@cached('lit_tier3_deposits', 'lit_tier3_deposits_timestamp')
def lit_tier3_deposits():
    transfers = get_lit_usdc_deposits(LIT_TIER3_CONTRACT)
    deposits_list = aggregate_lit_deposits(transfers, tier=3)
    
    return jsonify({
        "deposits": deposits_list,
        "count": len(deposits_list)
    })

# Generic API Endpoints for all sales
@app.route('/api/<string:sale_name>/total-investment', methods=['GET'])
def sale_total_investment(sale_name):
    if sale_name == 'lit':
        return lit_total_investment()
    
    if sale_name in STATIC_DATA:
        return jsonify({"total": STATIC_DATA[sale_name]['total']})
    else:
        return jsonify({"error": f"Sale {sale_name} not found"}), 404

# New endpoint for the live feed
@app.route('/api/live-feed', methods=['GET'])
def live_feed():
    """Return the most recent transactions for the live feed"""
    # Get optional limit parameter
    limit = request.args.get('limit', default=10, type=int)
    limit = min(limit, 20)  # Max 20 transactions
    
    # Get recent transactions for Lit (the active sale)
    transactions = get_recent_lit_transactions(limit)
    
    return jsonify({
        "transactions": transactions,
        "count": len(transactions)
    })

@app.route('/api/<string:sale_name>/deposits', methods=['GET'])
def sale_deposits(sale_name):
    if sale_name == 'lit':
        return lit_deposits()
    
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
    
    if sale_name == 'lit':
        # For Lit, fetch real-time data
        transfers = get_lit_usdc_deposits()
        deposits_list = aggregate_lit_deposits(transfers)
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
    
    if sale_name == 'lit':
        # For Lit, fetch real-time data
        transfers = get_lit_usdc_deposits()
        deposits_list = aggregate_lit_deposits(transfers)
        
        # Add tier specific counts
        tier1_transfers = get_lit_usdc_deposits(LIT_TIER1_CONTRACT)
        tier1_deposits = aggregate_lit_deposits(tier1_transfers, tier=1)
        
        tier2_transfers = get_lit_usdc_deposits(LIT_TIER2_CONTRACT)
        tier2_deposits = aggregate_lit_deposits(tier2_transfers, tier=2)
        
        tier3_transfers = get_lit_usdc_deposits(LIT_TIER3_CONTRACT)
        tier3_deposits = aggregate_lit_deposits(tier3_transfers, tier=3)
        
        tier_stats = {
            "tier1": {
                "total_investors": len(tier1_deposits),
                "total_investment": sum(item["amount"] for item in tier1_deposits) if tier1_deposits else 0
            },
            "tier2": {
                "total_investors": len(tier2_deposits),
                "total_investment": sum(item["amount"] for item in tier2_deposits) if tier2_deposits else 0
            },
            "tier3": {
                "total_investors": len(tier3_deposits),
                "total_investment": sum(item["amount"] for item in tier3_deposits) if tier3_deposits else 0
            }
        }
    elif sale_name in STATIC_DATA:
        # For concluded sales, use static data
        deposits_list = STATIC_DATA[sale_name]['deposits']
        tier_stats = None  # No tier data for static sales
    else:
        return jsonify({"error": f"Sale {sale_name} not found"}), 404
    
    # Calculate stats
    if deposits_list:
        if sale_name == 'lit':
            # Special handling for Lit with its structured deposits
            total_investment = sum(item["amount"] for item in deposits_list)
            total_investors = len(deposits_list)
            highest_allocation = max(deposits_list, key=lambda x: x["amount"])
            lowest_allocation = min(deposits_list, key=lambda x: x["amount"])
            average_allocation = total_investment / total_investors if total_investors > 0 else 0
            
            # Top 5 investors
            top_investors = sorted(deposits_list, key=lambda x: x["amount"], reverse=True)[:5]
        else:
            # Standard handling for other sales
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
    
    # Add tier stats if available
    if tier_stats:
        response_data["tier_stats"] = tier_stats
    
    return jsonify(response_data)

# Global stats endpoint with caching and improved integration
@app.route('/api/global-stats', methods=['GET'])
@cached('global_stats', 'global_stats_timestamp')
def global_stats():
    """Return aggregated statistics for all sales combined with caching"""
    # Initialize counters
    total_investment = 0
    total_investors_set = set()  # Use a set to prevent duplicate counting
    all_investments = []
    investor_sales_count = {}  # Track number of sales per investor
    investor_total_investments = {}  # Track total investments per investor
    
    # Process static data first (past sales)
    for sale_name, sale_data in STATIC_DATA.items():
        if 'deposits' in sale_data:
            for deposit in sale_data['deposits']:
                address = deposit['address'].lower()
                amount = deposit['amount']
                
                # Add to total investment
                total_investment += amount
                
                # Add investor to set
                total_investors_set.add(address)
                
                # Track individual investment (for median calculation)
                all_investments.append(amount)
                
                # Track sales participation
                if address not in investor_sales_count:
                    investor_sales_count[address] = set()
                    investor_total_investments[address] = 0
                investor_sales_count[address].add(sale_name)
                investor_total_investments[address] += amount
    
    # Process live Lit Protocol data
    try:
        # Get fresh Lit data
        transfers = get_lit_usdc_deposits()
        deposits_list = aggregate_lit_deposits(transfers)
        
        # Log the Lit data size to verify it's working
        print(f"Processing {len(deposits_list)} Lit deposits for global stats")
        
        for deposit in deposits_list:
            address = deposit['address'].lower()
            amount = deposit['amount']
            
            # Add to total investment
            total_investment += amount
            
            # Add investor to set
            total_investors_set.add(address)
            
            # Track individual investment
            all_investments.append(amount)
            
            # Track sales participation
            if address not in investor_sales_count:
                investor_sales_count[address] = set()
                investor_total_investments[address] = 0
            investor_sales_count[address].add('lit')
            investor_total_investments[address] += amount
    except Exception as e:
        print(f"Error fetching Lit data for global stats: {str(e)}")
    
    # Calculate statistics
    total_investors = len(total_investors_set)
    average_investment = total_investment / total_investors if total_investors > 0 else 0
    
    # Find largest individual investment (across all investors)
    largest_investment = max(investor_total_investments.values()) if investor_total_investments else 0
    
    # Find median investment
    if all_investments:
        all_investments.sort()
        mid = len(all_investments) // 2
        median_investment = all_investments[mid] if len(all_investments) % 2 == 1 else (all_investments[mid-1] + all_investments[mid]) / 2
    else:
        median_investment = 0
    
    # Calculate average sales per investor
    total_sales_participation = sum(len(sales) for sales in investor_sales_count.values())
    average_sales = total_sales_participation / total_investors if total_investors > 0 else 0
    
    # Find the investor with most sales
    most_active_sales = max(len(sales) for sales in investor_sales_count.values()) if investor_sales_count else 0
    
    # Log some stats to verify
    print(f"Global Stats: {total_investors} investors, ${total_investment:,.2f} invested, ${average_investment:,.2f} average")
    
    return jsonify({
        "total_investment": total_investment,
        "total_investors": total_investors,
        "average_investment": average_investment,
        "median_investment": median_investment,
        "largest_investment": largest_investment,
        "most_active_sales": most_active_sales,
        "average_sales": average_sales
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
    
    # Process static data first (past sales)
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
    
    # Process live Lit data
    try:
        transfers = get_lit_usdc_deposits()
        deposits_list = aggregate_lit_deposits(transfers)
        
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
            
            # If this is the first time we're seeing this address for Lit
            if 'lit' not in investors[address]['sales']:
                investors[address]['sales_participated'] += 1
                investors[address]['sales']['lit'] = amount
            else:
                # Add to existing amount for Lit
                investors[address]['sales']['lit'] += amount
            
            # Update total invested amount
            investors[address]['total_invested'] += amount
    except Exception as e:
        print(f"Error fetching Lit data: {str(e)}")
    
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
    total_investors = len(investors_list)
    total_pages = (total_investors + limit - 1) // limit if total_investors > 0 else 1
    
    # Adjust page if it's out of bounds after applying search
    page = min(page, total_pages)
    
    # Paginate the results
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_investors = investors_list[start_idx:end_idx]
    
    # Process the paginated investors to add additional data
    for investor in paginated_investors:
        # Convert sales dict to list for easier frontend processing
        investor['sales_list'] = [
            {'sale': sale, 'amount': amount}
            for sale, amount in investor['sales'].items()
        ]
        # Sort sales by amount
        investor['sales_list'].sort(key=lambda x: x['amount'], reverse=True)
    
    return jsonify({
        'investors': paginated_investors,
        'page': page,
        'limit': limit,
        'total_investors': total_investors_original,  # Always return the total count without search filter
        'total_pages': total_pages,
        'sort': sort,
        'filtered_count': total_investors  # Add a new field for the count after filtering
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
    
    # Process static data
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
    
    # Process live Lit data
    try:
        transfers = get_lit_usdc_deposits()
        deposits_list = aggregate_lit_deposits(transfers)
        
        for deposit in deposits_list:
            if deposit['address'].lower() == address:
                # Add to sales list
                investor_data['sales'].append({
                    'sale': 'lit',
                    'amount': deposit['amount'],
                    'tiers': deposit.get('tiers', [])
                })
                investor_data['total_invested'] += deposit['amount']
    except Exception as e:
        print(f"Error fetching Lit data: {str(e)}")
    
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

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)