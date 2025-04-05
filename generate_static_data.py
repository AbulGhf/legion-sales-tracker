import json
import requests
import time

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

def get_lit_usdc_deposits():
    """Get all USDC transfers to the Lit Protocol sale contracts"""
    print("Fetching USDC transfers to Lit Protocol contracts...")
    
    all_transfers = []
    
    for contract_address in LIT_CONTRACTS:
        page_key = None
        contract_transfers = []
        
        print(f"Fetching transfers for contract: {contract_address}")
        
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
                    print(f"Fetched {len(transfers)} transfers, getting next page...")
                else:
                    print(f"Fetched {len(transfers)} transfers, no more pages.")
                    break
            else:
                break
        
        all_transfers.extend(contract_transfers)
    
    print(f"Total transfers fetched: {len(all_transfers)}")
    return all_transfers

def aggregate_lit_deposits(transfers):
    """Aggregate deposits by address for Lit Protocol"""
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
print("Starting Lit Protocol data collection...")

# Try to load existing static data
try:
    with open('static_data.json', 'r') as f:
        static_data = json.load(f)
    print(f"Loaded existing static data for {len(static_data)} sales")
except Exception as e:
    print(f"Starting with fresh static data: {str(e)}")
    static_data = {}

# Fetch and process Lit Protocol data
start_time = time.time()
try:
    transfers = get_lit_usdc_deposits()
    deposits = aggregate_lit_deposits(transfers)
    
    total_investment = sum(deposit["amount"] for deposit in deposits)
    
    lit_data = {
        'total': total_investment,
        'deposits': deposits,
        'count': len(deposits)
    }
    
    print(f"\n✅ Lit Protocol: Found {lit_data['count']} investors with ${lit_data['total']:.2f} total investment")
    print(f"   Data collection completed in {time.time() - start_time:.2f} seconds")
    
    # Add to static data
    static_data['lit'] = lit_data
    
    # Save updated static data
    with open('static_data.json', 'w') as f:
        json.dump(static_data, f, indent=2)
    
    print("\n✅ Updated static_data.json with Lit Protocol data")
    print(f"Total sales in static data: {len(static_data)}")
    
except Exception as e:
    print(f"\n❌ Error processing Lit Protocol data: {str(e)}")