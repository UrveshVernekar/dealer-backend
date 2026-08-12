from typing import Optional
import io
import re
import pandas as pd
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db, engine
from datetime import datetime, timezone
from app.models.user import User
from app.models.sales_data import SalesData
from app.models.target_data import TargetData
from app.models.import_mapping import ImportTableMapping
from app.routers.auth import get_admin_user, get_current_user
from fastapi.responses import StreamingResponse

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
    "invoiced_quantity": "inv_qty_bu",
    "invoiced_qty": "inv_qty_bu",
    
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


def normalize_sheet_name(sheet_name: str) -> str:
    normalized = re.sub(r'[^a-z0-9]+', '_', str(sheet_name).strip().lower()).strip('_')
    if not normalized:
        return "sheet"
    if "sales" in normalized and "data" in normalized:
        return "sales_data"
    if "target" in normalized and "data" in normalized:
        return "target_data"
    return normalized


def persist_import_mapping(db: Session, sheet_name: str, table_name: str):
    mapping = db.query(ImportTableMapping).filter(
        ImportTableMapping.original_sheet_name == sheet_name
    ).first()
    if mapping is None:
        mapping = ImportTableMapping(
            original_sheet_name=sheet_name,
            normalized_table_name=table_name,
        )
        db.add(mapping)
    else:
        mapping.normalized_table_name = table_name
        mapping.imported_at = datetime.now(timezone.utc)
    db.commit()


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
            db_table_name = normalize_sheet_name(sheet)
            
            if db_table_name == "sale_report" and year is not None:
                df_data["selected_year"] = year
                if quarter is not None:
                    df_data["selected_quarter"] = quarter
                if month is not None:
                    df_data["selected_month"] = month
            
            print(db_table_name)
            persist_import_mapping(db, sheet, db_table_name)
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




def get_user_tables(db: Session):
    result = db.execute(text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
          AND table_name NOT LIKE 'pg_%'
          AND table_name NOT LIKE 'sql_%'
        ORDER BY table_name
    """))
    return [row[0] for row in result.fetchall()]


@router.get("/tables")
def get_imported_tables(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    return {"tables": sorted(get_user_tables(db))}

@router.get("/tables/{table_name}")
def get_table_data(
    table_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    available_tables = set(get_user_tables(db))
    if table_name not in available_tables:
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
    available_tables = set(get_user_tables(db))
    if table_name not in available_tables:
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


def resolve_required_table(db: Session, required_name: str):
    available_tables = set(get_user_tables(db))
    if required_name in available_tables:
        return required_name

    expected_name = normalize_sheet_name(required_name)
    mapping_rows = db.query(ImportTableMapping).all()
    for row in mapping_rows:
        if normalize_sheet_name(row.original_sheet_name) == expected_name and row.normalized_table_name in available_tables:
            return row.normalized_table_name

    return None


def run_outcome_calculation(db: Session):
    available_tables = set(get_user_tables(db))
    required_tables = ["new_scheme", "dealer_sku"]
    resolved_tables = {}
    missing_tables = []

    print("Available tables:", available_tables)
    for table_name in required_tables:
        resolved_name = resolve_required_table(db, table_name)
        if resolved_name:
            resolved_tables[table_name] = resolved_name
        else:
            missing_tables.append(table_name)

    if missing_tables:
        available_list = ", ".join(sorted(available_tables)) if available_tables else "none"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Required table(s) {', '.join(missing_tables)} do not exist yet. "
                f"Available user tables: {available_list}"
            )
        )
            
    df1 = pd.read_sql_query(f"SELECT * FROM {resolved_tables['dealer_sku']}", con=engine)
    df2 = pd.read_sql_query(f"SELECT * FROM {resolved_tables['new_scheme']}", con=engine)
    
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


def run_sales_outcome_calculation(db: Session, year: Optional[int] = None):
    available_tables = set(get_user_tables(db))
    required_tables = ["sales_data", "target_data"]
    missing_tables = [table for table in required_tables if table not in available_tables]

    if missing_tables:
        available_list = ", ".join(sorted(available_tables)) if available_tables else "none"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Required table(s) {', '.join(missing_tables)} do not exist yet. "
                f"Available user tables: {available_list}"
            )
        )

    if year is None:
        max_year = db.execute(text("SELECT MAX(year) FROM public.sales_data")).scalar()
        year = int(max_year) if max_year is not None else datetime.now().year

    sql = """
    WITH raw_sales AS (
        SELECT
            sd.year,
            sd.month,
            sd.product_category,
            sd.sold_to_pt,
            sd.sold_party_name,
            COALESCE(SUM(sd.inv_qty_bu::numeric), 0) AS month_sales,

            CASE
                WHEN sd.month IN ('April','May','June') THEN 'Q1'
                WHEN sd.month IN ('July','August','September') THEN 'Q2'
                WHEN sd.month IN ('October','November','December') THEN 'Q3'
                WHEN sd.month IN ('January','February','March') THEN 'Q4'
            END AS quarter,

            CASE
                WHEN sd.month IN ('April','May','June') THEN td.q1
                WHEN sd.month IN ('July','August','September') THEN td.q2
                WHEN sd.month IN ('October','November','December') THEN td.q3
                WHEN sd.month IN ('January','February','March') THEN td.q4
            END AS quarter_target

        FROM public.sales_data sd
        LEFT JOIN public.target_data td
        ON sd.sold_to_pt = td.sold_to_code
        AND sd.product_category = td.product

        -- Fetch both current year and last year
        WHERE sd.year IN (:year, :year - 1)

        GROUP BY
            sd.year,
            sd.month,
            sd.product_category,
            sd.sold_to_pt,
            sd.sold_party_name,
            td.q1, td.q2, td.q3, td.q4
    ),

    sales_with_fractions AS (
        SELECT
            year,
            month,
            product_category,
            sold_to_pt,
            sold_party_name,
            quarter,
            month_sales,
            quarter_target,

            -- Calculate each month's fraction of its quarterly sales for that specific year
            COALESCE(
                month_sales / NULLIF(
                    SUM(month_sales) OVER (
                        PARTITION BY sold_to_pt, product_category, year, quarter
                    ), 0
                ),
                0
            ) AS yearly_month_fraction

        FROM raw_sales
    )

    SELECT
        curr.sold_to_pt,
        curr.sold_party_name,
        curr.year,
        curr.month,
        curr.product_category,
        curr.month_sales,
        curr.quarter_target,

        -- Fraction from the exact same month & quarter in (year - 1)
        COALESCE(prev.yearly_month_fraction, 0) AS last_year_fraction_of_quarter,

        -- Current quarter target multiplied by last year's monthly weight
        
        COALESCE(curr.quarter_target, 0) * COALESCE(prev.yearly_month_fraction, 0)
        AS monthly_target

    FROM sales_with_fractions curr

    -- Left join to pair current year records with last year's corresponding month
    LEFT JOIN sales_with_fractions prev
    ON curr.sold_to_pt = prev.sold_to_pt
    AND curr.product_category = prev.product_category
    AND curr.month = prev.month
    AND prev.year = curr.year - 1

    WHERE curr.year = :year
    ORDER BY curr.year, curr.quarter, curr.month;
    """

    export_df = pd.read_sql_query(text(sql), con=engine)
    if export_df.empty:
        export_df = pd.DataFrame(columns=[
            "sold_to_pt",
            "year",
            "month",
            "product_category",
            "month_sales",
            "quarter_target",
            "fraction_of_quarter",
            "monthly_target",
        ])
        return export_df, 0.0, 0.0, 0.0

    # Calculate month numbers and period keys
    export_df["month_num"] = export_df["month"].str.strip().str.lower().map(MONTH_NAME_TO_NUM).fillna(1).astype(int)
    export_df["period_key"] = export_df["year"] * 12 + export_df["month_num"]

    # 1. Determine unique periods from calculated outcomes to establish boundaries
    periods_list = export_df[["year", "month_num"]].drop_duplicates().values.tolist()
    if periods_list:
        periods_list.sort(key=lambda x: x[0] * 12 + x[1])
        min_db_period = periods_list[0][0] * 12 + periods_list[0][1]
        max_db_period = periods_list[-1][0] * 12 + periods_list[-1][1]
    else:
        min_db_period = 2025 * 12 + 1
        max_db_period = 2025 * 12 + 12

    # Handle legacy year parameter
    if year is not None and duration == "all" and not start_period and not end_period:
        duration = "custom"
        start_period = f"{year}-01"
        end_period = f"{year}-12"

    # Calculate active range boundaries
    if duration == "all":
        min_period_key = min_db_period
        max_period_key = max_db_period
    elif duration == "custom":
        min_period_key = min_db_period
        max_period_key = max_db_period
        if start_period:
            try:
                sy, sm = map(int, start_period.split("-"))
                min_period_key = sy * 12 + sm
            except ValueError:
                pass
        if end_period:
            try:
                ey, em = map(int, end_period.split("-"))
                max_period_key = ey * 12 + em
            except ValueError:
                pass
    else:
        months_back = 3
        if duration == "1m":
            months_back = 1
        elif duration == "6m":
            months_back = 6
        elif duration == "12m":
            months_back = 12
        max_period_key = max_db_period
        min_period_key = max_period_key - months_back + 1

    # Filter in Python
    filtered_df = export_df[
        (export_df["period_key"] >= min_period_key) &
        (export_df["period_key"] <= max_period_key)
    ].copy()

    # Drop intermediate filtering columns
    filtered_df.drop(columns=["month_num", "period_key"], inplace=True, errors="ignore")

    total_old = float(filtered_df["month_sales"].sum()) if "month_sales" in filtered_df.columns else 0.0
    total_new = float(filtered_df["monthly_target"].sum()) if "monthly_target" in filtered_df.columns else 0.0
    delta = total_old - total_new
    return filtered_df, total_old, total_new, delta


@router.get("/outcome")
def get_scheme_outcome(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    current_user: User = Depends(get_current_user)
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


@router.get("/sales-outcome")
def get_sales_outcome(
    year: Optional[int] = Query(None, description="Year for sales outcome calculation. Defaults to latest available year if omitted."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    print(f"Inside the function get_sales_outcome with duration {duration}........")
    try:
        export_df, total_old, total_new, delta = run_sales_outcome_calculation(
            db, year=year, duration=duration, start_period=start_period, end_period=end_period
        )
        columns = list(export_df.columns)
        rows = export_df.to_dict(orient="records")
        
        # Format nan values to None/null for JSON standard compliance
        for row in rows:
            for k, v in row.items():
                if isinstance(v, float) and np.isnan(v):
                    row[k] = None
                    
        # Fetch distinct periods in database to return to UI
        res = db.execute(text("SELECT DISTINCT year, month FROM sales_data WHERE year IS NOT NULL AND month IS NOT NULL")).fetchall()
        periods_list = []
        for r in res:
            m_lower = r[1].strip().lower() if r[1] else ""
            m_num = MONTH_NAME_TO_NUM.get(m_lower, 1)
            periods_list.append((int(r[0]), m_num))
            
        distinct_periods_list = []
        months_abbr = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        for yr, m_num in sorted(periods_list, key=lambda x: x[0]*12 + x[1], reverse=True):
            m_label = months_abbr[m_num - 1]
            distinct_periods_list.append({
                "year": yr,
                "month": m_num,
                "label": f"{m_label} {yr}",
                "value": f"{yr}-{m_num:02d}"
            })
                    
        return {
            "columns": columns,
            "rows": rows,
            "summary": {
                "total_old": total_old,
                "total_new": total_new,
                "delta": delta
            },
            "periods": distinct_periods_list
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


@router.get("/sales-outcome/download")
def download_sales_outcome(
    year: Optional[int] = Query(None, description="Year for sales outcome calculation. Defaults to latest available year if omitted."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    print(f"Inside the function download_sales_outcome with duration {duration}........")
    try:
        export_df, total_old, total_new, delta = run_sales_outcome_calculation(
            db, year=year, duration=duration, start_period=start_period, end_period=end_period
        )
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            export_df.to_excel(writer, sheet_name="Sales_Outcome", index=False)
            
            start_row = len(export_df) + 2
            try:
                start_col = list(export_df.columns).index("month_sales")
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
                sheet_name="Sales_Outcome",
                startrow=start_row,
                startcol=start_col,
                index=False
            )
            
        buffer.seek(0)
        
        headers = {
            'Content-Disposition': 'attachment; filename="sales-outcome.xlsx"'
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

