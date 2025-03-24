import json
import requests
import time

# Constants for Skate Chain (Arbitrum)
SKATE_ALCHEMY_API_KEY = "uuLBOZte0sf0z3XRVPPsPKMrfuQ1gqHv"
SKATE_ALCHEMY_URL = f"https://arb-mainnet.g.alchemy.com/v2/{SKATE_ALCHEMY_API_KEY}"
SKATE_CONTRACT = "0xd4f787fc73cb2d12559d0a3158cb8b4d491fbe7a"
SKATE_USDC_CONTRACT = "0xaf88d065e77c8cc2239327c5edb3a432268e5831"  # Arbitrum USDC contract

def get_skate_usdc_deposits():
    """Get all USDC transfers to the Skate sale contract"""
    print("Fetching USDC transfers to Skate contract...")
    
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
                print(f"Fetched {len(transfers)} transfers, no more pages.")
                break
        else:
            break
    
    print(f"Total transfers fetched: {len(all_transfers)}")
    return all_transfers

def aggregate_skate_deposits(transfers):
    """Aggregate deposits by address for Skate"""
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
print("Starting Skate data collection...")

# Try to load existing static data
try:
    with open('static_data.json', 'r') as f:
        static_data = json.load(f)
    print(f"Loaded existing static data for {len(static_data)} sales")
except Exception as e:
    print(f"Starting with fresh static data: {str(e)}")
    static_data = {}

# Fetch and process Skate data
start_time = time.time()
try:
    transfers = get_skate_usdc_deposits()
    deposits = aggregate_skate_deposits(transfers)
    
    total_investment = sum(deposit["amount"] for deposit in deposits)
    
    skate_data = {
        'total': total_investment,
        'deposits': deposits,
        'count': len(deposits)
    }
    
    print(f"\n✅ Skate: Found {skate_data['count']} investors with ${skate_data['total']:.2f} total investment")
    print(f"   Data collection completed in {time.time() - start_time:.2f} seconds")
    
    # Add to static data
    static_data['skate'] = skate_data
    
    # Save updated static data
    with open('static_data.json', 'w') as f:
        json.dump(static_data, f, indent=2)
    
    print("\n✅ Updated static_data.json with Skate data")
    print(f"Total sales in static data: {len(static_data)}")
    
except Exception as e:
    print(f"\n❌ Error processing Skate data: {str(e)}")