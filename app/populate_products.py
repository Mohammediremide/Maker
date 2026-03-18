import sqlite3
import os
import json
import re
from datetime import datetime, timezone
from urllib.parse import quote
from urllib.request import Request, urlopen

DB_PATH = "app.db"
ENV_PATH = ".env"

CATEGORIES = {
    "Supermarket": [
        "Golden Morn 500g", "Milo Tin 400g", "Peak Milk Pack", "Dano Milk Powder", 
        "Poundo Yam 1kg", "Sunlight Detergent", "Mama Gold Rice", "Kings Vegetable Oil", 
        "Hypo Bleach", "Ariel Multi-wash", "Indomie Noodles Case", "Nestle Water 60cl",
        "Honeywell Flour 1kg", "Maggi Star Cube", "Knorr Chicken Cube", "Devon King's Oil 1L",
        "Onga Seasoning", "Power Pasta Spaghetti", "Irish Potatoes 1kg", "Cowbell Milk"
    ],
    "Health & Beauty": [
        "Shea Butter Lotion", "Cocoa Butter Cream", "Detol Antiseptic", "Colgate Toothpaste",
        "Garnier Face Wash", "Coconut Hair Oil", "Nivea Roll-on", "Classic Face Mask",
        "Perfume Blue Oud", "Argan Hair Serum", "Vaseline Jelly", "Dove Soap Bar",
        "Oral-B Toothbrush", "Maybelline Mascara", "L'Oreal Shampoo", "Old Spice Deodorant",
        "Neutrogena Sunscreen", "Body Wash Lavender", "Vitamin C Serum", "Axe Body Spray"
    ],
    "Home & Office": [
        "Smart Blender Pro", "Office Chair Flex", "Electric Kettle", "Micro-wave Oven",
        "Steam Iron", "Standing Fan", "LED Desk Lamp", "Leather Journal",
        "Non-stick Frying Pan", "Storage Box Set", "Pressure Cooker", "Toaster 2-Slice",
        "Rice Cooker 1.8L", "Water Dispenser", "Curtain Rod 2M", "Luxury Bedspread",
        "Dining Table Set", "Wall Clock Modern", "Gas Cooker 2-Burner", "Office Desk Oak"
    ],
    "Phones & Tablets": [
        "Samsung Galaxy S23", "iPhone 15 Pro Max", "iPad Air M1", "Redmi Note 12",
        "Infinix Hot 30", "Tecno Camon 20", "Samsung Tab A8", "Google Pixel 7",
        "Huawei P60 Pro", "Xiaomi 13 Ultra", "Surface Pro 9", "Oppo Reno 10",
        "Nokia G42 5G", "VIVO V27", "OnePlus 11", "Realme C53",
        "Itel P40", "Asus ROG Phone 7", "Sony Xperia 5 V", "Honor 90"
    ],
    "Computing": [
        "MacBook Air M2", "HP Laptop 15s", "Dell XPS 13", "Lenovo Legion 5",
        "Wireless Mouse Pro", "External SSD 1TB", "Laptop Stand", "Mechanical Keyboard",
        "Monitor 27-inch 4K", "WiFi Router 6", "HP Laser Printer", "Asus Zenbook 14",
        "Acer Swift Go", "Logitech Webcam 1080p", "USB Hub 7-in-1", "Power Bank 20000mAh",
        "Gaming Mouse Pad", "Headphone Stand", "Graphic Tablet", "Bag Backpack 15\""
    ],
    "Electronics": [
        "LG Smart TV 55\"", "Sony Soundbar 300W", "Home Theater 5.1", "Voltage Stabilizer",
        "Extension Box 4-Way", "Digital Camera 24MP", "Smart Watch Ultra", "Apple TV 4K",
        "DVD Player Multi", "Projector 1080p", "Rechargeable Fan", "Searchlight Power",
        "Binoculars 10x42", "Power Inverter 1.5KVA", "Solar Panel 200W", "Deep Freezer 200L",
        "Washing Machine 7kg", "Refrigerator 150L", "Home Gym Set", "Air Conditioner 1HP"
    ],
    "Fashion": [
        "Classic Leather Sneakers", "Slim Fit Navy Suit", "Casual Denim Jeans", "Silk Necktie Blue",
        "Leather Wallet Black", "Canvas Backpack", "Designer Sunglasses", "Wrist Watch Gold",
        "Summer Floral Dress", "Sports Jogger Set", "Polo Shirt White", "Luxury Handbag",
        "Ankle Boots Leather", "Sweater Cardigan", "Cotton Socks Set", "Boxer Shorts Blue",
        "Hat Fedora Style", "Scarf Winter Grey", "Belt Reversible", "Pajamas Set Cotton"
    ],
    "Baby Products": [
        "Huggies Diapers 50ct", "Baby Wipes 80pk", "Formula Nan Pro 1", "Baby Stroller Lite",
        "Feeding Bottle 240ml", "Baby Cot Mobile", "Johnson's Baby Bath", "Pacifier Set 2pk",
        "Teething Toy Silicone", "Baby Carrier Wrap", "Car Seat Group 1", "High Chair Foldable",
        "Baby Shoes Soft", "Onesies 5-Pack", "Crib Mattress", "Diaper Bag Multi",
        "Bottle Sterilizer", "Breast Pump Electric", "Baby Monitor Video", "Bath Tub Inflatable"
    ],
    "Gaming": [
        "PlayStation 5 Console", "Xbox Series X", "Nintendo Switch OLED", "DualSense Controller",
        "Gaming Headset Pro", "FIFA 24 Game Disc", "Spider-Man 2 PS5", "Xbox Game Pass 3M",
        "Gaming Chair Racer", "Desktop PC Core i9", "RTX 4070 Graphics", "Steam Deck 512GB",
        "Racing Wheel Set", "VR Headset Quest 3", "Retro Console Mini", "Switch Pro Controller",
        "COD Modern Warfare 3", "Elden Ring PS4", "Minecraft Card", "Fortnite V-Bucks"
    ],
    "Sporting Goods": [
        "Football Ball Size 5", "Basketball Spalding", "Tennis Racket Pro", "Yoga Mat 6mm",
        "Dumbbell 5kg Set", "Jump Rope Speed", "Swimming Goggles", "Bicycle Mountain 26\"",
        "Treadmill Electric", "Resistance Band Set", "Boxing Gloves 12oz", "Ab Roller Pro",
        "Sports Bottle 1L", "Knee Sleeve Pair", "Stopwatch Digital", "Skateboard Professional",
        "Cricket Bat Junior", "Badminton Set 4pk", "Table Tennis Paddle", "Golf Club Putter"
    ]
}

IMAGE_POOL = [
    "sneakers.png", "blender.png", "earbuds.png", "beauty.png", "chair.png", "bag.png"
]

CATEGORY_KEYWORDS = {
    "Supermarket": ["grocery", "food"],
    "Health & Beauty": ["beauty", "skincare"],
    "Home & Office": ["home", "office"],
    "Phones & Tablets": ["smartphone", "tablet"],
    "Computing": ["laptop", "computer"],
    "Electronics": ["electronics", "gadget"],
    "Fashion": ["fashion", "clothing"],
    "Baby Products": ["baby", "infant"],
    "Gaming": ["gaming", "console"],
    "Sporting Goods": ["sports", "fitness"],
}

STOPWORDS = {
    "and", "with", "for", "set", "pack", "pro", "max", "mini", "ultra", "plus", "lite",
    "new", "classic", "modern", "digital", "wireless", "smart", "blue", "black", "white",
    "gold", "grey", "gray", "red", "green", "pink", "1l", "1kg", "2pk", "5g",
}



def load_env(path):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def build_query(name, category):
    tokens = re.sub(r"[^a-z0-9 ]+", " ", name.lower()).split()
    tokens = [t for t in tokens if len(t) > 2 and not t.isdigit() and t not in STOPWORDS]
    tokens = tokens[:3]
    base = CATEGORY_KEYWORDS.get(category, ["product", "shopping"])
    query_terms = tokens + base
    return " ".join(query_terms) if query_terms else "product shopping"


def fetch_pexels_image(api_key, query, page=1, per_page=1):
    url = (
        "https://api.pexels.com/v1/search"
        f"?query={quote(query)}&per_page={per_page}&page={page}"
    )
    req = Request(url, headers={"Authorization": api_key})
    with urlopen(req, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    photos = payload.get("photos", [])
    if not photos:
        return None
    src = photos[0].get("src", {})
    return src.get("large") or src.get("medium") or src.get("original")

def build_image_url(name, category, lock_id, api_key):
    query = build_query(name, category)
    if api_key:
        page = (lock_id % 5) + 1
        image = fetch_pexels_image(api_key, query, page=page, per_page=1)
        if image:
            return image
        fallback = build_query(category, category)
        image = fetch_pexels_image(api_key, fallback, page=1, per_page=1)
        if image:
            return image
    flickr_query = ",".join(query.split()[:3] + CATEGORY_KEYWORDS.get(category, ["product"]))
    return f"https://loremflickr.com/640/640/{quote(flickr_query, safe=',')}?lock={lock_id}"


def populate():
    if not os.path.exists(DB_PATH):
        print("Database not found. Run app.py first.")
        return

    load_env(ENV_PATH)
    api_key = os.environ.get("PEXELS_API_KEY")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM products")
    now = datetime.now(timezone.utc).isoformat()

    product_id = 1
    for cat, names in CATEGORIES.items():
        for i, name in enumerate(names):
            price = 5000 + (i * 2000)
            
            image = build_image_url(name, cat, product_id, api_key)
            
            featured = 1 if i < 3 else 0
            cur.execute(
                "INSERT INTO products (name, price, tag, image, featured, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (name, price, cat, image, featured, now)
                )
            product_id += 1

    conn.commit()
    conn.close()
    print(f"Added {product_id-1} products with real image URLs.")

if __name__ == "__main__":
    populate()
