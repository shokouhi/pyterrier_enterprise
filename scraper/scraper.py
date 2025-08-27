import requests
from bs4 import BeautifulSoup
import sqlite3
import time
import os

def fetch_similar_sites(url):
    """Fetch similar sites from website.informer.com for a given URL."""
    # Clean the URL: remove protocol and trailing slashes
    clean_url = url.replace('https://', '').replace('http://', '').rstrip('/')
    search_url = f"https://website.informer.com/{clean_url}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    try:
        response = requests.get(search_url, headers=headers)
        
        if response.status_code != 200:
            print(f"Failed to fetch data for {url}, status code: {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        similar_sites = []

        # Update the selector and clean the text
        for site in soup.select('.history_websites'):
            site_text = site.get_text()
            # Get the first line before any Global rank or Daily Visitors text
            clean_site = site_text.split('\n')[0].strip()
            if clean_site:
                similar_sites.append(clean_site)

        return similar_sites
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data for {url}: {e}")
        return []

def initialize_database():
    """Initialize the SQLite database to store similar site data."""
    conn = sqlite3.connect('similar_sites.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site TEXT UNIQUE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS site_relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_site TEXT,
            similar_site TEXT,
            FOREIGN KEY(similar_site) REFERENCES sites(site)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS site_counts (
            site TEXT UNIQUE,
            count INTEGER DEFAULT 0
        )
    ''')

    conn.commit()
    conn.close()

def save_to_database(source_site, similar_sites):
    """Save the source site and its similar sites to the database."""
    conn = sqlite3.connect('similar_sites.db')
    cursor = conn.cursor()

    # Insert source site
    cursor.execute("INSERT OR IGNORE INTO sites (site) VALUES (?)", (source_site,))

    for site in similar_sites:
        # Insert similar site
        cursor.execute("INSERT OR IGNORE INTO sites (site) VALUES (?)", (site,))

        # Record the relation
        cursor.execute("INSERT INTO site_relations (source_site, similar_site) VALUES (?, ?)", (source_site, site))

        # Update count of similar site
        cursor.execute(
            "INSERT INTO site_counts (site, count) VALUES (?, 1) ON CONFLICT(site) DO UPDATE SET count = count + 1",
            (site,)
        )

    conn.commit()
    conn.close()

def display_database():
    """Display the contents of the database."""
    conn = sqlite3.connect('similar_sites.db')
    cursor = conn.cursor()

    print("\nSites Table:")
    for row in cursor.execute("SELECT * FROM sites"):
        print(row)

    print("\nSite Relations Table:")
    for row in cursor.execute("SELECT * FROM site_relations"):
        print(row)

    print("\nSite Counts Table:")
    for row in cursor.execute("SELECT * FROM site_counts"):
        print(row)

    conn.close()

def main(urls):
    """Main function to process the list of URLs."""
    # Delete existing database
    if os.path.exists('similar_sites.db'):
        os.remove('similar_sites.db')
    
    initialize_database()

    for url in urls:
        print(f"\nProcessing {url}...")
        similar_sites = fetch_similar_sites(url)

        if similar_sites:
            print("Found similar sites:")
            for site in similar_sites:
                print(f"- {site}")
            save_to_database(url, similar_sites)
        else:
            print(f"No similar sites found for {url}")

        time.sleep(10)  # Respectful delay to avoid being blocked

if __name__ == "__main__":
    urls_to_process = [
    "anakatarina.com", 
    "danabronfman.com", 
    "tarinthomas.com", 
    "mooreaseal.com/collections/fine-jewelry", 
    "agathavazjewelry.com", 
    "bario-neal.com", 
    "vrai.com", 
    "catorilife.com/collections", 
    "alexmonroe.com", 
    "abseas.shop/ab-seas", 
    "yamnyc.com", 
    "anandakhalsa.com", 
    "tskies.com",
    "monarcjewellery.com", 
    "emiconner.com",   
    "pippasmall.com/en-us/collections/all",      
    "presleyoldham.com", 
    "tenthousandthingsnyc.com", 
    "brionyraymond.com/pages/create-your-own-piece", 
    "larkspurandhawk.com/pages/a-nod-to-the-past", 
    "davidyurman.com", 
    "almasika.com", 
    "viltier.com", 
    "ireneneuwirth.com", 
    "rennajewels.com"
    ]

    main(urls_to_process)
