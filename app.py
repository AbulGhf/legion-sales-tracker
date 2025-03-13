from flask import Flask, jsonify, render_template
import requests
import json
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Constants
ALCHEMY_API_KEY = "uuLBOZte0sf0z3XRVPPsPKMrfuQ1gqHv"
ALCHEMY_URL = f"https://arb-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
LEGION_CONTRACT = "0xd4f787fc73cb2d12559d0a3158cb8b4d491fbe7a"
USDC_CONTRACT = "0xaf88d065e77c8cc2239327c5edb3a432268e5831"


def get_total_usdc_balance():
    """Get the current USDC balance of the Legion sale contract"""
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "alchemy_getTokenBalances",
        "params": [LEGION_CONTRACT, [USDC_CONTRACT]]
    }
    
    response = requests.post(ALCHEMY_URL, json=payload)
    data = response.json()
    
    if "error" in data:
        print(f"Error fetching token balance: {data['error']['message']}")
        return 0
    
    # USDC has 6 decimals on Arbitrum
    if len(data["result"]["tokenBalances"]) > 0:
        balance_hex = data["result"]["tokenBalances"][0]["tokenBalance"]
        balance = int(balance_hex, 16) / 1e6
        return balance
    
    return 0


def get_usdc_deposits():
    """Get all USDC transfers to the Legion sale contract"""
    
    all_transfers = []
    page_key = None
    
    while True:
        params = {
            "fromBlock": "0x0",
            "toBlock": "latest",
            "toAddress": LEGION_CONTRACT,
            "contractAddresses": [USDC_CONTRACT],
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
        
        response = requests.post(ALCHEMY_URL, json=payload)
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


def aggregate_deposits(transfers):
    """Aggregate deposits by address"""
    
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
    
    # Convert to a list of tuples for sorting
    deposits_list = [(address, amount) for address, amount in deposits_by_address.items()]
    # Sort by amount in descending order
    deposits_list.sort(key=lambda x: x[1], reverse=True)
    
    return deposits_list


@app.route('/')
def index():
    return app.send_static_file('index.html')


@app.route('/api/total-investment', methods=['GET'])
def total_investment():
    total = get_total_usdc_balance()
    return jsonify({"total": total})


@app.route('/api/deposits', methods=['GET'])
def deposits():
    transfers = get_usdc_deposits()
    deposits_list = aggregate_deposits(transfers)
    
    # Convert to list of dictionaries for JSON
    deposits_data = [
        {"address": address, "amount": amount}
        for address, amount in deposits_list
    ]
    
    return jsonify({
        "deposits": deposits_data,
        "count": len(deposits_data)
    })


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)