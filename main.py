import os
import io
import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

app = FastAPI(title="RetailPulse Portal Core Engine")

# CORS and Supabase setup remain as per your existing configuration
supabase: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

@app.post("/api/upload", tags=["Data Ingestion Pipeline"])
async def upload_weekly_ledger(
    store_id: int = Form(..., description="Store identification key"), 
    file: UploadFile = File(...)
):
    """
    Ingests weekly ledger via an atomic database procedure to ensure 
    relational integrity and permanent audit logging.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid format.")
    
    try:
        # 1. Local Processing
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
        
        # 2. Catalog Mapping
        products = supabase.table("product").select("product_id, product_name").execute()
        product_map = {p["product_name"]: p["product_id"] for p in products.data}
        
        # 3. Transform to transaction objects
        transactions = []
        for _, row in df.iterrows():
            if row["product_name"] in product_map:
                transactions.append({
                    "product_id": product_map[row["product_name"]],
                    "quantity": int(row["quantity"]),
                    "unit_price": round(float(row["total_ghs"]) / int(row["quantity"]), 2),
                    "total_price": float(row["total_ghs"]),
                    "payment_method": str(row["payment_method"]),
                    "transaction_date": str(row["transaction_date"])
                })

        # 4. Atomic Execution via RPC
        # This replaces the multi-step manual insertion logic
        response = supabase.rpc("proc_submit_weekly_data", {
            "p_store_id": store_id,
            "p_week_label": file.filename,
            "p_transactions": transactions
        }).execute()

        if not response.data.get("success"):
            raise Exception(response.data.get("error"))

        return {
            "success": True, 
            "submission_id": response.data.get("submission_id"),
            "message": "Pipeline executed. Records securely locked into permanent audit trail."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")