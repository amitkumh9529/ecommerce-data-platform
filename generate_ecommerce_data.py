import os
import random
from datetime import datetime, timedelta
from io import StringIO

import psycopg2
from faker import Faker
from dotenv import load_dotenv



# ---------------------------
# Configuration
# ---------------------------
SEED = 42
BATCH_SIZE = 10_000

CUSTOMERS = 50_000
PRODUCTS = 10_000
ORDERS = 150_000
ORDER_ITEMS = 250_000
PAYMENTS = 100_000
EVENTS = 500_000

fake = Faker()
Faker.seed(SEED)
random.seed(SEED)


load_dotenv()  # Load environment variables from .env file
DB_URL = os.getenv("SUPABASE_DB_URL")
if not DB_URL:
    raise RuntimeError(
        "Set SUPABASE_DB_URL to your Supabase PostgreSQL connection string."
    )

# Realistic value sets
CATEGORIES = [
    "Electronics", "Fashion", "Home & Kitchen", "Beauty", "Sports",
    "Books", "Grocery", "Toys", "Automotive", "Accessories"
]
BRANDS = [
    "Samsung", "Apple", "Sony", "Nike", "Adidas", "LG", "Dell",
    "Lenovo", "Philips", "Puma", "Levi's", "HP", "Bose", "Canon"
]
ORDER_STATUSES = ["completed", "pending", "cancelled", "shipped", "returned"]
PAYMENT_METHODS = ["credit_card", "debit_card", "upi", "paypal", "net_banking", None]
PAYMENT_STATUSES = ["paid", "failed", "pending", "refunded"]
EVENT_TYPES = ["view", "add_to_cart", "remove_from_cart", "purchase", "wishlist", "search"]
DEVICES = ["mobile", "desktop", "tablet", None]
BROWSERS = ["Chrome", "Safari", "Edge", "Firefox", "Opera", None]
CURRENCIES = ["USD", "INR", "EUR", "GBP"]
START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2026, 9, 30)


def rand_dt(start=START_DATE, end=END_DATE):
    seconds = int((end - start).total_seconds())
    return start + timedelta(seconds=random.randint(0, seconds))


def messy_email(i: int):
    """~6% null/invalid/duplicate-ish email values."""
    if random.random() < 0.02:
        return None
    email = fake.email().lower()
    r = random.random()
    if r < 0.015:
        return email.replace("@", "")            # invalid
    if r < 0.03:
        return f" {email} "                      # whitespace
    if r < 0.045 and i > 1:
        return f"customer{random.randint(1, max(1, i - 1))}@example.com"  # duplicate
    if r < 0.06:
        return email.upper()                     # casing issue
    return email


def messy_phone():
    if random.random() < 0.03:
        return None
    digits = fake.msisdn()[-10:]
    style = random.random()
    if style < 0.25:
        return digits
    if style < 0.5:
        return f"+91 {digits[:5]} {digits[5:]}"
    if style < 0.75:
        return f"+91-{digits[:5]}-{digits[5:]}"
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"


def copy_rows(cur, table, columns, rows):
    """Fast bulk load using PostgreSQL COPY FROM STDIN."""
    buf = StringIO()
    for row in rows:
        values = []
        for value in row:
            if value is None:
                values.append("\\N")
            elif isinstance(value, datetime):
                values.append(value.isoformat(sep=" "))
            else:
                text = str(value)
                text = text.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n")
                values.append(text)
        buf.write("\t".join(values) + "\n")
    buf.seek(0)
    cur.copy_from(buf, table, columns=columns, null="\\N")


def generate_customers(cur):
    print(f"Generating {CUSTOMERS:,} customers...")
    rows = []
    for i in range(1, CUSTOMERS + 1):
        rows.append((
            i,
            fake.first_name(),
            fake.last_name(),
            messy_email(i),
            messy_phone(),
            fake.city() if random.random() > 0.03 else None,
            fake.state() if random.random() > 0.03 else None,
            random.choice(["India", "United States", "United Kingdom", "Germany", "Singapore"]),
            rand_dt(START_DATE, datetime(2026, 6, 30)),
            rand_dt(START_DATE, END_DATE),
        ))
        if len(rows) >= BATCH_SIZE:
            copy_rows(cur, "customers", (
                "customer_id", "first_name", "last_name", "email", "phone",
                "city", "state", "country", "signup_date", "created_at"
            ), rows)
            rows.clear()
    if rows:
        copy_rows(cur, "customers", (
            "customer_id", "first_name", "last_name", "email", "phone",
            "city", "state", "country", "signup_date", "created_at"
        ), rows)


def generate_products(cur):
    print(f"Generating {PRODUCTS:,} products...")
    rows = []
    for i in range(1, PRODUCTS + 1):
        name = fake.catch_phrase()
        category = random.choice(CATEGORIES)
        if random.random() < 0.03:
            category = None
        brand = random.choice(BRANDS)
        if random.random() < 0.025:
            brand = f" {brand.lower()} "
        price = round(random.uniform(2, 5000), 2)
        r = random.random()
        if r < 0.005:
            price = -abs(price)  # bad value
        elif r < 0.01:
            price = 0           # bad value
        stock = random.randint(0, 1000)
        if random.random() < 0.02:
            stock = -random.randint(1, 20)
        rows.append((i, name, category, brand, price, stock, rand_dt()))
        if len(rows) >= BATCH_SIZE:
            copy_rows(cur, "products", (
                "product_id", "product_name", "category", "brand", "price", "stock_quantity", "created_at"
            ), rows)
            rows.clear()
    if rows:
        copy_rows(cur, "products", (
            "product_id", "product_name", "category", "brand", "price", "stock_quantity", "created_at"
        ), rows)


def generate_orders(cur):
    print(f"Generating {ORDERS:,} orders...")
    rows = []
    order_customer = {}
    for i in range(1, ORDERS + 1):
        valid_customer = random.random() >= 0.01
        customer_id = random.randint(1, CUSTOMERS) if valid_customer else CUSTOMERS + random.randint(1, 5000)
        order_customer[i] = customer_id
        status = random.choices(ORDER_STATUSES, weights=[55, 12, 10, 18, 5])[0]
        amount = round(random.uniform(5, 5000), 2)
        if random.random() < 0.01:
            amount *= random.choice([-1, 0])
        currency = random.choice(CURRENCIES)
        if random.random() < 0.03:
            currency = None
        rows.append((
            i,
            customer_id,
            rand_dt(),
            status,
            amount,
            currency,
            fake.city() if random.random() > 0.03 else None,
            random.choice(["India", "United States", "United Kingdom", "Germany", "Singapore"]),
        ))
        if len(rows) >= BATCH_SIZE:
            copy_rows(cur, "orders", (
                "order_id", "customer_id", "order_date", "status", "total_amount",
                "currency", "shipping_city", "shipping_country"
            ), rows)
            rows.clear()
    if rows:
        copy_rows(cur, "orders", (
            "order_id", "customer_id", "order_date", "status", "total_amount",
            "currency", "shipping_city", "shipping_country"
        ), rows)
    return order_customer


def generate_order_items(cur):
    print(f"Generating {ORDER_ITEMS:,} order items...")
    rows = []
    for i in range(1, ORDER_ITEMS + 1):
        order_id = random.randint(1, ORDERS)
        product_id = random.randint(1, PRODUCTS)
        quantity = random.randint(1, 5)
        if random.random() < 0.015:
            quantity = random.choice([0, -1, -2])
        unit_price = round(random.uniform(2, 5000), 2)
        discount = round(random.uniform(0, min(500, unit_price)), 2)
        if random.random() < 0.02:
            discount = None
        rows.append((i, order_id, product_id, quantity, unit_price, discount))
        if len(rows) >= BATCH_SIZE:
            copy_rows(cur, "order_items", (
                "order_item_id", "order_id", "product_id", "quantity", "unit_price", "discount"
            ), rows)
            rows.clear()
    if rows:
        copy_rows(cur, "order_items", (
            "order_item_id", "order_id", "product_id", "quantity", "unit_price", "discount"
        ), rows)


def generate_payments(cur):
    print(f"Generating {PAYMENTS:,} payments...")
    rows = []
    for i in range(1, PAYMENTS + 1):
        order_id = random.randint(1, ORDERS)
        status = random.choices(PAYMENT_STATUSES, weights=[75, 10, 10, 5])[0]
        amount = round(random.uniform(5, 5000), 2)
        if random.random() < 0.01:
            amount = -abs(amount)
        rows.append((
            i,
            order_id,
            random.choice(PAYMENT_METHODS),
            status,
            amount,
            random.choice(CURRENCIES),
            rand_dt(),
        ))
        if len(rows) >= BATCH_SIZE:
            copy_rows(cur, "payments", (
                "payment_id", "order_id", "payment_method", "payment_status",
                "amount", "currency", "payment_date"
            ), rows)
            rows.clear()
    if rows:
        copy_rows(cur, "payments", (
            "payment_id", "order_id", "payment_method", "payment_status",
            "amount", "currency", "payment_date"
        ), rows)


def generate_events(cur):
    print(f"Generating {EVENTS:,} events...")
    rows = []
    for i in range(1, EVENTS + 1):
        customer_id = random.randint(1, CUSTOMERS) if random.random() > 0.015 else CUSTOMERS + random.randint(1, 5000)
        product_id = random.randint(1, PRODUCTS) if random.random() > 0.015 else PRODUCTS + random.randint(1, 5000)
        event_time = rand_dt()
        # 1% timestamps deliberately pushed into the future
        if random.random() < 0.01:
            event_time += timedelta(days=random.randint(1, 30))
        rows.append((
            i,
            customer_id,
            product_id,
            f"sess_{random.randint(1, 120_000):06d}",
            random.choice(EVENT_TYPES),
            event_time,
            random.choice(DEVICES),
            random.choice(BROWSERS),
            fake.ipv4() if random.random() > 0.02 else None,
        ))
        if len(rows) >= BATCH_SIZE:
            copy_rows(cur, "events", (
                "event_id", "customer_id", "product_id", "session_id", "event_type",
                "event_timestamp", "device_type", "browser", "ip_address"
            ), rows)
            rows.clear()
    if rows:
        copy_rows(cur, "events", (
            "event_id", "customer_id", "product_id", "session_id", "event_type",
            "event_timestamp", "device_type", "browser", "ip_address"
        ), rows)


def main():
    print("Connecting to Supabase PostgreSQL...")
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Helpful for rerunning the generator safely.
        # Primary keys make accidental duplicate inserts fail, so clear first.
        print("Clearing existing generated data...")
        cur.execute("TRUNCATE TABLE order_items, payments, events, orders, products, customers RESTART IDENTITY;")

        generate_customers(cur)
        conn.commit()

        generate_products(cur)
        conn.commit()

        generate_orders(cur)
        conn.commit()

        generate_order_items(cur)
        conn.commit()

        generate_payments(cur)
        conn.commit()

        generate_events(cur)
        conn.commit()

        print("\nDone: ~1.06M rows generated.")
        print("Run these checks in Supabase SQL Editor:")
        print("  SELECT 'customers' table_name, COUNT(*) FROM customers;")
        print("  SELECT 'products', COUNT(*) FROM products;")
        print("  SELECT 'orders', COUNT(*) FROM orders;")
        print("  SELECT 'order_items', COUNT(*) FROM order_items;")
        print("  SELECT 'payments', COUNT(*) FROM payments;")
        print("  SELECT 'events', COUNT(*) FROM events;")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
