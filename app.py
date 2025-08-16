from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
import time

app = Flask(__name__)
CORS(app)  # Permet à Base44 d'appeler l'API

@app.route('/find-pdfs', methods=['POST'])
def find_pdfs():
    try:
        data = request.get_json()
        url = data.get('url')
        wine_name = data.get('wine_name', '')
        
        if not url:
            return jsonify({'error': 'URL required'}), 400
            
        # Headers pour simuler un navigateur
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Récupérer la page
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parser le HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Trouver tous les liens PDF
        pdf_links = []
        
        # Chercher tous les liens <a> avec href contenant .pdf
        for link in soup.find_all('a', href__=True):
            href = link['href']
            if '.pdf' in href.lower():
                # Convertir en URL absolue
                full_url = urljoin(url, href)
                
                # Récupérer le texte du lien pour context
                link_text = link.get_text(strip=True)
                
                pdf_links.append({
                    'url': full_url,
                    'text': link_text,
                    'is_technical_sheet': is_likely_technical_sheet(link_text, href, wine_name)
                })
        
        # Trier par pertinence (fiches techniques en premier)
        pdf_links.sort(key=lambda x: x['is_technical_sheet'], reverse=True)
        
        return jsonify({
            'success': True,
            'pdfs_found': len(pdf_links),
            'pdfs': pdf_links[:10],  # Limiter à 10 résultats
            'page_title': soup.title.string if soup.title else 'Unknown'
        })
        
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Failed to fetch URL: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Processing error: {str(e)}'}), 500

def is_likely_technical_sheet(link_text, href, wine_name):
    """Détermine si un PDF est probablement une fiche technique"""
    technical_keywords = [
        'fiche technique', 'technical sheet', 'fiche produit',
        'datasheet', 'specification', 'tech sheet'
    ]
    
    combined_text = (link_text + ' ' + href).lower()
    
    # Bonus si contient le nom du vin
    score = 0
    if wine_name and wine_name.lower() in combined_text:
        score += 2
    
    # Bonus si contient des mots-clés techniques
    for keyword in technical_keywords:
        if keyword in combined_text:
            score += 3
            
    return score > 0

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)