import io
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db, engine
from app.models.user import User
from app.routers.auth import get_admin_user

router = APIRouter(prefix="/import", tags=["Data Import"])

# Heuristic list of key terms to identify the header row
HEADER_INDICATORS = [
    "sold to", "sold-to", "dealer name", "material code", "material_id", 
    "billing type", "billing date", "sales org", "distribution channel", 
    "region", "state", "quantity", "basic rate", "net value", 
    "product mapping", "updated_channel", "material description"
]

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
        # Convert to string, lowercase, replace spaces/dashes with underscores
        c = str(col).strip().lower()
        c = c.replace(" ", "_").replace("-", "_").replace(".", "_").replace("/", "_").replace("=", "").replace("*", "")
        # Remove extra special characters
        c = "".join([char for char in c if char.isalnum() or char == "_"])
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
    year: int = Form(...),
    quarter: str = Form(...),
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Excel (.xlsx, .xls) files are allowed."
        )
        
    try:
        # Read the file content
        content = await file.read()
        excel_file = pd.ExcelFile(io.BytesIO(content))
        sheet_names = excel_file.sheet_names
        
        results = {}
        
        for sheet in sheet_names:
            # Read sheet without headers to inspect raw rows
            df_raw = pd.read_excel(io.BytesIO(content), sheet_name=sheet, header=None)
            
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
            
            # If the sheet is sale-report, append selected year and quarter
            # We map the sheet name to a valid database table name
            db_table_name = sheet.lower().replace("-", "_").replace(" ", "_")
            
            if db_table_name == "sale_report":
                df_data["selected_year"] = year
                df_data["selected_quarter"] = quarter
                
            # Save the dataframe to the database using SQLAlchemy connection
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

ALLOWED_TABLES = {"new_scheme", "dealer_sku", "target_compilation", "dealer_product", "sale_report"}

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

