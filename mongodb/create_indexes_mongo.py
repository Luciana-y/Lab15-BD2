from pymongo import MongoClient, ASCENDING, HASHED, TEXT

MONGO_URI = "mongodb://localhost:28017"
DB_NAME = "news_analysis"
COLLECTION_NAME = "milei_news"


def main():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
    coll = client[DB_NAME][COLLECTION_NAME]

    #indice simple sobre published
    name = coll.create_index([("published", ASCENDING)], name="idx_published")
    print(f"[ok] indice simple: {name}")

    #indice hash sobre news_paper
    name = coll.create_index([("news_paper", HASHED)], name="idx_news_paper_hashed")
    print(f"[ok] indice hash: {name}")

    #indice de texto sobre title + summary
    name = coll.create_index(
        [("title", TEXT), ("summary", TEXT)],
        name="idx_text_title_summary",
        default_language="spanish",
        weights={"title": 3, "summary": 1},
    )
    print(f"[ok] indice de texto: {name}")

    print("\nIndices actuales en la coleccion")
    for idx_name, info in coll.index_information().items():
        print(f"  {idx_name}: {info.get('key')}")

    print("\nIndices creados. Siguiente paso: abrir queries_mongo.ipynb y ejecutarlo.")
    client.close()


if __name__ == "__main__":
    main()
