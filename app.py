from flask import Flask, render_template, request, jsonify, redirect, url_for
import json
import os
import requests
from datetime import datetime
from urllib.parse import urlparse
import base64
from dotenv import load_dotenv
import re

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

def calculate_total_size(games_data):
    """Calcule la taille totale des jeux en GB"""
    total_gb = 0
    
    for game in games_data['downloads']:
        if game.get('fileSize'):
            size_str = game['fileSize'].lower().strip()
            
            # Extraire le nombre et l'unité
            match = re.search(r'([\d.]+)\s*(gb|mb|kb|b)', size_str)
            if match:
                number = float(match.group(1))
                unit = match.group(2)
                
                # Convertir en GB
                if unit == 'gb':
                    total_gb += number
                elif unit == 'mb':
                    total_gb += number / 1024
                elif unit == 'kb':
                    total_gb += number / (1024 * 1024)
                elif unit == 'b':
                    total_gb += number / (1024 * 1024 * 1024)
    
    return total_gb

def count_verified_games(games_data):
    """Compte le nombre de jeux vérifiés IGDB"""
    verified_count = 0
    for game in games_data['downloads']:
        if game.get('igdbId') and game['igdbId'] != 'custom':
            verified_count += 1
    return verified_count

def search_igdb_games(game_name, limit=10):
    """Recherche des jeux sur IGDB et retourne une liste de suggestions"""
    if not IGDB_ACCESS_TOKEN:
        get_igdb_access_token()
    
    if not IGDB_ACCESS_TOKEN:
        return []
    
    try:
        headers = {
            'Client-ID': IGDB_CLIENT_ID,
            'Authorization': f'Bearer {IGDB_ACCESS_TOKEN}'
        }
        
        # Query pour rechercher les jeux
        query = f'''
        fields name, cover.url, cover.image_id, first_release_date;
        search "{game_name}";
        limit {limit};
        '''
        
        response = requests.post(
            'https://api.igdb.com/v4/games',
            headers=headers,
            data=query
        )
        response.raise_for_status()
        
        games = response.json()
        suggestions = []
        
        for game in games:
            cover_url = None
            if 'cover' in game and game['cover']:
                cover_url = game['cover']['url'].replace('t_thumb', 't_cover_small')
                cover_url = f"https:{cover_url}"
            
            # Formater la date de sortie
            release_date = None
            if 'first_release_date' in game and game['first_release_date']:
                release_timestamp = game['first_release_date']
                release_date = datetime.fromtimestamp(release_timestamp).strftime('%Y')
            
            suggestions.append({
                'id': game['id'],
                'name': game['name'],
                'cover_url': cover_url,
                'release_year': release_date
            })
        
        return suggestions
        
    except Exception as e:
        print(f"❌ Erreur lors de la recherche IGDB pour {game_name}: {e}")
        return []

def search_igdb_game_by_id(game_id):
    """Recherche un jeu spécifique par son ID IGDB"""
    if not IGDB_ACCESS_TOKEN:
        get_igdb_access_token()
    
    if not IGDB_ACCESS_TOKEN:
        return None
    
    try:
        headers = {
            'Client-ID': IGDB_CLIENT_ID,
            'Authorization': f'Bearer {IGDB_ACCESS_TOKEN}'
        }
        
        query = f'''
        fields name, cover.url, cover.image_id;
        where id = {game_id};
        '''
        
        response = requests.post(
            'https://api.igdb.com/v4/games',
            headers=headers,
            data=query
        )
        response.raise_for_status()
        
        games = response.json()
        if games and 'cover' in games[0] and games[0]['cover']:
            cover_url = games[0]['cover']['url']
            large_cover_url = cover_url.replace('t_thumb', 't_cover_big')
            return {
                'name': games[0]['name'],
                'banner_url': f"https:{large_cover_url}"
            }
        
        return None
        
    except Exception as e:
        print(f"❌ Erreur lors de la recherche IGDB par ID {game_id}: {e}")
        return None

def load_games():
    """Charge les données depuis le fichier JSON"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
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
    
    # Calculer les statistiques
    total_size_gb = calculate_total_size(data)
    verified_count = count_verified_games(data)
    total_games = len(data['downloads'])
    
    # Formater la taille totale
    if total_size_gb >= 1:
        total_size_display = f"{total_size_gb:.1f} GB"
    else:
        total_size_mb = total_size_gb * 1024
        total_size_display = f"{total_size_mb:.1f} MB"
    
    if search_query:
        filtered_games = search_games(search_query, data)
        filtered_data = data.copy()
        filtered_data['downloads'] = filtered_games
        
        # Recalculer pour les résultats filtrés
        total_size_gb_filtered = calculate_total_size(filtered_data)
        verified_count_filtered = count_verified_games(filtered_data)
        
        if total_size_gb_filtered >= 1:
            total_size_display = f"{total_size_gb_filtered:.1f} GB"
        else:
            total_size_mb = total_size_gb_filtered * 1024
            total_size_display = f"{total_size_mb:.1f} MB"
        
        return render_template('index.html', 
                             data=filtered_data, 
                             search_query=search_query,
                             total_games=len(filtered_games),
                             total_size=total_size_display,
                             verified_games=verified_count_filtered)
    
    return render_template('index.html', 
                         data=data, 
                         search_query=search_query,
                         total_games=total_games,
                         total_size=total_size_display,
                         verified_games=verified_count)

@app.route('/add', methods=['POST'])
def add_game():
    """Ajoute un nouveau jeu"""
    data = load_games()
    
    title = request.form.get('title')
    uri = request.form.get('uri')
    file_size = request.form.get('fileSize', '')
    igdb_id = request.form.get('igdb_id')
    
    if title and uri:
        banner_url = None
        
        # Si un ID IGDB est fourni, utiliser les données officielles
        if igdb_id and igdb_id != 'custom':
            igdb_data = search_igdb_game_by_id(igdb_id)
            if igdb_data:
                title = igdb_data['name']  # Utiliser le nom officiel
                banner_url = igdb_data['banner_url']
        else:
            # Rechercher la bannière pour le nom personnalisé
            banner_url = search_igdb_game_by_id(None)  # Cette fonction sera ajustée
        
        new_game = {
            "title": title,
            "uris": [uri],
            "uploadDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "fileSize": file_size,
            "bannerUrl": banner_url,
            "igdbId": igdb_id if igdb_id != 'custom' else None
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
        igdb_id = request.form.get('igdb_id')
        
        if title and uri:
            banner_url = None
            
            # Si un ID IGDB est fourni, utiliser les données officielles
            if igdb_id and igdb_id != 'custom':
                igdb_data = search_igdb_game_by_id(igdb_id)
                if igdb_data:
                    title = igdb_data['name']
                    banner_url = igdb_data['banner_url']
            else:
                # Rechercher une nouvelle bannière si le titre a changé
                if title != data['downloads'][game_id]['title']:
                    igdb_data = search_igdb_game_by_id(None)
                    if igdb_data:
                        banner_url = igdb_data['banner_url']
            
            data['downloads'][game_id]['title'] = title
            data['downloads'][game_id]['uris'] = [uri]
            data['downloads'][game_id]['fileSize'] = file_size
            data['downloads'][game_id]['uploadDate'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            data['downloads'][game_id]['bannerUrl'] = banner_url
            data['downloads'][game_id]['igdbId'] = igdb_id if igdb_id != 'custom' else None
            
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
        # Rechercher le jeu par son titre actuel
        suggestions = search_igdb_games(game['title'], limit=1)
        if suggestions:
            igdb_data = search_igdb_game_by_id(suggestions[0]['id'])
            if igdb_data:
                data['downloads'][game_id]['bannerUrl'] = igdb_data['banner_url']
                data['downloads'][game_id]['title'] = igdb_data['name']
                data['downloads'][game_id]['igdbId'] = suggestions[0]['id']
                save_games(data)
    
    return redirect(url_for('index'))

@app.route('/api/search_games')
def api_search_games():
    """API pour la recherche de jeux IGDB"""
    query = request.args.get('q', '')
    if len(query) < 2:
        return jsonify([])
    
    suggestions = search_igdb_games(query, limit=10)
    return jsonify(suggestions)

if __name__ == '__main__':
    get_igdb_access_token()
    app.run(debug=True, host='0.0.0.0', port=5000)