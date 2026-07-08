from pathlib import Path
import pandas as pd
from pymongo import MongoClient

# Ruta base donde está la carpeta Argentina
BASE_DIR = Path("data/Argentina")

# Conexión al router mongos
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "news_analysis"
COLLECTION_NAME = "milei_news"


def normalize_column_name(col: str) -> str:
    """
    Normaliza nombres de columnas por si vienen con mayúsculas,
    espacios o formatos diferentes.
    """
    return (
        col.strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
    )


def clean_dataframe(df: pd.DataFrame, news_paper: str, section: str) -> pd.DataFrame:
    """
    Limpia y estandariza el DataFrame para que todos los CSV
    tengan el mismo formato antes de insertarse en MongoDB.
    """

    # Normalizar nombres de columnas
    df.columns = [normalize_column_name(c) for c in df.columns]

    # Agregar periódico y sección desde la ruta de carpetas
    df["news_paper"] = news_paper
    df["section"] = section

    # Crear columnas esperadas si no existen
    expected_columns = [
        "news_paper",
        "section",
        "title",
        "summary",
        "published",
        "link",
        "tags"
    ]

    for col in expected_columns:
        if col not in df.columns:
            df[col] = None

    # Limpieza básica
    df["news_paper"] = df["news_paper"].fillna("unknown").astype(str).str.strip()
    df["section"] = df["section"].fillna("unknown").astype(str).str.lower().str.strip()

    df["title"] = df["title"].fillna("").astype(str).str.strip()
    df["summary"] = df["summary"].fillna("").astype(str).str.strip()
    df["link"] = df["link"].fillna("").astype(str).str.strip()

    # tags puede venir como texto, lista serializada o vacío
    df["tags"] = df["tags"].fillna("").astype(str).str.strip()

    # Convertir fecha
    df["published"] = pd.to_datetime(df["published"], errors="coerce")

    # Eliminar filas sin título y sin resumen
    df = df[~((df["title"] == "") & (df["summary"] == ""))]

    # Quedarse solo con columnas necesarias
    df = df[expected_columns]

    return df


def read_all_csv_files() -> pd.DataFrame:
    """
    Recorre Argentina/periódico/sección/*.csv y une todo
    en un solo DataFrame.
    """

    all_dataframes = []

    csv_files = list(BASE_DIR.rglob("*.csv"))

    print(f"CSV encontrados: {len(csv_files)}")

    for csv_path in csv_files:
        try:
            relative_path = csv_path.relative_to(BASE_DIR)
            parts = relative_path.parts

            # Esperado:
            # parts[0] = periódico
            # parts[1] = sección
            if len(parts) < 3:
                print(f"Saltando archivo con estructura inesperada: {csv_path}")
                continue

            news_paper = parts[0]
            section = parts[1]

            print(f"Leyendo: {csv_path}")
            print(f"  Periódico: {news_paper}")
            print(f"  Sección: {section}")

            # Intenta leer con UTF-8
            try:
                df = pd.read_csv(csv_path)
            except UnicodeDecodeError:
                df = pd.read_csv(csv_path, encoding="latin1")

            df = clean_dataframe(df, news_paper, section)
            all_dataframes.append(df)

        except Exception as e:
            print(f"Error leyendo {csv_path}: {e}")

    if not all_dataframes:
        raise ValueError("No se pudo leer ningún CSV.")

    final_df = pd.concat(all_dataframes, ignore_index=True)

    return final_df


def upload_to_mongo(df: pd.DataFrame):
    """
    Inserta el DataFrame limpio en MongoDB.
    """

    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    # Limpia colección anterior para evitar duplicados
    collection.delete_many({})

    # Convertir fechas NaT a None para MongoDB
    df = df.where(pd.notnull(df), None)

    records = df.to_dict("records")

    if records:
        collection.insert_many(records)

    print(f"Registros insertados en MongoDB: {collection.count_documents({})}")

    print("\nDistribución por section:")
    for row in collection.aggregate([
        {"$group": {"_id": "$section", "cantidad": {"$sum": 1}}},
        {"$sort": {"cantidad": -1}}
    ]):
        print(row)

    print("\nDistribución por news_paper:")
    for row in collection.aggregate([
        {"$group": {"_id": "$news_paper", "cantidad": {"$sum": 1}}},
        {"$sort": {"cantidad": -1}}
    ]):
        print(row)


if __name__ == "__main__":
    df = read_all_csv_files()

    print("\nDataset final:")
    print(df.head())

    print("\nDimensiones:")
    print(df.shape)

    print("\nNulos por columna:")
    print(df.isnull().sum())

    print("\nDistribución de section:")
    print(df["section"].value_counts())

    upload_to_mongo(df)