import io
import re
import pandas as pd
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db, engine
from app.models.user import User
from app.models.sales_data import SalesData
from app.models.target_data import TargetData
from app.routers.auth import get_admin_user

router = APIRouter(prefix="/import", tags=["Data Import"])

# Heuristic list of key terms to identify the header row
HEADER_INDICATORS = [
    "sold to", "sold-to", "dealer name", "material code", "material_id", 
    "billing type", "billing date", "sales org", "distribution channel", 
    "region", "state", "quantity", "basic rate", "net value", 
    "product mapping", "updated_channel", "material description"
]

SALES_COLUMN_MAPPINGS = {
    "billing_date": "bill_date",
    "bill_date": "bill_date",
    "billing_document_date": "bill_date",
    "invoice_date": "bill_date",
    
    "plant": "plnt",
    "plnt": "plnt",
    
    "branch": "branch",
    "region": "branch",
    
    "item": "item",
    "itm": "item",
    "billing_item": "item",
    
    "sold_to_party": "sold_to_pt",
    "sold_to_pt": "sold_to_pt",
    "sold_to": "sold_to_pt",
    
    "ship_to_party_name": "ship_to_party_name",
    "ship_to_name": "ship_to_party_name",
    "ship_party_name": "ship_to_party_name",
    
    "ship_to": "ship_to",
    "ship_to_party": "ship_to",
    "ship_to_pt": "ship_to",
    
    "sold_to_party_name": "sold_party_name",
    "sold_party_name": "sold_party_name",
    "sold_name": "sold_party_name",
    "dealer_name": "sold_party_name",
    
    "material_group": "mat_group",
    "mat_group": "mat_group",
    "mat_grp": "mat_group",
    "matl_group": "mat_group",
    "matl_grp": "mat_group",
    
    "material": "material",
    "material_code": "material",
    "material_id": "material",
    "mat_code": "material",
    
    "material_description": "material_description",
    "material_desc": "material_description",
    "mat_description": "material_description",
    
    "billed_quantity": "inv_qty_bu",
    "inv_qty_bu": "inv_qty_bu",
    "quantity": "inv_qty_bu",
    "qty": "inv_qty_bu",
    "invoice_qty": "inv_qty_bu",
    "inv_qty": "inv_qty_bu",
    
    "dealer_price": "dealer_pri",
    "dealer_pri": "dealer_pri",
    "dealer_rate": "dealer_pri",
    
    "sale_price": "sale_price",
    "selling_price": "sale_price",
    "sales_price": "sale_price",
    
    "basic_rate": "basic_rate",
    "basic_value": "basic_rate",
    "basic_amount": "basic_rate",
    
    "discount_p": "discount_p",
    "discount_percentage": "discount_p",
    
    "discount_w": "discount_w",
    "discount_value": "discount_w",
    
    "dealer_commission": "dealer_com",
    "dealer_com": "dealer_com",
    "commission": "dealer_com",
    
    "free_goods": "free_goods",
    "free_qty": "free_goods",
    "free_items": "free_goods",
    
    "cash_discount_percent": "cash_disco",
    "cash_disco_percent": "cash_disco",
    "cash_discount_p": "cash_disco",
    "cash_disco": "cash_disco",
    
    "total_scheme_discount": "tot_sch",
    "tot_sch": "tot_sch",
    "scheme_discount": "tot_sch",
    "total_scheme": "tot_sch",
    
    "combo_offer": "combo_offe",
    "combo_offe": "combo_offe",
    "combo": "combo_offe",
    
    "special_discount": "special",
    "special": "special",
    "special_off": "special",
    
    "adjusted_dealer_price": "adjusted_d",
    "adjusted_d": "adjusted_d",
    "adjusted_dealer": "adjusted_d",
    "adj_dealer_price": "adjusted_d",
    
    "cash_discount": "cash_disc",
    "cash_disc": "cash_disc",
    "cash_discount_amount": "cash_disc",
    
    "net_value": "netvalue",
    "netvalue": "netvalue",
    "net_amount": "netvalue",
    
    "tax_amount": "tax_amount",
    "tax_value": "tax_amount",
    "tax": "tax_amount",
    
    "gross_value": "gross_val",
    "gross_val": "gross_val",
    "gross_amount": "gross_val",
    
    "cgst_rate": "cgst_rate",
    "cgst_percentage": "cgst_rate",
    
    "cgst_amount": "central_gs",
    "central_gs": "central_gs",
    "central_gst": "central_gs",
    "cgst": "central_gs",
    
    "sgst_rate": "sgst_rate",
    "sgst_percentage": "sgst_rate",
    
    "sgst_amount": "state_gst",
    "state_gst": "state_gst",
    "state_gst_amount": "state_gst",
    "sgst": "state_gst",
    
    "igst_amount": "integrated",
    "integrated_gst": "integrated",
    "integrated": "integrated",
    "igst": "integrated",
    
    "igst_rate": "igst_rate",
    "igst_percentage": "igst_rate",
    
    "ugst_amount": "union_ter",
    "union_territory_gst": "union_ter",
    "union_ter": "union_ter",
    "ugst": "union_ter",
    
    "ugst_rate": "ugst_rate",
    "ugst_percentage": "ugst_rate"
}

TARGET_COLUMN_MAPPINGS = {
    "region": "region",
    "state": "state",
    
    "channel_code": "channel_code",
    "new_channel": "new_channel",
    
    "sold_to_code": "sold_to_code",
    "sold_to_pt": "sold_to_code",
    "sold_to": "sold_to_code",
    
    "new_sold_to_party": "new_sold_to_party",
    "new_sold_to_pt": "new_sold_to_party",
    "new_sold_to": "new_sold_to_party",
    
    "dealer_name": "dealer_name",
    "dealer": "dealer_name",
    
    "product": "product",
    "product_raw": "product_raw",
    
    "q1": "q1",
    "q2": "q2",
    "q3": "q3",
    "q4": "q4",
    "total": "total",
    "remarks": "remarks"
}

def find_header_row_index(df_raw):
    best_row_idx = 0
    best_score = 0
    
    # Scan the first 15 rows
    scan_limit = min(15, len(df_raw))
    for idx in range(scan_limit):
        row_values = df_raw.iloc[idx].fillna("").astype(str).str.strip().str.lower().tolist()
        
        score = 0
        for val in row_values:
            if not val:
                continue
            # Check if any indicator keyword is part of the cell value
            for indicator in HEADER_INDICATORS:
                if indicator in val:
                    score += 1
                    break
        
        # If the row has more keyword matches, update the best candidate
        if score > best_score:
            best_score = score
            best_row_idx = idx
            
    return best_row_idx if best_score >= 2 else 0

def sanitize_column_names(columns):
    clean_cols = []
    for col in columns:
        # Convert to string, lowercase
        c = str(col).strip().lower()
        # Replace non-alphanumeric character sequences with a single underscore
        c = re.sub(r'[^a-z0-9]+', '_', c)
        # Strip leading/trailing underscores
        c = c.strip('_')
        if not c or c == "unnamed":
            c = "unnamed_col"
        elif c[0].isdigit():
            c = "col_" + c
        clean_cols.append(c)
        
    # Ensure all column names are unique
    seen = {}
    final_cols = []
    for col in clean_cols:
        if col in seen:
            seen[col] += 1
            final_cols.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 0
            final_cols.append(col)
            
    return final_cols

@router.post("/upload")
async def upload_excel_data(
    file: UploadFile = File(...),
    year: int = Form(None),
    quarter: str = Form(None),
    month: str = Form(None),
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):

    print("Inside the function upload ........")    
    filename = file.filename.lower()
    
    if not filename.endswith(('.xlsx', '.xls', '.xlsb')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Excel (.xlsx, .xls, .xlsb) files are allowed."
        )
        
    try:
        
        # 1. Determine the correct engine dynamically
        reader_engine = None
        if filename.endswith(".xlsb"):
            reader_engine = "pyxlsb"
        elif filename.endswith(".xlsx"):
            reader_engine = "openpyxl"
        elif filename.endswith(".xls"):
            reader_engine = "xlrd"
        # Read the file content
        content = await file.read()
        
        file_stream = io.BytesIO(content)
        file_stream.seek(0)
        
        # 2. Pass the engine to ExcelFile so it knows how to parse sheet names
        excel_file = pd.ExcelFile(file_stream, engine=reader_engine)
        sheet_names = excel_file.sheet_names
        
        results = {}
        
        for sheet in sheet_names:
            # Re-seek or pass the BytesIO object directly with the engine
            file_stream.seek(0)
            df_raw = pd.read_excel(
                file_stream, 
                sheet_name=sheet,
                engine=reader_engine, 
                header=None
            )
            
            if df_raw.empty:
                continue
                            
            # Find the header row index
            header_idx = find_header_row_index(df_raw)
            
            # Extract headers and clean them
            headers = df_raw.iloc[header_idx].fillna("").astype(str).str.strip().tolist()
            # Clean and ensure unique headers
            cleaned_headers = []
            for i, h in enumerate(headers):
                if not h:
                    cleaned_headers.append(f"Unnamed_{i}")
                else:
                    cleaned_headers.append(h)
                    
            # Slice the data below the header
            df_data = df_raw.iloc[header_idx + 1:].copy()
            df_data.columns = cleaned_headers
            df_data.reset_index(drop=True, inplace=True)
            
            # Drop rows that are completely empty
            df_data.dropna(how="all", inplace=True)
            
            # Sanitize column names
            df_data.columns = sanitize_column_names(df_data.columns)
            
            # If the sheet is sale-report, append selected year and quarter/month
            # We map the sheet name to a valid database table name
            db_table_name = sheet.lower().replace("-", "_").replace(" ", "_")
            if "sales" in db_table_name and "data" in db_table_name:
                db_table_name = "sales_data"
            elif "target" in db_table_name and "data" in db_table_name:
                db_table_name = "target_data"
            
            if db_table_name == "sale_report" and year is not None:
                df_data["selected_year"] = year
                if quarter is not None:
                    df_data["selected_quarter"] = quarter
                if month is not None:
                    df_data["selected_month"] = month
            
            print(db_table_name)
            # Save the dataframe to the database using SQLAlchemy connection
            if db_table_name == "sales_data":
                # Rename columns using SALES_COLUMN_MAPPINGS to align alternative column names
                df_data = df_data.rename(columns=SALES_COLUMN_MAPPINGS)
                # Keep only the first occurrence of each column name (avoids duplicates from mapping)
                df_data = df_data.loc[:, ~df_data.columns.duplicated()]
                
                # Ensure bill_date is parsed as datetime to extract month/year
                if "bill_date" in df_data.columns:
                    df_data["bill_date"] = pd.to_datetime(df_data["bill_date"], dayfirst=True, errors="coerce")
                    # Extract year and month (full month name)
                    df_data["year"] = df_data["bill_date"].dt.year
                    df_data["month"] = df_data["bill_date"].dt.strftime("%B")
                
                # Derive product_category from mat_group
                if "mat_group" in df_data.columns:
                    def map_mat_group(val):
                        if pd.isna(val):
                            return None
                        val_str = str(val).strip()
                        val_upper = val_str.upper()
                        if val_upper in ["FLT", "FLU", "WD"]:
                            return "FL"
                        elif val_upper in ["AC", "ACMIU", "ACMOU"]:
                            return "AC"
                        elif val_upper in ["MW"]:
                            return "MWO"
                        elif val_upper in ["REFDC", "REFFF"]:
                            return "REF"
                        elif val_upper in ["TL", "TLM"]:
                            return "TL"
                        return val_str
                    df_data["product_category"] = df_data["mat_group"].apply(map_mat_group)
                
                # Fetch only valid columns from model schema
                allowed_cols = [c.name for c in SalesData.__table__.columns if c.name != "id"]
                # Keep only columns that exist in the database table schema
                df_data = df_data[[col for col in df_data.columns if col in allowed_cols]]
                
                # Delete existing rows matching the uploaded billing dates to simulate replacement
                if "bill_date" in df_data.columns:
                    unique_dates = df_data["bill_date"].dropna().unique()
                    date_list = [pd.to_datetime(d).date() for d in unique_dates]
                    if date_list:
                        db.execute(
                            text("DELETE FROM sales_data WHERE bill_date = ANY(CAST(:dates AS date[]))"),
                            {"dates": date_list}
                        )
                        db.commit()
                
                # Save to database using append to retain predefined table structure
                df_data.to_sql(
                    name=db_table_name,
                    con=engine,
                    if_exists="append",
                    index=False
                )
            elif db_table_name == "target_data":
                # Rename columns using TARGET_COLUMN_MAPPINGS to align alternative column names
                df_data = df_data.rename(columns=TARGET_COLUMN_MAPPINGS)
                # Keep only the first occurrence of each column name (avoids duplicates from mapping)
                df_data = df_data.loc[:, ~df_data.columns.duplicated()]
                
                # Fetch only valid columns from model schema
                allowed_cols = [c.name for c in TargetData.__table__.columns if c.name != "id"]
                # Keep only columns that exist in the database table schema
                df_data = df_data[[col for col in df_data.columns if col in allowed_cols]]
                
                # Delete existing target data to simulate "replace"
                db.execute(text("DELETE FROM target_data"))
                db.commit()
                
                # Save to database using append to retain predefined table structure
                df_data.to_sql(
                    name=db_table_name,
                    con=engine,
                    if_exists="append",
                    index=False
                )
            else:
                # We replace the table dynamically
                df_data.to_sql(
                    name=db_table_name,
                    con=engine,
                    if_exists="replace",
                    index=False
                )
            
            results[sheet] = {
                "table_name": db_table_name,
                "rows_inserted": len(df_data),
                "columns": list(df_data.columns)
            }
            
        return {
            "status": "success",
            "message": "Excel data imported successfully.",
            "details": results
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during import: {str(e)}"
        )


from fastapi.responses import StreamingResponse

ALLOWED_TABLES = {"new_scheme", "dealer_sku", "target_compilation", "dealer_product", "sale_report", "sales_data", "target_data"}

@router.get("/tables")
def get_imported_tables(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    existing_tables = []
    for table in ALLOWED_TABLES:
        result = db.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :t)"
        ), {"t": table}).scalar()
        if result:
            existing_tables.append(table)
    return {"tables": sorted(existing_tables)}

@router.get("/tables/{table_name}")
def get_table_data(
    table_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    if table_name not in ALLOWED_TABLES:
        raise HTTPException(status_code=400, detail="Invalid table name")
        
    table_exists = db.execute(text(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :t)"
    ), {"t": table_name}).scalar()
    if not table_exists:
        raise HTTPException(status_code=404, detail=f"Table {table_name} does not exist yet. Please upload data first.")
        
    result = db.execute(text(f"SELECT * FROM {table_name}"))
    columns = list(result.keys())
    rows = [dict(row._mapping) for row in result.fetchall()]
    
    return {
        "table_name": table_name,
        "columns": columns,
        "rows": rows
    }

@router.get("/tables/{table_name}/download")
def download_table(
    table_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    if table_name not in ALLOWED_TABLES:
        raise HTTPException(status_code=400, detail="Invalid table name")
        
    table_exists = db.execute(text(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :t)"
    ), {"t": table_name}).scalar()
    if not table_exists:
        raise HTTPException(status_code=404, detail=f"Table {table_name} does not exist yet. Please upload data first.")
        
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", con=engine)
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=table_name, index=False)
    buffer.seek(0)
    
    headers = {
        'Content-Disposition': f'attachment; filename="{table_name}.xlsx"'
    }
    return StreamingResponse(
        buffer,
        headers=headers,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def get_column(df, candidates, default=0):
    for c in candidates:
        if c in df.columns:
            return pd.to_numeric(df[c], errors='coerce').fillna(default)
    return pd.Series(default, index=df.index)


def run_outcome_calculation(db: Session):
    for t in ["new_scheme", "dealer_sku"]:
        exists = db.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :t)"
        ), {"t": t}).scalar()
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Required table '{t}' does not exist yet. Please upload dealer data Excel sheets first."
            )
            
    df1 = pd.read_sql_query("SELECT * FROM dealer_sku", con=engine)
    df2 = pd.read_sql_query("SELECT * FROM new_scheme", con=engine)
    
    target_states = [
        "tamilnadu", "tamil nadu", "kerela", "kerala", "westbengal", "west bengal", 
        "bihar", "jharkand", "jharkhand", "odisha", "orissa", "northeast", "north east", 
        "north-east", "chattisgarh", "chhattisgarh", "madhya pradesh", "madhyapradesh", 
        "gujarat", "gujrat", "mumbai", "pune", "vidharbha", "delhi", "rajasthan", 
        "rajastan", "uttar pradesh", "uttarpradesh", "uttarakhand", "uttarkhand"
    ]
    
    if "so_region" in df1.columns:
        df1 = df1[df1["so_region"].str.lower().isin(target_states)].copy()
    if "branch" in df2.columns:
        df2 = df2[df2["branch"].str.lower().isin(target_states)].copy()
        
    if len(df1) > 0 and len(df2) > 0:
        df1["new_sold_to_party"] = df1["new_sold_to_party"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
        df1["material_code"] = df1["material_code"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
        df2["sold_to_party_code"] = df2["sold_to_party_code"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
        df2["material_id"] = df2["material_id"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
        
        merged_df = pd.merge(
            df1,
            df2,
            left_on=["new_sold_to_party", "material_code"],
            right_on=["sold_to_party_code", "material_id"],
            how="inner"
        )
    else:
        merged_df = pd.DataFrame()
        
    export_cols = [
        'new_sold_to_party', 'dealer_name', 'product_mapping', 'material_code',
        'material_description', 'sum_of_sum_of_tie_up_schemes', 'sum_of_sum_of_cash_discount',
        'sum_of_sum_of_foi', 'sum_of_updated_iq_ac_adj_', 'mrp', 'dp', 'iq_dp',
        'current_scheme', 'on_invoice_discount', 'on_invoice_discount_iq_dp',
        'cash_discount', 'cd_iq_dp', 'sell_through', 'sell_through_iq_dp',
        'sell_out', 'sell_out_iq_dp', 'mthly_on_vol_tie_up', 'qtrly_on_vol_tie_up',
        'old_discount', 'new_discount'
    ]
    
    export_df = pd.DataFrame(columns=export_cols)
    
    if len(merged_df) > 0:
        iq_dp = (get_column(merged_df, ['dp']) / 1.18) * get_column(merged_df, ['sum_of_updated_iq_ac_adj_'])
        on_invoice_discount_iq_dp = iq_dp * get_column(merged_df, ['on_invoice_discount'])
        sell_through_iq_dp = iq_dp * get_column(merged_df, ['sell', 'sell_through'])
        sell_out_iq_dp = iq_dp * get_column(merged_df, ['sell_3', 'sellout_support_'])
        cd_iq_dp = (iq_dp - on_invoice_discount_iq_dp) * get_column(merged_df, ['cash_discount', 'cd_'])
        old_discount = get_column(merged_df, ['sum_of_sum_of_total_discount'])
        new_discount = on_invoice_discount_iq_dp + cd_iq_dp + sell_through_iq_dp + sell_out_iq_dp
        
        export_df['new_sold_to_party'] = get_column(merged_df, ['new_sold_to_party'])
        export_df['dealer_name'] = get_column(merged_df, ['dealer_name'])
        export_df['product_mapping'] = get_column(merged_df, ['product_mapping'])
        export_df['material_code'] = get_column(merged_df, ['material_code'])
        export_df['material_description'] = get_column(merged_df, ['material_description'])
        export_df['sum_of_sum_of_tie_up_schemes'] = get_column(merged_df, ['sum_of_sum_of_tie_up_schemes'])
        export_df['sum_of_sum_of_cash_discount'] = get_column(merged_df, ['sum_of_sum_of_cash_discount'])
        export_df['sum_of_sum_of_foi'] = get_column(merged_df, ['sum_of_sum_of_foi'])
        export_df['sum_of_updated_iq_ac_adj_'] = get_column(merged_df, ['sum_of_updated_iq_ac_adj_'])
        export_df['mrp'] = get_column(merged_df, ['mrp'])
        export_df['dp'] = get_column(merged_df, ['dp'])
        export_df['iq_dp'] = iq_dp
        export_df['current_scheme'] = get_column(merged_df, ['current_scheme'])
        export_df['on_invoice_discount'] = get_column(merged_df, ['on_invoice_discount'])
        export_df['on_invoice_discount_iq_dp'] = on_invoice_discount_iq_dp
        export_df['cash_discount'] = get_column(merged_df, ['cash_discount', 'cd_'])
        export_df['cd_iq_dp'] = cd_iq_dp
        export_df['sell_through'] = get_column(merged_df, ['sell', 'sell_through'])
        export_df['sell_through_iq_dp'] = sell_through_iq_dp
        export_df['sell_out'] = get_column(merged_df, ['sell_3', 'sellout_support_'])
        export_df['sell_out_iq_dp'] = sell_out_iq_dp
        export_df['mthly_on_vol_tie_up'] = get_column(merged_df, ['mthly', 'mthly_1'])
        export_df['qtrly_on_vol_tie_up'] = get_column(merged_df, ['qtrly', 'qtrly_1'])
        export_df['old_discount'] = old_discount
        export_df['new_discount'] = new_discount
        
        total_old = float(old_discount.sum())
        total_new = float(new_discount.sum())
    else:
        total_old = 0.0
        total_new = 0.0
        
    delta = total_old - total_new
    return export_df, total_old, total_new, delta


@router.get("/outcome")
def get_scheme_outcome(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    try:
        export_df, total_old, total_new, delta = run_outcome_calculation(db)
        columns = list(export_df.columns)
        rows = export_df.to_dict(orient="records")
        
        # Format nan values to None/null for JSON standard compliance
        for row in rows:
            for k, v in row.items():
                if isinstance(v, float) and np.isnan(v):
                    row[k] = None
                    
        return {
            "columns": columns,
            "rows": rows,
            "summary": {
                "total_old": total_old,
                "total_new": total_new,
                "delta": delta
            }
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during outcome generation: {str(e)}"
        )


@router.get("/outcome/download")
def download_scheme_outcome(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    try:
        export_df, total_old, total_new, delta = run_outcome_calculation(db)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            export_df.to_excel(writer, sheet_name="Outcome", index=False)
            
            # Aligned Grand Total Block at the bottom of sheet
            start_row = len(export_df) + 2
            try:
                start_col = list(export_df.columns).index("old_discount")
            except ValueError:
                start_col = max(0, len(export_df.columns) - 4)
                
            summary_df = pd.DataFrame({
                "Metric": ["Grand Total"],
                "Old_discount": [total_old],
                "New_discount": [total_new],
                "Delta": [delta]
            })
            
            summary_df.to_excel(
                writer,
                sheet_name="Outcome",
                startrow=start_row,
                startcol=start_col,
                index=False
            )
            
        buffer.seek(0)
        
        headers = {
            'Content-Disposition': 'attachment; filename="outcome.xlsx"'
        }
        return StreamingResponse(
            buffer,
            headers=headers,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate spreadsheet download: {str(e)}"
        )


