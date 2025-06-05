import json
import requests
import time

# Constants for Intuition
INTUITION_CONTRACTS = [
    "0x81eE48c2bb20B21bB20C95B24a36010f1DD9BCe7",
    "0x81A00dA473D1BfF1D1b894c8a9b4C88464F15F9D"
]

ALCHEMY_API_KEY = "uuLBOZte0sf0z3XRVPPsPKMrfuQ1gqHv"
ALCHEMY_ETH_URL = f"https://eth-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"  # Ethereum mainnet endpoint
USDC_CONTRACT_ETH = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"  # Ethereum mainnet USDC contract

def get_intuition_transfers():
    """Get all transfers to the Intuition contracts"""
    print("Fetching transfers to Intuition contracts on Ethereum mainnet...")
    
    all_transfers = []
    
    for contract_address in INTUITION_CONTRACTS:
        page_key = None
        contract_transfers = []
        
        print(f"Fetching transfers for contract: {contract_address}")
        
        while True:
            params = {
                "fromBlock": "0x0",
                "toBlock": "latest",
                "toAddress": contract_address,
                "contractAddresses": [USDC_CONTRACT_ETH],
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
            
            response = requests.post(ALCHEMY_ETH_URL, json=payload)
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
    
    print(f"Total Intuition transfers fetched across all contracts: {len(all_transfers)}")
    return all_transfers

def aggregate_intuition_deposits(transfers):
    """Aggregate deposits by address for Intuition"""
    print("Aggregating Intuition deposits by address...")
    
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
    
    print(f"Total unique Intuition investors: {len(deposits_list)}")
    return deposits_list

# Main execution
print("Starting Intuition data collection...")

# Try to load existing static data
try:
    with open('static_data.json', 'r') as f:
        static_data = json.load(f)
    print(f"Loaded existing static data for {len(static_data)} sales")
except Exception as e:
    print(f"Starting with fresh static data: {str(e)}")
    static_data = {}

# Fetch and process Intuition data
print("\n=== Processing Intuition Data (Ethereum Mainnet) ===")
start_time = time.time()
try:
    intuition_transfers = get_intuition_transfers()
    intuition_deposits = aggregate_intuition_deposits(intuition_transfers)
    
    intuition_total_investment = sum(deposit["amount"] for deposit in intuition_deposits)
    
    intuition_data = {
        'total': intuition_total_investment,
        'deposits': intuition_deposits,
        'count': len(intuition_deposits)
    }
    
    print(f"\n✅ Intuition: Found {intuition_data['count']} investors with ${intuition_data['total']:.2f} total investment")
    print(f"   Data collection completed in {time.time() - start_time:.2f} seconds")
    
    # Add to static data
    static_data['intuition'] = intuition_data
    
except Exception as e:
    print(f"\n❌ Error processing Intuition data: {str(e)}")

# Save updated static data
try:
    with open('static_data.json', 'w') as f:
        json.dump(static_data, f, indent=2)
    
    print(f"\n✅ Updated static_data.json with Intuition data")
    print(f"Total sales in static data: {len(static_data)}")
    
    # Print summary
    if 'intuition' in static_data:
        print(f"   - Intuition (Mainnet): {static_data['intuition']['count']} investors, ${static_data['intuition']['total']:.2f}")
        
except Exception as e:
    print(f"\n❌ Error saving static data: {str(e)}")

print("\n🎉 Intuition data collection complete!")