from flask import Flask, render_template, request, jsonify, redirect, url_for
import json
import os
import requests
from datetime import datetime
from urllib.parse import urlparse
import base64
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
DATA_FILE = 'games.json'

# Configuration IGDB
IGDB_CLIENT_ID = os.getenv('IGDB_CLIENT_ID')
IGDB_CLIENT_SECRET = os.getenv('IGDB_CLIENT_SECRET')
IGDB_ACCESS_TOKEN = None

def get_igdb_access_token():
    """Obtient un token d'accès IGDB"""
    global IGDB_ACCESS_TOKEN
    
    if not IGDB_CLIENT_ID or not IGDB_CLIENT_SECRET:
        print("⚠️  Clés IGDB non configurées. Les bannières ne fonctionneront pas.")
        return None
    
    try:
        response = requests.post(
            'https://id.twitch.tv/oauth2/token',
            params={
                'client_id': IGDB_CLIENT_ID,
                'client_secret': IGDB_CLIENT_SECRET,
                'grant_type': 'client_credentials'
            }
        )
        response.raise_for_status()
        IGDB_ACCESS_TOKEN = response.json()['access_token']
        return IGDB_ACCESS_TOKEN
    except Exception as e:
        print(f"❌ Erreur lors de l'obtention du token IGDB: {e}")
        return None

def search_igdb_game(game_name):
    """Recherche un jeu sur IGDB et retourne l'URL de la bannière"""
    if not IGDB_ACCESS_TOKEN:
        get_igdb_access_token()
    
    if not IGDB_ACCESS_TOKEN:
        return None
    
    try:
        # Requête à l'API IGDB
        headers = {
            'Client-ID': IGDB_CLIENT_ID,
            'Authorization': f'Bearer {IGDB_ACCESS_TOKEN}'
        }
        
        # Query pour rechercher le jeu
        query = f'''
        fields name, cover.url, cover.image_id;
        search "{game_name}";
        limit 1;
        '''
        
        response = requests.post(
            'https://api.igdb.com/v4/games',
            headers=headers,
            data=query
        )
        response.raise_for_status()
        
        games = response.json()
        
        if games and 'cover' in games[0] and games[0]['cover']:
            # Récupérer l'URL de l'image en haute résolution
            cover_url = games[0]['cover']['url']
            # Convertir l'URL pour obtenir une image plus grande
            large_cover_url = cover_url.replace('t_thumb', 't_cover_big')
            return f"https:{large_cover_url}"
        
        return None
        
    except Exception as e:
        print(f"❌ Erreur lors de la recherche IGDB pour {game_name}: {e}")
        return None

def load_games():
    """Charge les données depuis le fichier JSON"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        # Structure par défaut
        return {
            "name": "MA BIBLIOTHÈQUE DE JEUX",
            "downloads": []
        }

def save_games(data):
    """Sauvegarde les données dans le fichier JSON"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def check_url(url):
    """Vérifie si un lien de téléchargement fonctionne"""
    try:
        response = requests.head(url, timeout=10, allow_redirects=True)
        return response.status_code == 200
    except:
        return False

def format_file_size(size_bytes):
    """Formate la taille du fichier en unités lisibles"""
    if not size_bytes:
        return "Inconnu"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def search_games(query, games_data):
    """Recherche des jeux par titre"""
    if not query:
        return games_data['downloads']
    
    query = query.lower()
    results = []
    
    for game in games_data['downloads']:
        if query in game['title'].lower():
            results.append(game)
    
    return results

@app.route('/')
def index():
    """Page principale"""
    data = load_games()
    search_query = request.args.get('search', '')
    
    if search_query:
        filtered_games = search_games(search_query, data)
        # Créer une copie des données avec les jeux filtrés
        filtered_data = data.copy()
        filtered_data['downloads'] = filtered_games
        return render_template('index.html', data=filtered_data, search_query=search_query)
    
    return render_template('index.html', data=data, search_query=search_query)

@app.route('/add', methods=['POST'])
def add_game():
    """Ajoute un nouveau jeu"""
    data = load_games()
    
    title = request.form.get('title')
    uri = request.form.get('uri')
    file_size = request.form.get('fileSize', '')
    
    if title and uri:
        # Rechercher la bannière sur IGDB
        banner_url = search_igdb_game(title)
        
        new_game = {
            "title": title,
            "uris": [uri],
            "uploadDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "fileSize": file_size,
            "bannerUrl": banner_url  # Ajouter l'URL de la bannière
        }
        data['downloads'].append(new_game)
        save_games(data)
    
    return redirect(url_for('index'))

@app.route('/edit/<int:game_id>', methods=['POST'])
def edit_game(game_id):
    """Modifie un jeu existant"""
    data = load_games()
    
    if 0 <= game_id < len(data['downloads']):
        title = request.form.get('title')
        uri = request.form.get('uri')
        file_size = request.form.get('fileSize', '')
        
        if title and uri:
            # Rechercher une nouvelle bannière si le titre a changé
            if title != data['downloads'][game_id]['title']:
                banner_url = search_igdb_game(title)
                data['downloads'][game_id]['bannerUrl'] = banner_url
            
            data['downloads'][game_id]['title'] = title
            data['downloads'][game_id]['uris'] = [uri]
            data['downloads'][game_id]['fileSize'] = file_size
            data['downloads'][game_id]['uploadDate'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            save_games(data)
    
    return redirect(url_for('index'))

@app.route('/delete/<int:game_id>')
def delete_game(game_id):
    """Supprime un jeu"""
    data = load_games()
    
    if 0 <= game_id < len(data['downloads']):
        data['downloads'].pop(game_id)
        save_games(data)
    
    return redirect(url_for('index'))

@app.route('/check_url/<int:game_id>')
def check_game_url(game_id):
    """Vérifie si le lien d'un jeu fonctionne"""
    data = load_games()
    
    if 0 <= game_id < len(data['downloads']):
        game = data['downloads'][game_id]
        if game['uris']:
            is_valid = check_url(game['uris'][0])
            return jsonify({
                'valid': is_valid,
                'message': '✅ Lien fonctionnel' if is_valid else '❌ Lien cassé'
            })
    
    return jsonify({'valid': False, 'message': 'Erreur de vérification'})

@app.route('/update_library_name', methods=['POST'])
def update_library_name():
    """Met à jour le nom de la bibliothèque"""
    data = load_games()
    new_name = request.form.get('library_name')
    
    if new_name:
        data['name'] = new_name
        save_games(data)
    
    return redirect(url_for('index'))

@app.route('/clear_search')
def clear_search():
    """Efface la recherche et retourne à la liste complète"""
    return redirect(url_for('index'))

@app.route('/refresh_banner/<int:game_id>')
def refresh_banner(game_id):
    """Rafraîchit la bannière d'un jeu"""
    data = load_games()
    
    if 0 <= game_id < len(data['downloads']):
        game = data['downloads'][game_id]
        banner_url = search_igdb_game(game['title'])
        data['downloads'][game_id]['bannerUrl'] = banner_url
        save_games(data)
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Obtenir le token IGDB au démarrage
    get_igdb_access_token()
    app.run(debug=True, host='0.0.0.0', port=5000)