import io
import json
import zipfile
from pathlib import Path

import pandas as pd
from pymongo import MongoClient

REPO_ROOT = Path(__file__).resolve().parent.parent
ZIP_PATH = REPO_ROOT / "data" / "Argentina.zip"
DIR_PATH = REPO_ROOT / "data" / "Argentina"

MONGO_URI = "mongodb://localhost:28017"
DB_NAME = "news_analysis"
COLLECTION_NAME = "milei_news"

EXPECTED_COLUMNS = [
    "news_paper",
    "section",
    "title",
    "summary",
    "published",
    "link",
    "tags",
]


def decode_bytes(raw: bytes) -> str:
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def parse_concatenated_json(text: str) -> list:
    decoder = json.JSONDecoder()
    idx = 0
    n = len(text)
    objects = []
    while idx < n:
        while idx < n and text[idx] in " \r\n\t":
            idx += 1
        if idx >= n:
            break
        obj, end = decoder.raw_decode(text, idx)
        if isinstance(obj, list):
            objects.extend(obj)
        else:
            objects.append(obj)
        idx = end
    return objects


def iter_json_sources():
    if ZIP_PATH.exists():
        with zipfile.ZipFile(ZIP_PATH) as zf:
            for name in zf.namelist():
                if name.endswith(".json"):
                    yield name, zf.read(name)
    elif DIR_PATH.exists():
        for path in DIR_PATH.rglob("*.json"):
            yield str(path.relative_to(DIR_PATH)), path.read_bytes()
    else:
        raise FileNotFoundError(
            f"No se encontro ni {ZIP_PATH} ni {DIR_PATH}. "
            "Coloca el dataset en data/ antes de ejecutar."
        )


def read_all_records() -> pd.DataFrame:
    rows = []
    files_ok = files_err = 0

    for name, raw in iter_json_sources():
        try:
            text = decode_bytes(raw)
            objects = parse_concatenated_json(text)
        except Exception as e:
            files_err += 1
            continue

        parts = Path(name).parts
        path_paper = parts[0] if len(parts) >= 1 else None
        path_section = parts[1] if len(parts) >= 2 else None

        for obj in objects:
            if not isinstance(obj, dict):
                continue
            rows.append({
                "news_paper": obj.get("news_paper") or path_paper,
                "section": obj.get("section") or path_section,
                "title": obj.get("title"),
                "summary": obj.get("summary"),
                "published": obj.get("published"),
                "link": obj.get("link"),
                "tags": obj.get("tags"),
            })
        files_ok += 1

    print(f"Archivos leidos: {files_ok} (con error: {files_err})")
    print(f"Registros crudos (antes de limpiar): {len(rows)}")
    return pd.DataFrame(rows, columns=EXPECTED_COLUMNS)


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    #normalizacion de texto
    df["news_paper"] = df["news_paper"].fillna("unknown").astype(str).str.strip().str.lower()
    #section: el campo clave del sharding, quitar espacios y pasar a minuscula
    df["section"] = df["section"].fillna("unknown").astype(str).str.strip().str.lower()
    df.loc[df["section"] == "", "section"] = "unknown"

    df["title"] = df["title"].fillna("").astype(str).str.strip()
    df["summary"] = df["summary"].fillna("").astype(str).str.strip()
    df["link"] = df["link"].fillna("").astype(str).str.strip()
    df["tags"] = df["tags"].fillna("").astype(str).str.strip()

    df["published"] = pd.to_datetime(df["published"], errors="coerce",
                                     utc=True, format="mixed")

    before = len(df)
    df = df[~((df["title"] == "") & (df["summary"] == ""))]
    print(f"Filas sin title ni summary eliminadas: {before - len(df)}")

    before = len(df)
    df = df.drop_duplicates(subset=["news_paper", "section", "title", "published", "link"])
    print(f"Duplicados eliminados: {before - len(df)}")

    return df[EXPECTED_COLUMNS].reset_index(drop=True)


def print_stats(df: pd.DataFrame):
    print("\n Estadisticas del dataset limpio")
    print(f"Registros finales : {len(df)}")
    print(f"Periodicos        : {df['news_paper'].nunique()}")
    print(f"Secciones         : {df['section'].nunique()}")
    print("\nNulos por columna:")
    print(df.isnull().sum().to_string())
    print("\nFechas invalidas (published NaT):", int(df["published"].isna().sum()))
    print("\nDistribucion por section (top 15):")
    print(df["section"].value_counts().head(15).to_string())
    print("\nDistribucion por news_paper:")
    print(df["news_paper"].value_counts().to_string())


def upload_to_mongo(df: pd.DataFrame):
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
    collection = client[DB_NAME][COLLECTION_NAME]

    collection.delete_many({})

    df = df.astype(object).where(pd.notnull(df), None)
    records = df.to_dict("records")

    BATCH = 5000
    inserted = 0
    for i in range(0, len(records), BATCH):
        chunk = records[i:i + BATCH]
        collection.insert_many(chunk, ordered=False)
        inserted += len(chunk)
        print(f"  insertados {inserted}/{len(records)}")

    print(f"\nDocumentos en la coleccion: {collection.count_documents({})}")
    client.close()


if __name__ == "__main__":
    df_raw = read_all_records()
    df = clean_dataframe(df_raw)
    print_stats(df)
    upload_to_mongo(df)
    print("\nCarga finalizada. Siguiente paso: python create_indexes_mongo.py")
