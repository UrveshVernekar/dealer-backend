# import pandas as pd
# import numpy as np
# import io
# import re
# import traceback
# import uuid
# import csv
# from fastapi import FastAPI, File, UploadFile
# import asyncio
# from fastapi import UploadFile
# from io import BytesIO
# import asyncio


# upload_tasks = {}
# po_upload_tasks = {}
# alternative_upload_tasks = {}

# def process_po_upload_task(task_id: str, content: bytes):
#     try:
#         po_upload_tasks[task_id] = {"status": "processing", "progress": 10, "message": "Reading Excel file..."}

#         # READ EXCEL (defensively try 'IND', then first sheet)
#         try:
#             df_raw = pd.read_excel(
#                 io.BytesIO(content),
#                 sheet_name='IND',
#                 header=None
#             )
#         except Exception:
#             try:
#                 df_raw = pd.read_excel(
#                     io.BytesIO(content),
#                     sheet_name=0,
#                     header=None
#                 )
#             except Exception as read_err:
#                 raise Exception(f"Failed to read Excel sheets: {str(read_err)}")

#         po_upload_tasks[task_id] = {"status": "processing", "progress": 20, "message": "Finding header row..."}

#     except Exception as e:
#         traceback.print_exc()
#         po_upload_tasks[task_id] = {
#             "status": "failed",
#             "progress": 0,
#             "message": "Import failed",
#             "error": str(e)
#         }
 
 


# async def upload_data(file: UploadFile = File(...)):
#     target_sheet = "dealer_SKU"
     

#     # 1. Open and read the file locally as binary bytes
#     with open(file, "rb") as f:
#         contents = await file.read()  
    
#     # 2. Wrap the bytes in BytesIO so pandas can read it like a file stream
#     df = pd.read_excel(BytesIO(contents), sheet_name=target_sheet, engine="pyxlsb")
    
#     # Process your dataframe...
#     return {"filename": file.filename, "rows": len(df)}      
        


# if __name__ == "__main__":
    
#     file_path = "/mnt/d/work/ifb/mckinsey/Q1_analysis_v8_simulation_160726_vcheck.xlsb"
        
#     response = asyncio.run(upload_data(file=file_path)) 
#     print(response)


import pandas as pd
import numpy as np
import io
import re
import traceback
import uuid
import csv
from fastapi import FastAPI, File, UploadFile
import asyncio
from io import BytesIO
import gc
import sys
import os

# ... keep your upload tasks variables and process_po_upload_task function ...

async def upload_data(
                    outfile:str,
                    file: UploadFile = File(...), 
                    schemefile: UploadFile = File()
                    ):
    target_sheet1 = "dealer_SKU"
    target_sheet2 = "Vistex_Template_Scheme"
    target_sheet3 = "Target"
    target_sheet4 = "Dealer_product"
     
    # Since 'file' is a proper UploadFile object now, we await its read stream directly
    contents = await file.read() 
    scheme_contents = await schemefile.read() 
    
    # Read using the pyxlsb engine
    df1 = pd.read_excel(
        BytesIO(contents), 
        sheet_name=target_sheet1, 
        engine="pyxlsb",
        header=0,
        skiprows=3
    )
    
    df1.columns = df1.columns.str.strip()
    df1.columns = df1.columns.str.replace(r'\s+', ' ', regex=True).str.strip()
    
    
    target_states = ["tamilnadu", 
                     "tamil nadu", 
                     "kerela", 
                     "kerala", 
                     "westbengal", 
                     "west bengal", 
                     "bihar", 
                     "jharkand",
                     "jharkhand",
                     "odisha",
                     "orissa",
                     "northeast",
                     "north east",
                     "north-east",
                     "chattisgarh",
                     "chhattisgarh",
                     "madhya pradesh",
                     "madhyapradesh",
                     "gujarat",
                     "gujrat",
                     "mumbai",
                     "pune",
                     "vidharbha",
                     "delhi",
                     "rajasthan",
                     "rajastan",
                     "uttar pradesh",
                     "uttarpradesh",
                     "uttarakhand",
                     "uttarkhand",
                     "chandigarh",
                     "punjab",
                     "haryana",
                     "jammu & kashmir",
                     "andhra pradesh",
                     "andhrapradesh",
                     "karnataka",
                     "karnatak",
                     "telengana",
                     "telangana"
                     ]
    df1_filtered = df1[df1["SO_Region"].str.lower().isin(target_states)]
    df1_filtered = df1
    
    df1_filtered.to_excel(outfile, 
                          sheet_name="dealer_SKU",
                          engine="openpyxl",
                          index=False)
    # 'mode="a"' requires the openpyxl engine
    
    df2 = pd.read_excel(
        BytesIO(scheme_contents), 
        sheet_name=target_sheet2, 
        engine="pyxlsb",
        header=0,
        skiprows=3
    )
    
    df2.columns = df2.columns.str.strip()
    df2.columns = df2.columns.str.replace(r'\s+', ' ', regex=True).str.strip()
    
    # target_states = ["tamilnadu", "tamil nadu", "kerela"]
    
    df2_filtered = df2[df2["Branch"].str.lower().isin(target_states)]
    
    # print("Begin print") 
    # print(df2["Branch"].str.lower().head())
    # print("End print")    
    
    with pd.ExcelWriter(outfile, 
                    mode="a", 
                    engine="openpyxl", 
                    if_sheet_exists="replace") as writer:
        df2_filtered.to_excel(writer, sheet_name="new_scheme", index=False)
        
    # df2_filtered.to_excel("output_file_TN.xlsx", sheet_name="new_scheme", index=False)
    
    
    df3 = pd.read_excel(
        BytesIO(scheme_contents), 
        sheet_name=target_sheet3, 
        engine="pyxlsb",
        header=0,
        skiprows=3
    )
    
    df3.columns = df3.columns.str.strip()
    df3.columns = df3.columns.str.replace(r'\s+', ' ', regex=True).str.strip()
    # Create a list of target values
    # target_states = ["tamilnadu", "tamil nadu", "kerela"]

    # Filter using .isin()
    df3_filtered = df3[df3["State"].str.lower().isin(target_states)]
    
    with pd.ExcelWriter(outfile, 
                    mode="a", 
                    engine="openpyxl", 
                    if_sheet_exists="replace") as writer:
        df3_filtered.to_excel(writer, sheet_name="Target_Compilation", index=False)
       

    columns = ['New Sold to Party',
                'Sum of Sum of Tie up schemes', 
                'Sum of Sum of Cash Discount', 
                'Sum of Sum of FOI',
                'Sum of Updated_IQ (AC adj.)'
            ]
    # 2. Start with an empty Python list instead of an empty DataFrame
    output_rows = []

 
    print(f"Length of df1 before filter : {len(df1_filtered)}")
    # target_dealers = ['patra electronics', 'patraelectronics']
    
    # df1_filtered = df1_filtered[df1_filtered["New Sold to Party"] == 1003661]
    # df2_filtered = df2_filtered[df2_filtered["Dealer Name"].str.lower().isin(target_dealers)]
    
    
    print(f"Length of df1 after filter : {len(df1_filtered)}")
    print(f"Length of df2 : {len(df2_filtered)}")
    print("\n\n")
        
    merged_df = pd.merge(
        df1_filtered, 
        df2_filtered, 
        left_on=["New Sold to Party", "Material Code"], 
        right_on=["Sold to party code", "Material_id"],  # Fixed the period to a comma here
        how="inner",
        suffixes=(' (Actuals)', ' (Scheme)')
        )
    
    
    print("\n".join(merged_df.columns))
    
    
    # 1. Calculate and store your new columns in a dictionary
    new_cols = {}
    new_cols[''] = ""
    new_cols["IQ_DP"] = (merged_df['DP']/1.18) * merged_df['Sum of Updated_IQ (AC adj.)']
    new_cols["On-invoice discount IQ_DP"] = new_cols['IQ_DP'] * merged_df['On-invoice discount %']
    merged_df['Sell Through %'].fillna(0)
    new_cols["Sell Through IQ_DP"] = new_cols['IQ_DP'] * merged_df['Sell Through %']
    merged_df['Sell Out %'].fillna(0)
    new_cols["Sell Out IQ_DP"] = new_cols['IQ_DP'] * merged_df['Sell Out %']
    merged_df['Cash Discount %'].fillna(0)
    new_cols["CD IQ_DP"] = (new_cols["IQ_DP"] - new_cols["On-invoice discount IQ_DP"]) * merged_df['Cash Discount %']
    new_cols["Old_discount"] = merged_df["Sum of Sum of Total Discount"]
    new_cols["QTRLY On Vol Tie-up discount"] = new_cols["IQ_DP"] * merged_df["QTRLY On Vol Tie-up %"]
    new_cols["QTRLY On Overall Val Tie-up discount"] = new_cols["IQ_DP"] * merged_df["QTRLY On Overall Val Tie-up %"]
    # 1. Create a list of the columns you want to add up
    columns_to_sum = [
        new_cols["On-invoice discount IQ_DP"],
        new_cols["CD IQ_DP"],
        new_cols["Sell Through IQ_DP"],
        new_cols["Sell Out IQ_DP"],
        new_cols["QTRLY On Vol Tie-up discount"],
        new_cols["QTRLY On Overall Val Tie-up discount"]
    ]

    # 2. Sum them across rows (axis=1), which automatically ignores empty cells
    new_cols["New_discount"] = pd.concat(columns_to_sum, axis=1).sum(axis=1)
    
    
    # 1. Calculate the single grand total numbers
    total_old = new_cols["Old_discount"].sum()
    total_new = new_cols["New_discount"].sum()
    grand_delta = total_old - total_new

    # 2. Build your small, isolated summary block
    summary_data = {
        "Metric": ["Grand Total"],
        "Old_discount": [total_old],
        "New_discount": [total_new],
        "Delta": [grand_delta]
    }
    df_summary = pd.DataFrame(summary_data)
    
    # new_cols["New_discount"] = new_cols["On-invoice discount IQ_DP"] + new_cols["CD IQ_DP"] + new_cols["Sell Through IQ_DP"] + new_cols["Sell Out IQ_DP"]
    # 2. Concat all the new columns to merged_df in one single operation
    merged_df = pd.concat([merged_df, pd.DataFrame(new_cols, index=merged_df.index)], axis=1)
    
    
    # 1. Store the exact list of columns you intend to export
    columns_to_export = [
        'New Sold to Party',
        'Dealer Name',
        'Product Mapping',
        'Material Code',
        'Material Description',
        'Sum of Sum of Tie up schemes', 
        'Sum of Sum of Cash Discount', 
        'Sum of Sum of FOI',
        'Sum of Updated_IQ (AC adj.)',
        '',
        'MRP',
        'DP',
        'IQ_DP',
        'Current scheme',
        '',
        'On-invoice discount %',
        'On-invoice discount IQ_DP',
        'Cash Discount %',
        'CD IQ_DP',
        'Sell Through %',
        'Sell Through IQ_DP',
        'Sell Out %',
        'Sell Out IQ_DP',
        'MTHLY On Vol Tie-up %',
        'QTRLY On Vol Tie-up %',
        'Old_discount',
        'New_discount'
    ]
    
    with pd.ExcelWriter(outfile, 
                    mode="w",              
                    engine="openpyxl") as writer:
        
        # Write the main table using the subset list
        merged_df[columns_to_export].to_excel(writer, sheet_name="Outcome", index=False)
        
        # Calculate exactly where the main table ends
        start_row_for_totals = len(merged_df) + 2
    
        # FIX: Find the column index relative to what was ACTUALLY written to Excel
        # Since "Old_discount" is the first metric column in df_summary, align to that
        start_col_for_totals = columns_to_export.index("Old_discount")
        
        # Write the summary block right below the data
        df_summary.to_excel(
            writer, 
            sheet_name="Outcome", 
            startrow=start_row_for_totals, 
            startcol=start_col_for_totals, 
            index=False
        )
    
    
    del df1  # Delete dataframe reference
    del df2  # Delete dataframe reference
    del df3  # Delete dataframe reference
    # del df4  # Delete dataframe reference
    
    gc.collect()      


if __name__ == "__main__":
    
    if len(sys.argv) < 4:
        print("Usage: python <program> <actuals file.xlsb>  <scheme.xlsb> <output.xlsx> ")
        sys.exit(1)

    file_path = sys.argv[1] #"/mnt/d/work/ifb/mckinsey/Actuals_vs_scheme_analysis.xlsb"
    scheme_file_path = sys.argv[2] # "/mnt/d/work/ifb/mckinsey/data/Revised/Kerala.xlsb"

    outfile_name = sys.argv[3]

    
    # 1. Read the local file as binary bytes
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    
    
    base_file_name = os.path.basename(file_path)
       
    # 2. Correctly wrap those bytes in an UploadFile object 
    # so 'await file.read()' works exactly like it does in a live API
    mock_upload_file = UploadFile(
        file=BytesIO(file_bytes),
        filename= base_file_name
    )
    
    # 1. Read the local file as binary bytes
    with open(scheme_file_path, "rb") as f:
        scheme_file_bytes = f.read()
    
    
    base_scheme_file_name = os.path.basename(scheme_file_path) 
       
    # 2. Correctly wrap those bytes in an UploadFile object 
    # so 'await file.read()' works exactly like it does in a live API
    mock_scheme_upload_file = UploadFile(
        file=BytesIO(scheme_file_bytes),
        filename=base_scheme_file_name
    )
    
    
        
    # 3. Pass the mock object into your async function
    response = asyncio.run(upload_data(
                                    outfile=outfile_name,
                                    file=mock_upload_file,
                                    schemefile=mock_scheme_upload_file
                                )) 
    print(response)