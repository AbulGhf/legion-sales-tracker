import json
import requests
import time

# Constants for Session Data
SESSION_CONTRACTS = [
    "0x543Eb0BFB29803C28eC0A0Ed181683c915F44ED2",
    "0xD3472eD0F891ee9279ADFFC7e147bFCF8E72C790",
    "0x90cd2BBccdC85Ab75a14d2112ffa2A5cD42817A4"
]
ALCHEMY_API_KEY = "uuLBOZte0sf0z3XRVPPsPKMrfuQ1gqHv"
ALCHEMY_URL = f"https://arb-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"  # Arbitrum endpoint
USDC_CONTRACT = "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"  # Arbitrum USDC contract

def get_session_transfers():
    """Get all transfers to the Session contracts"""
    print("Fetching transfers to Session contracts on Arbitrum...")
    
    all_transfers = []
    
    for contract_address in SESSION_CONTRACTS:
        page_key = None
        contract_transfers = []
        
        print(f"Fetching transfers for contract: {contract_address}")
        
        while True:
            params = {
                "fromBlock": "0x0",
                "toBlock": "latest",
                "toAddress": contract_address,
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
                contract_transfers.extend(transfers)
                
                # Check if there are more pages
                if "pageKey" in data["result"]:
                    page_key = data["result"]["pageKey"]
                    print(f"Fetched {len(transfers)} transfers, getting next page...")
                else:
                    print(f"Fetched {len(transfers)} transfers, no more pages.")
                    break
            else:
                break
        
        print(f"Total transfers fetched for contract {contract_address}: {len(contract_transfers)}")
        all_transfers.extend(contract_transfers)
    
    print(f"Total transfers fetched across all contracts: {len(all_transfers)}")
    return all_transfers

def aggregate_session_deposits(transfers):
    """Aggregate deposits by address for Session"""
    print("Aggregating deposits by address...")
    
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
    
    print(f"Total unique investors: {len(deposits_list)}")
    return deposits_list

# Main execution
print("Starting Session data collection...")

# Try to load existing static data
try:
    with open('static_data.json', 'r') as f:
        static_data = json.load(f)
    print(f"Loaded existing static data for {len(static_data)} sales")
except Exception as e:
    print(f"Starting with fresh static data: {str(e)}")
    static_data = {}

# Fetch and process Session data
start_time = time.time()
try:
    transfers = get_session_transfers()
    deposits = aggregate_session_deposits(transfers)
    
    total_investment = sum(deposit["amount"] for deposit in deposits)
    
    session_data = {
        'total': total_investment,
        'deposits': deposits,
        'count': len(deposits)
    }
    
    print(f"\n✅ Session: Found {session_data['count']} investors with ${session_data['total']:.2f} total investment")
    print(f"   Data collection completed in {time.time() - start_time:.2f} seconds")
    
    # Add to static data
    static_data['session'] = session_data
    
    # Save updated static data
    with open('static_data.json', 'w') as f:
        json.dump(static_data, f, indent=2)
    
    print("\n✅ Updated static_data.json with Session data")
    print(f"Total sales in static data: {len(static_data)}")
    
except Exception as e:
    print(f"\n❌ Error processing Session data: {str(e)}")