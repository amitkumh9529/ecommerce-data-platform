import os
import io
import boto3
import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Supabase PostgreSQL
conn = psycopg2.connect(
    host=os.getenv("SUPABASE_DB_HOST"),
    port=os.getenv("SUPABASE_DB_PORT"),
    database=os.getenv("SUPABASE_DB_NAME"),
    user=os.getenv("SUPABASE_DB_USER"),
    password=os.getenv("SUPABASE_DB_PASSWORD")
)

# AWS S3
s3 = boto3.client(
    "s3",
    region_name=os.getenv("AWS_REGION"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

bucket = os.getenv("S3_BUCKET")

tables = [
    "customers",
    "products",
    "orders",
    "order_items"
]

for table in tables:

    print(f"Extracting {table}...")

    query = f"SELECT * FROM {table}"

    df = pd.read_sql(query, conn)

    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False)
    buffer.seek(0)

    key = f"raw/{table}/{table}.parquet"

    s3.upload_fileobj(
        buffer,
        bucket,
        key
    )

    print(f"Uploaded: s3://{bucket}/{key}")
    print(f"Rows: {len(df)}")

conn.close()

print("Ingestion completed.")