from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse

app = Flask(__name__)
CORS(app)

TECHNICAL_KEYWORDS = [
    'fiche technique', 'technical sheet', 'fiche produit', 'fiche-produit', 'fiche-technique',
    'datasheet', 'specification', 'tech sheet', 'ft', 'ts',
    'télécharger', 'download', 'pdf'
]

def is_likely_technical_sheet(link_text, href, wine_name):
    """Scores a link based on its likelihood of being a technical sheet."""
    combined_text = (str(link_text) + ' ' + str(href)).lower()
    score = 0
    
    # Check for technical keywords
    for keyword in TECHNICAL_KEYWORDS:
        if keyword in combined_text:
            score += 3
            
    # Check if href ends with .pdf
    if href and '.pdf' in href.lower():
        score += 5
        
    # Bonus for wine name
    if wine_name and wine_name.lower() in combined_text:
        score += 2
        
    # Bonus for vintage (simple check for 4 digits starting with 20 or 19)
    if re.search(r'\b(20\d{2}|19\d{2})\b', combined_text):
        score += 1
        
    return score

@app.route('/find-pdfs', methods=['POST'])
def find_pdfs():
    try:
        data = request.get_json()
        url = data.get('url')
        wine_name = data.get('wine_name', '')
        
        if not url:
            return jsonify({'error': 'URL required'}), 400
            
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
            'Connection': 'keep-alive'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'lxml') # Using better lxml parser
        
        candidate_links = []
        
        for link in soup.find_all('a', href__=True):
            href = link['href']
            link_text = link.get_text(strip=True)
            
            # Skip irrelevant links
            if href.startswith(('#', 'javascript:', 'mailto:')):
                continue

            # Calculate score
            score = is_likely_technical_sheet(link_text, href, wine_name)
            
            if score > 0:
                full_url = urljoin(url, href)
                candidate_links.append({
                    'url': full_url,
                    'text': link_text,
                    'score': score
                })
        
        # Remove duplicates based on URL
        unique_links = {link['url']: link for link in candidate_links}.values()
        
        # Sort by score, descending
        sorted_links = sorted(list(unique_links), key=lambda x: x['score'], reverse=True)
        
        return jsonify({
            'success': True,
            'pdfs_found': len(sorted_links),
            'pdfs': sorted_links[:10],
            'page_title': soup.title.string if soup.title else 'Unknown'
        })
        
    except requests.exceptions.RequestException as e:
        return jsonify({'success': False, 'error': f'Failed to fetch URL: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f'Processing error: {str(e)}'}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
