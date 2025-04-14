import json
import requests
import time

# Constants for Resolv Protocol (Ethereum)
RESOLV_ALCHEMY_API_KEY = "uuLBOZte0sf0z3XRVPPsPKMrfuQ1gqHv"
RESOLV_ALCHEMY_URL = f"https://eth-mainnet.g.alchemy.com/v2/{RESOLV_ALCHEMY_API_KEY}"  # Ethereum endpoint
RESOLV_CONTRACTS = [
    "0xee6deedb6c1535E4912eE5db48E08b36FD2fAA8f",
    "0x5Fdab714fe8BB9d40C8B1e5f7c2BacD8E7f869d8"
]
RESOLV_USDC_CONTRACT = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"  # Ethereum USDC contract

def get_resolv_usdc_deposits():
    """Get all USDC transfers to the Resolv Protocol sale contracts"""
    print("Fetching USDC transfers to Resolv Protocol contracts...")
    
    all_transfers = []
    
    for contract_address in RESOLV_CONTRACTS:
        page_key = None
        contract_transfers = []
        
        print(f"Fetching transfers for contract: {contract_address}")
        
        while True:
            params = {
                "fromBlock": "0x0",
                "toBlock": "latest",
                "toAddress": contract_address,
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
        
        all_transfers.extend(contract_transfers)
    
    print(f"Total transfers fetched: {len(all_transfers)}")
    return all_transfers

def aggregate_resolv_deposits(transfers):
    """Aggregate deposits by address for Resolv Protocol"""
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
print("Starting Resolv Protocol data collection...")

# Try to load existing static data
try:
    with open('static_data.json', 'r') as f:
        static_data = json.load(f)
    print(f"Loaded existing static data for {len(static_data)} sales")
except Exception as e:
    print(f"Starting with fresh static data: {str(e)}")
    static_data = {}

# Fetch and process Resolv Protocol data
start_time = time.time()
try:
    transfers = get_resolv_usdc_deposits()
    deposits = aggregate_resolv_deposits(transfers)
    
    total_investment = sum(deposit["amount"] for deposit in deposits)
    
    resolv_data = {
        'total': total_investment,
        'deposits': deposits,
        'count': len(deposits)
    }
    
    print(f"\n✅ Resolv Protocol: Found {resolv_data['count']} investors with ${resolv_data['total']:.2f} total investment")
    print(f"   Data collection completed in {time.time() - start_time:.2f} seconds")
    
    # Add to static data
    static_data['resolv'] = resolv_data
    
    # Save updated static data
    with open('static_data.json', 'w') as f:
        json.dump(static_data, f, indent=2)
    
    print("\n✅ Updated static_data.json with Resolv Protocol data")
    print(f"Total sales in static data: {len(static_data)}")
    
except Exception as e:
    print(f"\n❌ Error processing Resolv Protocol data: {str(e)}")