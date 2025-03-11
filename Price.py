
#Part 1: Imports required libraries and Setup

import os
import re
import logging
import time
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient, errors
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
from urllib.parse import urlparse
import streamlit as st
import threading
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import bcrypt  # For secure password hashing
import plotly.express as px
from PIL import Image
from streamlit_option_menu import option_menu
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from functools import lru_cache

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("price_tracker.log"), logging.StreamHandler()]
)


#Part 2: Streamlit Page Configuration

# Page icon
icon = Image.open("D:/All Documents/Projects/ECOMM/Logo.png")

# Page configuration
st.set_page_config(
    page_title="Multi-Platform Price Tracker & Alert System",
    page_icon=icon,
    layout="wide",
    initial_sidebar_state="expanded",
)

# Header
st.markdown("<h2 style='text-align: center; color: #000080;'>Ramachandra College of Engineering</h2>", unsafe_allow_html=True)
st.markdown("<h2 style='text-align: center; color: #BDB76B;'>Department of Computer Science & Engineering</h2>", unsafe_allow_html=True)
st.text("")
st.text("")

# Page Styling with Background Image
background_image_path = "D:/All Documents/Projects/ECOMM/Logo.png"
st.markdown(
    f"""
    <style>
    body {{
        background-image: url('{background_image_path}');
        background-size: cover;
        background-repeat: no-repeat;
        background-attachment: fixed;
        background-position: center;
    }}
    .header-title {{
        font-size: 35px;
        font-weight: medium;
        color: #708090;
        text-align: left;
        margin-bottom: 30px;
    }}
    .emotion-text {{
        font-size: 24px;
        font-weight: bold;
        color: #4169e1;
        text-align: center;
        margin-bottom: 20px;
    }}
    .song-info {{
        font-size: 18px;
        color: #008080;
        text-align: center;
        margin-bottom: 20px;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.balloons()

# Sidebar Menu
with st.sidebar:
    st.sidebar.image(icon, use_container_width=True)
    selected = option_menu(
        menu_title="Main Menu",
        options=["Home", "Project Details", "Contact", "Account", "Settings"],
        icons=["house", "book", "envelope", "person", "gear"],
        menu_icon="cast",
        default_index=0,
    )
    
# Part 3: Database Configuration

# Database Configuration
class DatabaseManager:
    def __init__(self):
        self.client = None
        self.db = None
        self.connect()

    def connect(self):
        try:
            # Use the MongoDB Atlas connection string from the .env file
            self.client = MongoClient("mongodb+srv://tagemo5926:B0vogxwZjX0cyOcK@cluster0.yfstd.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
            self.db = self.client[os.getenv("DB_NAME", "MyPriceTracker")]
            logging.info("✅ Successfully connected to MongoDB Atlas")
        except errors.ConnectionFailure as e:
            logging.error(f"❌ MongoDB Atlas connection failed: {e}")
            raise

    def get_collection(self, name="Products"):
        return self.db[name]

    def get_user_collection(self, name="Users"):
        return self.db[name]
    
    
# Part 4: Password Hashing and User Authentication


# Password Hashing
def hash_password(password):
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed_password

def verify_password(password, hashed_password):
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password)

# User Authentication
def authenticate_user(username, password):
    db = DatabaseManager()
    users_collection = db.get_user_collection()
    user = users_collection.find_one({"username": username})
    if user and verify_password(password, user["password"]):
        return True, user["name"], user["email"]
    return False, None, None

def register_user(username, password, name, email):
    db = DatabaseManager()
    users_collection = db.get_user_collection()
    
    if users_collection.find_one({"username": username}):
        return False, "Username already exists."
    
    hashed_password = hash_password(password)
    users_collection.insert_one({
        "username": username,
        "password": hashed_password,
        "name": name,
        "email": email
    })
    return True, "User registered successfully."

# Part 5: Base Product Parser

# Base Product Parser
class BaseProductParser:
    PLATFORM = "Generic"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 Edg/133.0.0.0"
    }

    def __init__(self, url):
        self.url = url
        self.soup = None
        self.product_data = {
            "name": "Unknown Product",
            "price": 0.0,
            "platform": self.PLATFORM,
            "url": url,
            "last_checked": datetime.now(),
            "username": None,
            "email": None
        }

    def fetch_page(self):
        try:
            session = requests.Session()
            retries = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
            session.mount("http://", HTTPAdapter(max_retries=retries))
            session.mount("https://", HTTPAdapter(max_retries=retries))

            response = session.get(self.url, headers=self.HEADERS, timeout=10)
            response.raise_for_status()
            self.soup = BeautifulSoup(response.content, "html.parser")
            return True
        except Exception as e:
            logging.error(f"Error fetching page: {e}")
            return False

    def parse_price(self):
        raise NotImplementedError

    def parse_name(self):
        raise NotImplementedError

    def get_product_details(self):
        if self.fetch_page():
            self.parse_name()
            self.parse_price()
        return self.product_data

    
# Part 6: Platform-Specific Parsers

# Flipkart Product Parser
class FlipkartParser(BaseProductParser):
    PLATFORM = "Flipkart"

    def parse_name(self):
        try:
            possible_name_tags = ["span.VU-ZEz", "h1._6EBuvT span", "h1"]
            for selector in possible_name_tags:
                name_tag = self.soup.select_one(selector)
                if name_tag:
                    self.product_data["name"] = name_tag.get_text(strip=True)
                    return
            logging.error("Product name not found, Flipkart may have changed HTML structure.")
        except Exception as e:
            logging.error(f"Error parsing name: {e}")

    def parse_price(self):
        try:
            possible_price_tags = ["div.Nx9bqj", "div._30jeq3._16Jk6d", "span._30jeq3"]
            for selector in possible_price_tags:
                price_tag = self.soup.select_one(selector)
                if price_tag:
                    price_str = price_tag.get_text(strip=True).replace("₹", "").replace(",", "")
                    price = re.search(r"\d+(\.\d+)?", price_str)
                    self.product_data["price"] = round(float(price.group()), 2) if price else 0.0
                    return
            logging.error("Price not found, Flipkart may have changed HTML structure.")
        except Exception as e:
            logging.error(f"Error parsing price: {e}")

# Amazon Product Parser
class AmazonParser(BaseProductParser):
    PLATFORM = "Amazon"

    def parse_name(self):
        try:
            name_tag = self.soup.find("span", id="productTitle")
            self.product_data["name"] = name_tag.get_text(strip=True) if name_tag else "Unknown Product"
        except Exception as e:
            logging.error(f"Error parsing name: {e}")

    def parse_price(self):
        try:
            price_str = None
            whole = self.soup.find("span", class_="a-price-whole")
            fraction = self.soup.find("span", class_="a-price-fraction")
            if whole:
                price_str = whole.get_text(strip=True).replace(",", "")
                if fraction:
                    price_str += f".{fraction.get_text(strip=True)}"
            if not price_str:
                price_tag = self.soup.find("span", class_="a-offscreen")
                if price_tag:
                    price_str = price_tag.get_text(strip=True).replace(",", "")
            if price_str:
                price = re.search(r"\d+(\.\d+)?", price_str)
                self.product_data["price"] = round(float(price.group()), 2) if price else 0.0
        except Exception as e:
            logging.error(f"Error parsing price: {e}")

# AJIO Product Parser
class AjioParser(BaseProductParser):
    PLATFORM = "AJIO"

    def get_product_details(self):
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        driver.get(self.url)
        time.sleep(5)  # Wait for content to load
        
        try:
            product_name = driver.find_element(By.CLASS_NAME, "prod-name").text.strip()
        except:
            product_name = "Unknown Product"
        
        try:
            price_str = driver.find_element(By.CLASS_NAME, "prod-sp").text.strip()
            price = re.search(r"\d+(\.\d+)?", price_str.replace("₹", "").replace(",", ""))
            self.product_data["price"] = round(float(price.group()), 2) if price else 0.0
        except:
            self.product_data["price"] = 0.0
        
        self.product_data["name"] = product_name
        driver.quit()
        
        return self.product_data

# Shopsy Product Parser
class ShopsyParser(BaseProductParser):
    PLATFORM = "Shopsy"

    def get_product_details(self):
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(self.url)
        
        wait = WebDriverWait(driver, 20)
        product_name, price = "Unknown Product", 0.0
        
        try:
            product_name = driver.title.split("Price in India")[0].strip()
        except Exception as e:
            logging.error(f"Error extracting product name: {e}")
        
        price_selectors = [
            (By.CLASS_NAME, "css-146c3p1"),
            (By.CSS_SELECTOR, ".css-146c3p1.r-cqee49.r-1vgyyaa.r-1rsjblm.r-13hce6t"),
            (By.XPATH, "//div[contains(@class, 'css-146c3p1')]"),
        ]
        
        for selector_type, selector_value in price_selectors:
            try:
                price_element = wait.until(EC.presence_of_element_located((selector_type, selector_value)))
                price_str = price_element.text.strip()
                if "Add to cart" in price_str:
                    raise Exception("Incorrect price extracted")
                price = float(price_str.replace("₹", "").replace(",", ""))
                break
            except Exception as e:
                logging.error(f"Failed to extract price using {selector_type}: {selector_value}. Error: {e}")
                continue
        
        if price == 0.0:
            try:
                meta_price = driver.find_element(By.XPATH, "//meta[@property='product:price:amount']")
                price = float(meta_price.get_attribute("content"))
            except Exception as e:
                logging.error(f"Failed to extract price using meta tag: {e}")
        
        self.product_data["name"] = product_name
        self.product_data["price"] = price
        driver.quit()
        
        return self.product_data

# Part 7: Email Manager

# Email Manager
class EmailManager:
    def __init__(self, receiver_email):
        self.sender = "multiplatformpricetracker@gmail.com"
        self.password = "hrlgzprcbgdknctj"
        self.receiver = receiver_email

    def send_alert(self, product, old_price):
        try:
            msg = MIMEMultipart()
            price_change = "increased" if product['price'] > old_price else "decreased"
            msg["Subject"] = f"📉 Price Alert: {product['name']} ({price_change})"
            msg["From"] = self.sender
            msg["To"] = self.receiver

            html = f"""
            <html>
                <body>
                    <h2>{product['name']}</h2>
                    <p>Price {price_change} on {product['platform']}:</p>
                    <p style="color: red; font-size: 24px;">
                        <del>₹{old_price}</del> → <strong>₹{product['price']}</strong>
                    </p>
                    <p><a href="{product['url']}">View Product</a></p>
                </body>
            </html>
            """
            msg.attach(MIMEText(html, "html"))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self.sender, self.password)
                server.sendmail(self.sender, self.receiver, msg.as_string())

            logging.info(f"📩 Email alert sent for {product['name']} to {self.receiver}")
        except Exception as e:
            logging.error(f"Failed to send email: {e}")

    def send_no_change_alert(self):
        try:
            msg = MIMEMultipart()
            msg["Subject"] = "📊 Price Tracker: No Price Changes"
            msg["From"] = self.sender
            msg["To"] = self.receiver

            html = """
            <html>
                <body>
                    <h2>Price Tracker Update</h2>
                    <p>All product prices remain the same.</p>
                </body>
            </html>
            """
            msg.attach(MIMEText(html, "html"))
            
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self.sender, self.password)
                server.sendmail(self.sender, self.receiver, msg.as_string())
            
            logging.info(f"📩 Sent 'no price changes' email to {self.receiver}")
        except Exception as e:
            logging.error(f"Failed to send email: {e}")

# Part 8: Price Monitor

# Price Monitor
class PriceMonitor:
    def __init__(self):
        self.db = DatabaseManager()
        self.collection = self.db.get_collection()
        self.price_history_collection = self.db.get_collection("PriceHistory")
        self.no_change_email_sent = False

    def save_price_history(self, product_id, price):
        try:
            self.price_history_collection.insert_one({
                "product_id": product_id,
                "price": price,
                "date": datetime.now()
            })
        except Exception as e:
            logging.error(f"Error saving price history: {e}")

    def validate_url(self, url):
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception as e:
            logging.error(f"Error validating URL: {e}")
            return False

    def add_product(self, url, username, email):
        if not self.validate_url(url):
            logging.error("❌ Invalid URL format")
            return False

        parser = self.get_parser(url)
        product = parser.get_product_details()
        product["username"] = username
        product["email"] = email

        try:
            existing = self.collection.find_one({"url": url, "username": username})
            if existing:
                logging.info(f"🔄 Product exists: {product['name']}")
                return False

            self.collection.insert_one(product)
            logging.info(f"✅ New product added: {product['name']}")
            return True
        except errors.PyMongoError as e:
            logging.error(f"Database error: {e}")
            return False

    def get_parser(self, url):
        domain = urlparse(url).netloc.lower()
        if "amazon" in domain:
            return AmazonParser(url)
        elif "flipkart" in domain:
            return FlipkartParser(url)
        elif "ajio" in domain:
            return AjioParser(url)
        elif "shopsy" in domain:
            return ShopsyParser(url)
        return BaseProductParser(url)

    def check_price_changes(self):
        try:
            products = self.collection.find()
            price_changed = False

            # Skip email if no products are being tracked
            if products.count() == 0:
                return

            for product in products:
                parser = self.get_parser(product['url'])
                new_product_data = parser.get_product_details()

                if new_product_data['price'] == 0.0:
                    logging.info(f"🔄 Price temporarily unavailable for {product['name']}")
                    continue

                self.save_price_history(product['_id'], new_product_data['price'])

                if product['price'] == 0.0:
                    self.collection.update_one(
                        {"_id": product['_id']},
                        {"$set": {"price": new_product_data['price'], "last_checked": datetime.now()}}
                    )
                    logging.info(f"🔄 Updated initial price for {product['name']}")
                    continue

                old_price = round(float(product['price']), 2)
                new_price = round(float(new_product_data['price']), 2)

                logging.info(f"🔄 Comparing prices for {product['name']}: Old Price = ₹{old_price}, New Price = ₹{new_price}")

                if new_price > old_price:
                    logging.info(f"🔼 Price increased for {product['name']} from ₹{old_price} to ₹{new_price}")
                    email_manager = EmailManager(product["email"])
                    email_manager.send_alert(new_product_data, old_price)
                    self.collection.update_one(
                        {"_id": product['_id']},
                        {"$set": {"price": new_price, "last_checked": datetime.now()}}
                    )
                    logging.info(f"✅ Updated price in database for {product['name']}")
                    price_changed = True
                elif new_price < old_price:
                    logging.info(f"🔽 Price decreased for {product['name']} from ₹{old_price} to ₹{new_price}")
                    email_manager = EmailManager(product["email"])
                    email_manager.send_alert(new_product_data, old_price)
                    self.collection.update_one(
                        {"_id": product['_id']},
                        {"$set": {"price": new_price, "last_checked": datetime.now()}}
                    )
                    logging.info(f"✅ Updated price in database for {product['name']}")
                    price_changed = True
                else:
                    logging.info(f"🔄 No price change for {product['name']}")
                    continue

            if not price_changed and not self.no_change_email_sent:
                email_manager = EmailManager(product["email"])
                email_manager.send_no_change_alert()
                self.no_change_email_sent = True
        except Exception as e:
            logging.error(f"Error checking price changes: {e}")
        
        
# Part 9: Background Thread for Price Monitoring

# Background Thread for Price Monitoring
def start_price_monitoring(monitor):
    while True:
        logging.info("🔍 Checking for price changes...")
        monitor.check_price_changes()
        logging.info("⏳ Next check in 1 minute...")
        time.sleep(60)  # Check every 1 minute
        

# Part 10: Streamlit UI Components


# Custom CSS for Styling
def load_css():
    st.markdown(
        """
        <style>
        .card {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 16px;
            margin: 8px 0;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }
        .card h3 {
            margin: 0;
            font-size: 18px;
        }
        .card p {
            margin: 4px 0;
            font-size: 14px;
        }
        .card a {
            color: #007bff;
            text-decoration: none;
        }
        .card button {
            background-color: #dc3545;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            cursor: pointer;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def product_card(product):
    st.markdown(
        f"""
        <div class="card">
            <h3>{product['name']}</h3>
            <p>Price: ₹{product['price']}</p>
            <p>Platform: {product['platform']}</p>
            <p>Last Checked: {product['last_checked']}</p>
            <a href="{product['url']}" target="_blank">View Product</a>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button(f"Compare Prices for {product['name']}", key=f"compare_{product['_id']}"):
        with st.spinner("Fetching prices from other platforms..."):
            comparison_data = compare_prices(product['name'], product['price'], product['platform'])
        
        st.write("### Price Comparison")
        st.table(comparison_data)

        import plotly.express as px
        fig = px.bar(comparison_data, x="platform", y="price", title="Price Comparison")
        st.plotly_chart(fig)

# Login Page
def login_page():
    st.title("🔒 Login")
    st.write("Please log in to access the Price Tracker Dashboard.")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        authenticated, name, email = authenticate_user(username, password)
        if authenticated:
            st.session_state["logged_in"] = True
            st.session_state["username"] = username
            st.session_state["name"] = name
            st.session_state["email"] = email
            st.query_params["page"] = "main"
            st.rerun()
        else:
            st.error("Incorrect username or password.")

    st.write("Don't have an account? Register below.")
    if st.button("Go to Register"):
        st.query_params["page"] = "register"
        st.rerun()

# Register Page
def register_page():
    st.title("📝 Register")
    st.write("Create a new account to start tracking prices.")

    new_username = st.text_input("New Username")
    new_password = st.text_input("New Password", type="password")
    name = st.text_input("Your Name")
    email = st.text_input("Your Email")
    if st.button("Register"):
        success, message = register_user(new_username, new_password, name, email)
        if success:
            st.success(message)
            st.query_params["page"] = "login"
            st.rerun()
        else:
            st.error(message)

    st.write("Already have an account? Log in below.")
    if st.button("Go to Login"):
        st.query_params["page"] = "login"
        st.rerun()

# Compare Prices Function
@lru_cache(maxsize=10)
def compare_prices(product_name, current_price, current_platform):
    platforms = {
        "Amazon": {
            "url": f"https://www.amazon.in/s?k={product_name.replace(' ', '+')}",
            "parser": AmazonParser
        },
        "Flipkart": {
            "url": f"https://www.flipkart.com/search?q={product_name.replace(' ', '%20')}",
            "parser": FlipkartParser
        },
        "AJIO": {
            "url": f"https://www.ajio.com/search/?text={product_name.replace(' ', '%20')}",
            "parser": AjioParser
        },
        "Shopsy": {
            "url": f"https://www.shopsy.in/search?q={product_name.replace(' ', '%20')}",
            "parser": ShopsyParser
        }
    }

    results = []
    threads = []

    results.append({
        "platform": current_platform,
        "price": current_price,
        "url": "Already Tracked"
    })

    for platform, data in platforms.items():
        if platform == current_platform:
            continue

        url = data["url"]
        parser_class = data["parser"]
        thread = threading.Thread(target=scrape_platform, args=(platform, url, parser_class, results))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    return results

def scrape_platform(platform, url, parser_class, results):
    try:
        parser = parser_class(url)
        product_data = parser.get_product_details()

        if product_data["price"] == 0.0:
            results.append({
                "platform": platform,
                "price": "Not Available",
                "url": "N/A"
            })
        else:
            results.append({
                "platform": platform,
                "price": product_data["price"],
                "url": url
            })
    except Exception as e:
        logging.error(f"Failed to fetch price from {platform}: {e}")
        results.append({
            "platform": platform,
            "price": "Not Available",
            "url": "N/A"
        })

# Main Dashboard
def main_dashboard():
    st.title("📉 Price Tracker Dashboard")
    st.write(f"Welcome, {st.session_state['name']}!")

    st.write("### Add a Product to Track")
    product_url = st.text_input("Enter Amazon, Flipkart, AJIO, or Shopsy product URL:")
    if st.button("Add Product"):
        monitor = PriceMonitor()
        if monitor.add_product(product_url, st.session_state["username"], st.session_state["email"]):
            st.success(f"✅ Product added successfully!")
        else:
            st.error("❌ Failed to add product. Please check the URL.")

    st.write("### Tracked Products")
    monitor = PriceMonitor()
    user_products = list(monitor.collection.find({"username": st.session_state["username"]}))

    # Pagination Logic
    if "page_number" not in st.session_state:
        st.session_state.page_number = 1

    items_per_page = 5
    total_pages = (len(user_products) // items_per_page + (1 if len(user_products) % items_per_page != 0 else 0))

    if total_pages > 1:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            if st.button("Previous Page") and st.session_state.page_number > 1:
                st.session_state.page_number -= 1
        with col2:
            st.write(f"Page {st.session_state.page_number} of {total_pages}")
        with col3:
            if st.button("Next Page") and st.session_state.page_number < total_pages:
                st.session_state.page_number += 1

    start_idx = (st.session_state.page_number - 1) * items_per_page
    end_idx = start_idx + items_per_page
    paginated_products = user_products[start_idx:end_idx]

    if paginated_products:
        for product in paginated_products:
            product_card(product)

            price_history = list(monitor.price_history_collection.find({"product_id": product['_id']}))
            if price_history:
                dates = [entry['date'] for entry in price_history]
                prices = [entry['price'] for entry in price_history]

                st.write("### Price History")
                fig = px.line(
                    x=dates, y=prices,
                    title=f"Price History for {product['name']}",
                    labels={"x": "Date", "y": "Price (₹)"}
                )
                st.plotly_chart(fig)
            else:
                st.write("No price history available for this product.")

            if st.button(f"Delete {product['name']}", key=product['_id']):
                if st.checkbox(f"Are you sure you want to delete {product['name']}?"):
                    monitor.collection.delete_one({"_id": product['_id']})
                    st.success(f"✅ Deleted {product['name']}")
                    st.rerun()
            st.write("---")
    else:
        st.write("No products found in the database.")

    if st.button("Logout"):
        st.session_state.clear()
        st.query_params["page"] = "login"
        st.rerun()

# Project Details Page
def project_details_page():
    st.markdown("<h2 class='sider-title' style='color: SlateGray;'>Project Details</h2>", unsafe_allow_html=True)
    st.write("")
    st.markdown("<h3 class='sider-title' style='color: black;'>Title:</h3>", unsafe_allow_html=True)
    st.write("")
    st.write("Multi-Platform Price Tracker and Alert System for E-Commerce Sites Using Web Scraping")
    st.write("")
    st.markdown("<h3 class='sider-title' style='color: black;'>Description:</h3>", unsafe_allow_html=True)
    st.write("")
    st.write("""
    The **Multi-Platform Price Tracker and Alert System for E-Commerce Sites Using Web Scraping** is a comprehensive tool designed to simplify and enhance the online shopping experience by automating the process of tracking product prices across multiple e-commerce platforms. This system leverages advanced **web scraping techniques** to extract real-time data on product prices, availability, discounts, and ratings from popular online stores such as **Amazon, Flipkart, AJIO, and Shopsy**. The collected data is stored in a **cloud-based database**, enabling users to monitor price changes over time and make informed purchasing decisions.

    #### **Key Features**:
    1. **Real-Time Price Tracking**:
       - The system continuously monitors product prices across multiple e-commerce platforms.
       - Users can add products by simply providing the product URL, and the system will track its price automatically.

    2. **Personalized Price Alerts**:
       - Users can set up personalized alerts to receive notifications via **email** when the price of a tracked product drops or increases.
       - Alerts include detailed information such as the old price, new price, and a direct link to the product.

    3. **Price History and Trends**:
       - The system maintains a historical record of price changes for each product, allowing users to analyze price trends over time.
       - Visualizations such as **line graphs** are provided to help users identify the best time to make a purchase.

    4. **Multi-Platform Support**:
       - The tool supports price tracking from multiple e-commerce platforms, including **Amazon, Flipkart, AJIO, and Shopsy**.
       - Each platform has a dedicated parser to handle its unique HTML structure and extract accurate product information.

    5. **User-Friendly Dashboard**:
       - The system features an intuitive **Streamlit-based dashboard** where users can:
         - Add and manage tracked products.
         - View detailed product information, including current price, platform, and last checked time.
         - Delete products they no longer wish to track.

    6. **User Authentication**:
       - Users can create an account, log in, and securely manage their tracked products.
       - The system uses **password hashing** to ensure the security of user credentials.

    7. **Email Notifications**:
       - Users receive email alerts when price changes are detected.
       - The system also sends a summary email if no price changes occur during a monitoring cycle.

    8. **Background Monitoring**:
       - Price monitoring runs in the background using **multi-threading**, ensuring real-time updates without interrupting the user experience.

    9. **Cloud Database Integration**:
       - The system uses **MongoDB Atlas** for cloud-based data storage, ensuring scalability and reliability.
       - Product details, user information, and price history are securely stored in the database.

    10. **Customizable and Extendable**:
        - The system is designed to be easily extendable, allowing support for additional e-commerce platforms in the future.
        - The modular architecture makes it simple to add new features or modify existing ones.

    #### **Technologies Used**:
    - **Web Scraping**: BeautifulSoup, Selenium
    - **Backend**: Python, MongoDB
    - **Frontend**: Streamlit
    - **Email Notifications**: SMTP (Gmail)
    - **Authentication**: bcrypt for password hashing
    - **Visualization**: Plotly for price history graphs
    - **Deployment**: Streamlit Cloud (or any cloud platform)

    #### **Benefits**:
    - **Time-Saving**: Automates the tedious process of manually checking prices across multiple platforms.
    - **Cost-Effective**: Helps users save money by alerting them to price drops and discounts.
    - **Informed Decisions**: Provides insights into price trends, enabling users to make smarter purchasing decisions.
    - **User-Friendly**: The intuitive interface makes it easy for users of all technical levels to use the system.

    #### **Applications**:
    - **Individual Shoppers**: Ideal for online shoppers looking to save money by tracking prices and receiving alerts for discounts.
    - **Businesses**: Useful for businesses monitoring competitor pricing and market trends.
    - **Market Analysts**: Provides valuable data for analyzing price fluctuations and consumer behavior.

    #### **How It Works**:
    1. **User Adds a Product**:
       - The user provides the product URL from a supported e-commerce platform.
       - The system uses web scraping to extract product details (name, price, etc.) and stores them in the database.

    2. **Background Monitoring**:
       - A background thread continuously monitors the prices of all tracked products at regular intervals.

    3. **Price Change Detection**:
       - If a price change is detected, the system sends an email alert to the user with the updated price information.

    4. **User Dashboard**:
       - Users can log in to the dashboard to view their tracked products, analyze price history, and manage their alerts.

    #### **Future Enhancements**:
    1. **Support for Additional Platforms**: Expand the system to support more e-commerce platforms.
    2. **Mobile App**: Develop a mobile application for easier access and notifications.
    3. **Advanced Analytics**: Add more advanced analytics features, such as price prediction and competitor analysis.
    4. **Social Sharing**: Allow users to share deals and discounts on social media platforms.
    """)
    st.write("")
    image = "D:/All Documents/Projects/ECOMM/Logo.png"
    image = Image.open(image)
    st.image(image, caption="Logo", width=500, use_container_width=True, clamp=False, channels="RGB", output_format="auto")

# 🔹 Contact Section
def contact_page():
    st.markdown("<h2 class='sider-title' style='color: SlateGray;'>Project Team</h2>", unsafe_allow_html=True)
    st.text("")

    # Team member details
    team_members = [
        {
            "name": "Sidhardha Kanigiri",
            "Roll_Number": "21ME1A05G0",
            "Dept": "Department of Computer Science & Engineering"
        },
        {
            "name": "Likhitha Desabathula",
            "Roll_Number": "21ME1A05E5",
            "Dept": "Department of Computer Science & Engineering"
        },
        {
            "name": "Venkata Pranay N",
            "Roll_Number": "21ME1A05G3",
            "Dept": "Department of Computer Science & Engineering"
        },
        {
            "name": "Naga Babu Gunduboina",
            "Roll_Number": "21ME1A05F0",
            "Dept": "Department of Computer Science & Engineering"
        }
    ]

    # Display team member details with images side by side
    col1, col2, col3, col4 = st.columns(4)

    for i, member in enumerate(team_members):
        with locals()[f"col{i+1}"]:
            st.write(f"Name: {member['name']}")
            st.write(f"Roll Number: {member['Roll_Number']}")
            st.write(f"Department: {member['Dept']}")

# 🔹 Account Section
def account_page():
    st.markdown("<h2 class='sider-title' style='color: SlateGray;'>Account</h2>", unsafe_allow_html=True)
    st.text("")

    # Check if the user is logged in
    if "logged_in" in st.session_state and st.session_state["logged_in"]:
        st.write(f"*Name:* {st.session_state['name']}")
        st.write(f"*Email:* {st.session_state['email']}")

        # Logout Button
        if st.button("Logout"):
            st.session_state.clear()  # Clear the session state
            st.success("You have been logged out.")  # Show a success message
            # Do not redirect to the login page here
    else:
        st.warning("Please log in to view your account details.")

# 🔹 Settings Page
def settings_page():
    st.title("⚙️ Settings")
    st.write("Customize your price tracking preferences.")

    # Frequency of price checks
    frequency = st.selectbox(
        "Price Check Frequency",
        options=["Every 1 Minute","Every 5 minutes", "Every 15 minutes", "Every 1 hour", "Every 24 hours"],
        index=0
    )

    # Email alert preferences
    email_alerts = st.multiselect(
        "Receive Email Alerts For",
        options=["Price Drops", "Price Increases"],
        default=["Price Drops"]
    )

    if st.button("Save Preferences"):
        # Save preferences to the database
        db = DatabaseManager()
        db.get_user_collection().update_one(
            {"username": st.session_state["username"]},
            {"$set": {"frequency": frequency, "email_alerts": email_alerts}}
        )
        st.success("Preferences saved successfully!")

# 🔹 Main Function
def main():
    # Load custom CSS
    load_css()

    # Initialize session state for login
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
        st.session_state["username"] = None
        st.session_state["name"] = None
        st.session_state["email"] = None

    # Get the current page from query parameters
    current_page = st.query_params.get("page", "login")  # Default to login page

    # Render the appropriate page based on the selected option
    if selected == "Home":
        if current_page == "login":
            login_page()
        elif current_page == "register":
            register_page()
        elif current_page == "main" and st.session_state["logged_in"]:
            main_dashboard()
        else:
            st.warning("Please log in to access the dashboard.")
            st.query_params["page"] = "login"  # Redirect to login if not logged in
            st.rerun()  # Force rerun to update the page

    elif selected == "Project Details":
        if st.session_state["logged_in"]:
            project_details_page()
        else:
            st.warning("Please log in to access Project Details.")
            st.query_params["page"] = "login"  # Redirect to login page
            st.rerun()  # Force rerun to update the page

    elif selected == "Contact":
        if st.session_state["logged_in"]:
            contact_page()
        else:
            st.warning("Please log in to access Contact.")
            st.query_params["page"] = "login"  # Redirect to login page
            st.rerun()  # Force rerun to update the page

    elif selected == "Account":
        if st.session_state["logged_in"]:
            account_page()
        else:
            st.warning("Please log in to access your Account.")
            st.query_params["page"] = "login"  # Redirect to login page
            st.rerun()  # Force rerun to update the page

    elif selected == "Settings":
        if st.session_state["logged_in"]:
            settings_page()
        else:
            st.warning("Please log in to access Settings.")
            st.query_params["page"] = "login"  # Redirect to login page
            st.rerun()  # Force rerun to update the page

# Run the Streamlit app
if __name__ == "__main__":
    # Start the price monitoring thread
    monitor = PriceMonitor()
    monitor_thread = threading.Thread(target=start_price_monitoring, args=(monitor,), daemon=True)
    monitor_thread.start()

    # Run the Streamlit app
    main()
