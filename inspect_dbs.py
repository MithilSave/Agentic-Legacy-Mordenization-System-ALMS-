import sqlite3
import os

print("="*60)
print("1. Inspecting audit.db (SQLite)")
print("="*60)
if os.path.exists("audit.db"):
    try:
        conn = sqlite3.connect("audit.db")
        cursor = conn.cursor()
        
        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"Tables found: {[t[0] for t in tables]}")
        
        for table in tables:
            table_name = table[0]
            print(f"\n--- Top 3 rows from table: {table_name} ---")
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 3;")
            rows = cursor.fetchall()
            for row in rows:
                print(row)
        conn.close()
    except Exception as e:
        print(f"Error reading audit.db: {e}")
else:
    print("audit.db not found.")

print("\n" + "="*60)
print("2. Inspecting cache_db (DiskCache)")
print("="*60)
if os.path.exists("cache_db"):
    try:
        import diskcache
        cache = diskcache.Cache("cache_db")
        print(f"Total items in cache: {len(cache)}")
        print("Top 3 keys in cache:")
        for i, key in enumerate(cache):
            if i >= 3:
                break
            print(f"- {key}")
        cache.close()
    except Exception as e:
        print(f"Error reading cache_db: {e}")
else:
    print("cache_db not found.")

print("\n" + "="*60)
print("3. Inspecting chroma_db (Chroma Vector DB)")
print("="*60)
if os.path.exists("chroma_db"):
    try:
        import chromadb
        client = chromadb.PersistentClient(path="chroma_db")
        collections = client.list_collections()
        print(f"Collections found: {[c.name for c in collections]}")
        
        for coll in collections:
            print(f"\n--- Collection: {coll.name} ---")
            count = coll.count()
            print(f"Total documents: {count}")
            if count > 0:
                print("Top 1 document:")
                results = coll.peek(1)
                print(results)
    except Exception as e:
        print(f"Error reading chroma_db: {e}")
else:
    print("chroma_db not found.")
