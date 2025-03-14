import json
import sys
import time

# Import functions from your main app
from app import (
    get_giza_usdc_deposits, aggregate_giza_deposits,
    get_electron_usdc_deposits, aggregate_electron_deposits,
    get_almanak_usdc_deposits, aggregate_almanak_deposits,
    get_pulse_usdc_deposits, aggregate_pulse_deposits,
    get_fuel_usdc_deposits, aggregate_fuel_deposits,
    get_nil_usdc_deposits, aggregate_nil_deposits,
    get_corn_usdc_deposits, aggregate_corn_deposits,
    get_enclave_usdc_deposits, aggregate_enclave_deposits
)

# Dictionary to store all static data
static_data = {}

def fetch_sale_data(name, get_deposits_func, aggregate_func):
    """Fetch and process data for a specific sale"""
    print(f"Fetching {name} data...")
    start_time = time.time()
    
    try:
        transfers = get_deposits_func()
        deposits = aggregate_func(transfers)
        
        sale_data = {
            'total': sum(deposit["amount"] for deposit in deposits),
            'deposits': deposits,
            'count': len(deposits)
        }
        
        print(f"✅ {name}: Found {sale_data['count']} investors with ${sale_data['total']:.2f} total investment")
        print(f"   Completed in {time.time() - start_time:.2f} seconds")
        return sale_data
    except Exception as e:
        print(f"❌ Error fetching {name} data: {str(e)}")
        return None

# Process each sale one by one
sales_to_process = [
    ('giza', get_giza_usdc_deposits, aggregate_giza_deposits),
    ('electron', get_electron_usdc_deposits, aggregate_electron_deposits),
    ('almanak', get_almanak_usdc_deposits, aggregate_almanak_deposits),
    ('pulse', get_pulse_usdc_deposits, aggregate_pulse_deposits),
    ('fuel', get_fuel_usdc_deposits, aggregate_fuel_deposits),
    ('nil', get_nil_usdc_deposits, aggregate_nil_deposits),
    ('corn', get_corn_usdc_deposits, aggregate_corn_deposits),
    ('enclave', get_enclave_usdc_deposits, aggregate_enclave_deposits)
]

# Process all sales
for name, get_func, agg_func in sales_to_process:
    result = fetch_sale_data(name, get_func, agg_func)
    if result:
        static_data[name] = result
    
    # Wait a bit between requests to avoid rate limiting
    time.sleep(2)

# Save to a JSON file
with open('static_data.json', 'w') as f:
    json.dump(static_data, f, indent=2)

print("\n✅ Static data saved to static_data.json")
print(f"Total sales processed: {len(static_data)}/{len(sales_to_process)}")