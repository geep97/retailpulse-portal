import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from supabase import create_client, Client

# Securely load environment vars from your fixed .env
load_dotenv()

app = FastAPI(title="RetailPulse Portal Core Engine", version="1.0.0")

# Setup CORS middleware to allow your frontend connection pooling without blocks
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this to specific domains later for production security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("System error: Supabase configurations missing from environment registry.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.get("/")
async def health_check():
    return {"status": "healthy", "application": "RetailPulse Portal Core Engine"}

@app.get("/api/analytics/baseline-2023")
async def get_2023_baseline_summary():
    """
    Fetches and aggregates the 2023 historical sales dataset 
    from Supabase relational tables to serve active portal dashboard widgets.
    """
    try:
        # Fetch live transactions along with the related store name
        response = supabase.table("transactions").select(
            "store_id, quantity, total_price, payment_method, stores(store_name)"
        ).execute()
        
        records = response.data
        if not records:
            return {"message": "No data found inside active ledger tables", "data": []}
            
        # Compile global high-level summary KPIs
        total_revenue = sum(item["total_price"] for item in records)
        total_items_sold = sum(item["quantity"] for item in records)
        transaction_count = len(records)
        
        # Calculate isolated metrics grouping per store profile
        store_breakdown = {}
        for item in records:
            s_name = item.get("stores", {}).get("store_name", f"Store Reference ID #{item['store_id']}")
            if s_name not in store_breakdown:
                store_breakdown[s_name] = {"revenue_ghs": 0.0, "items_sold": 0, "transaction_count": 0}
            
            store_breakdown[s_name]["revenue_ghs"] += float(item["total_price"])
            store_breakdown[s_name]["items_sold"] += int(item["quantity"])
            store_breakdown[s_name]["transaction_count"] += 1

        # Round values nicely for JSON transfer serialization
        for name in store_breakdown:
            store_breakdown[name]["revenue_ghs"] = round(store_breakdown[name]["revenue_ghs"], 2)

        return {
            "success": True,
            "summary": {
                "total_revenue_ghs": round(total_revenue, 2),
                "total_items_sold": total_items_sold,
                "total_transactions": transaction_count,
                "avg_ticket_value_ghs": round(total_revenue / transaction_count, 2) if transaction_count > 0 else 0
            },
            "stores_performance": store_breakdown
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))