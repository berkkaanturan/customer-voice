import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db import get_supabase_client

def clean_database():
    client = get_supabase_client()
    print("Fetching all reviews from database...")
    
    page = 0
    limit = 1000
    all_rows = []
    
    while True:
        res = client.table("reviews").select("id, text_hash, platform_name").range(page*limit, (page+1)*limit - 1).execute()
        data = res.data or []
        all_rows.extend(data)
        print(f"Page {page+1} fetched {len(data)} rows.")
        if len(data) < limit:
            break
        page += 1
        
    print(f"Total reviews in DB: {len(all_rows)}")
    
    # Identify duplicates
    hashes = {}
    dups_ids = []
    
    for r in all_rows:
        h = r["text_hash"]
        if h in hashes:
            dups_ids.append(r["id"])
        else:
            hashes[h] = r["id"]
            
    print(f"Duplicate reviews found: {len(dups_ids)}")
    
    if dups_ids:
        print("Deleting duplicates...")
        # Delete in chunks of 100
        chunk_size = 100
        deleted_count = 0
        for i in range(0, len(dups_ids), chunk_size):
            chunk = dups_ids[i : i + chunk_size]
            try:
                client.table("reviews").delete().in_("id", chunk).execute()
                deleted_count += len(chunk)
                print(f"Deleted chunk {i+1}–{i+len(chunk)}")
            except Exception as e:
                print(f"Failed to delete chunk: {e}")
        print(f"Successfully deleted {deleted_count} duplicate reviews.")
    else:
        print("No duplicates to delete.")

if __name__ == "__main__":
    clean_database()
