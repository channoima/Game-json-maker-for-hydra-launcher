from flask import Flask, render_template, request, jsonify, redirect, url_for
import json
import os
import requests
from datetime import datetime
from urllib.parse import urlparse

app = Flask(__name__)
DATA_FILE = 'games.json'

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
        new_game = {
            "title": title,
            "uris": [uri],
            "uploadDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "fileSize": file_size
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)