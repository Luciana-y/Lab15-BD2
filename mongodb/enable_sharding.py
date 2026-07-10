from pymongo import MongoClient
from pymongo.errors import OperationFailure

MONGO_URI = "mongodb://localhost:28017"
DB_NAME = "news_analysis"
COLLECTION_NAME = "milei_news"
NS = f"{DB_NAME}.{COLLECTION_NAME}"

STRATEGY = "hashed"


def main():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
    admin = client.admin
    coll = client[DB_NAME][COLLECTION_NAME]

    #sharding a nivel de base de datos
    try:
        admin.command("enableSharding", DB_NAME)
        print(f"[ok] sharding habilitado en la base '{DB_NAME}'")
    except OperationFailure as e:
        if "already enabled" in str(e).lower():
            print(f"[=] sharding ya estaba habilitado en '{DB_NAME}'")
        else:
            raise

    #indice sobre la shard key
    if STRATEGY == "hashed":
        key = {"section": "hashed"}
        coll.create_index([("section", "hashed")])
    else:  # ranged
        key = {"section": 1}
        coll.create_index([("section", 1)])
    print(f"[ok] indice de shard key creado: {key}")

    #shardear la coleccion
    try:
        admin.command("shardCollection", NS, key=key)
        print(f"[ok] coleccion shardeada: {NS} con clave {key} ({STRATEGY})")
    except OperationFailure as e:
        if "already sharded" in str(e).lower():
            print(f"[=] la coleccion {NS} ya estaba shardeada")
        else:
            raise

    print("\n Distribucion de chunks por shard (config.chunks)")
    coll_meta = client.config.collections.find_one({"_id": NS})
    uuid = coll_meta.get("uuid") if coll_meta else None
    pipeline = [
        {"$match": {"uuid": uuid}},
        {"$group": {"_id": "$shard", "chunks": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    rows = list(client.config.chunks.aggregate(pipeline))
    if rows:
        for r in rows:
            print(f"  {r['_id']:16s} -> {r['chunks']} chunks")
    else:
        print("  (aun no hay chunks; apareceran al cargar datos)")
        
    print("\nSiguiente paso: python load_mongo_recursive.py")
    client.close()


if __name__ == "__main__":
    main()
