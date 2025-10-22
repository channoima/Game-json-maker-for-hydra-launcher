from flask import Flask, render_template, request, redirect, url_for, flash, session
import json
import os
import requests
from datetime import datetime

app = Flask(__name__)
FICHIER_JSON = "jeux.json"

app.secret_key = "HydraJSONGameManager"

def charger_donnees():
    if os.path.exists(FICHIER_JSON):
        with open(FICHIER_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"name": "Ma bibliothèque de jeux", "downloads": []}

def sauvegarder_donnees(donnees):
    with open(FICHIER_JSON, "w", encoding="utf-8") as f:
        json.dump(donnees, f, indent=4, ensure_ascii=False)

def lien_valide(url):
    try:
        response = requests.head(url, timeout=3)
        return response.status_code == 200
    except Exception:
        return False
    
@app.route('/')
def index():
    data = charger_donnees()
    recherche = request.args.get('q', '').lower()
    jeux = data["downloads"]

    if recherche:
        jeux = [jeu for jeu in jeux if recherche in jeu["title"].lower()]

    verifications = session.pop('verifications', {})

    return render_template("index.html", jeux=jeux, source_name=data["name"], recherche=recherche, verifications=verifications)

@app.route('/ajouter', methods=['GET', 'POST'])
def ajouter():
    if request.method == 'POST':
        nouveau_jeu = {
            "title": request.form['title'],
            "uris": [request.form['lien']],
            "uploadDate": datetime.now().strftime("%Y-%m-%d"),
            "fileSize": request.form['taille']
        }
        data = charger_donnees()
        data["downloads"].append(nouveau_jeu)
        sauvegarder_donnees(data)
        return redirect(url_for('index'))
    return render_template("ajouter.html")

@app.route('/modifier_nom', methods=['POST'])
def modifier_nom():
    nouveau_nom = request.form['nouveau_nom']
    data = charger_donnees()
    data["name"] = nouveau_nom
    sauvegarder_donnees(data)
    return redirect(url_for('index'))

@app.route('/modifier/<int:index>', methods=['GET', 'POST'])
def modifier(index):
    data = charger_donnees()

    if index < 0 or index >= len(data["downloads"]):
        return "Jeu introuvable", 404

    jeu = data["downloads"][index]

    if request.method == 'POST':
        jeu["title"] = request.form['title']
        jeu["uris"] = [request.form['lien']]
        jeu["fileSize"] = request.form['taille']
        jeu["image_url"] = request.form.get('image_url', '')
        sauvegarder_donnees(data)
        return redirect(url_for('index'))

    return render_template("modifier.html", jeu=jeu, index=index)

@app.route('/supprimer/<int:index>', methods=['POST'])
def supprimer(index):
    data = charger_donnees()
    if 0 <= index < len(data["downloads"]):
        del data["downloads"][index]
        sauvegarder_donnees(data)
    return redirect(url_for('index'))

@app.route('/verifier/<int:index>', methods=['POST'])
def verifier(index):
    data = charger_donnees()

    if 0 <= index < len(data["downloads"]):
        jeu = data["downloads"][index]
        url = jeu["uris"][0]

        try:
            import requests
            r = requests.head(url, timeout=5)
            est_valide = r.status_code == 200
        except Exception:
            est_valide = False

        session['verifications'] = session.get('verifications', {})
        session['verifications'][str(index)] = "ok" if est_valide else "hs"

    recherche = request.form.get('q', '')

    return redirect(url_for('index', q=recherche))

if __name__ == '__main__':
    app.run(debug=True)
