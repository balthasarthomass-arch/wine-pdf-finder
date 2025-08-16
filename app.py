from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

app = Flask(__name__)
CORS(app)

# Keywords indicating a technical sheet, in French and English
TECHNICAL_KEYWORDS = [
    'fiche technique', 'technical sheet', 'fiche produit', 'datasheet',
    'télécharger', 'download', 'pdf', 'ft', 'ts', 'fiche-technique', 'fiche-produit'
]

def find_links(url, wine_name):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.google.com/'
    }
    
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    
    # Use response.text and let BeautifulSoup handle encoding
    soup = BeautifulSoup(response.text, 'lxml')
    
    candidates = []
    
    # --- Strategy 1: Find all <a> tags and score them ---
    for link in soup.find_all('a', href__=True):
        href = link['href']
        text = link.get_text(strip=True).lower()
        
        # Skip junk links
        if not href or href.startswith(('#', 'javascript:', 'mailto:')):
            continue
            
        score = 0
        combined_text = text + ' ' + href.lower()
        
        for keyword in TECHNICAL_KEYWORDS:
            if keyword in combined_text:
                score += 1
        
        if '.pdf' in href.lower():
            score += 2 # Higher score for direct PDF links
        
        if wine_name and wine_name.lower() in combined_text:
            score += 1

        if score > 0:
            full_url = urljoin(url, href)
            candidates.append({'url': full_url, 'text': link.get_text(strip=True), 'score': score, 'method': 'tag_scan'})

    # --- Strategy 2: Search entire text for URL-like strings ending in .pdf ---
    # This can find URLs that are not in <a> tags
    pdf_regex = r'https?://[^\s"\'<>]+?\.pdf'
    found_in_text = re.findall(pdf_regex, response.text, re.IGNORECASE)
    
    for pdf_url in found_in_text:
        candidates.append({'url': pdf_url, 'text': 'Trouvé dans le texte de la page', 'score': 5, 'method': 'regex_scan'})

    # --- Consolidate and Rank ---
    # Remove duplicates, keeping the one with the highest score
    final_links = {}
    for link in candidates:
        if link['url'] not in final_links or link['score'] > final_links[link['url']]['score']:
            final_links[link['url']] = link
            
    # Convert back to a list and sort
    sorted_links = sorted(list(final_links.values()), key=lambda x: x['score'], reverse=True)
    
    return sorted_links, soup.title.string if soup.title else 'No Title Found'


@app.route('/find-pdfs', methods=['POST'])
def find_pdfs_endpoint():
    try:
        data = request.get_json()
        url = data.get('url')
        wine_name = data.get('wine_name', '')
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
            
        found_links, page_title = find_links(url, wine_name)
        
        return jsonify({
            'success': True,
            'pdfs_found': len(found_links),
            'pdfs': found_links,
            'page_title': page_title
        })

    except requests.exceptions.RequestException as e:
        return jsonify({'success': False, 'error': f'Network or HTTP error: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f'An unexpected error occurred: {str(e)}'}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
