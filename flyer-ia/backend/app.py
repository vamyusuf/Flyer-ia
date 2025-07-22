from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import openai 
import requests
import replicate
from replicate.exceptions import ReplicateError
from replicate.helpers import FileOutput
# PIL n'est plus nécessaire pour le dessin de texte si Imagen fait tout,
# mais on le garde pour ouvrir et sauvegarder l'image générée.
from PIL import Image 
import io
import base64
import os
import uuid
from dotenv import load_dotenv
import traceback

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# --- CONFIGURATION ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

if not OPENAI_API_KEY:
    raise ValueError("ERREUR: La variable d'environnement OPENAI_API_KEY n'est pas définie.")
if not REPLICATE_API_TOKEN:
    raise ValueError("ERREUR: La variable d'environnement REPLICATE_API_TOKEN n'est pas définie.")

os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
print("✅ Replicate/Imagen configuré")

UPLOAD_FOLDER = 'generated_flyers'
# FONT_FOLDER n'est plus nécessaire car Pillow ne dessinera plus le texte
# if not os.path.exists(FONT_FOLDER): print(f"⚠️ ATTENTION: Le dossier des polices '{FONT_FOLDER}' est manquant.")
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


# --- CLASSE DE GÉNÉRATION (Version 100% IA pour l'image et le texte) ---
class FlyerGenerator:
    def __init__(self, api_key):
        self.client = openai.OpenAI(api_key=api_key)
        # self.fonts = self._load_fonts() # Plus besoin de charger les polices

    # Plus besoin de _load_fonts() ni _draw_text_wrapped()

    def describe_image_style(self, style_image_bytes):
        print("   [Étape 1/2] Analyse du style de l'image par GPT-4o...")
        img_base64 = base64.b64encode(style_image_bytes).decode('utf-8')
        prompt = """
        The visual style is elegant and contemplative, blending refined Islamic architectural elements with celestial symbolism to evoke a serene yet festive nocturnal atmosphere. The composition is airy and balanced, featuring softly illuminated domes and slender minarets silhouetted against a twilight gradient sky. A stylized crescent moon, delicate and luminous, serves as a central visual anchor, subtly radiating a sense of spiritual elevation. The color palette is dominated by warm, muted tones—amber golds, deep indigos, and soft terracotta—layered with gentle highlights of pearl and ivory to create depth and sophistication. Ornamental patterns are used sparingly and with finesse, ensuring the overall aesthetic remains modern, dignified, and imbued with quiet reverence. This background sets the perfect tone for a prestigious evening celebration steeped in cultural richness and celestial harmony.
"""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user","content": [{"type": "text", "text": prompt},{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}]}],
                max_tokens=300
            )
            description = response.choices[0].message.content
            print(f"   🤖 Description générée par GPT-4o : {description}")
            return description
        except Exception as e:
            print(f"❌ Erreur lors de la description de l'image par GPT-4o : {e}")
            raise

    def generate_full_flyer_with_all_text(self, style_description, content_data):
        print("   [Étape 2/2] Génération de l'image complète du flyer avec TOUT le texte via Imagen 4 (Replicate)...")
        
        headline = content_data.get('headline1', '')
        description = content_data.get('short_description', '')
        event_info = content_data.get('event_info', '')
        footer_info = content_data.get('footer_info', '')

        # Prompt pour Imagen 4: Inclure TOUS les champs de texte
        imagen_prompt = f"""Create a professional vertical flyer in a 9:16 aspect ratio.

Style and atmosphere: {style_description}

🔒 IMPORTANT INSTRUCTIONS:

Do not add any extra symbols, logos, decorative characters, or placeholder text.

Do not generate any text outside of the provided input.

The flyer must include ONLY the following text, perfectly integrated and well-structured, with **absolute fidelity to spelling and grammar**:

 {headline}
 {description}
 {event_info}
 {footer_info}

🧩 Design Requirements:

Ensure all text is clearly legible and **free of any spelling or grammatical errors**.

Layout should be clean, elegant, and professional.

Text should be visually well-positioned with a clear hierarchy (title, body, details, footer).

Integrate text directly into the image with seamless alignment to the design.

❌ Absolutely no extra or unintended text, symbols, or unreadable artifacts in the image."""
        print(f"   🚀 Envoi du prompt complet à Imagen 4: '{imagen_prompt[:200]}...'")
        
        try:
            output = replicate.run(
                "google/imagen-4", # Le modèle Imagen 4 sur Replicate
                input={
                    "prompt": imagen_prompt,
                    "aspect_ratio": "9:16", # Garder le format vertical
                    "output_format": "jpg",
                    "safety_filter_level": "block_medium_and_above",
                    # AJOUT DE NEGATIVE PROMPTS SPÉCIFIQUES POUR LE TEXTE
                    "negative_prompt": "unreadable text, garbled text, misspelled text, incorrect text, text errors, extra text, overlapping text, poorly positioned text, blurry text, low quality text, bad typography, distorted text" 
                }
            )
            
            image_url = None
            if not output: raise Exception("Replicate (Imagen 4) returned an empty response.")
            if isinstance(output, list): 
                image_url = output[0] if output else None
            elif isinstance(output, (str, FileOutput)): 
                image_url = str(output) # Pour FileOutput ou URL directe
            
            if not image_url: raise Exception("Could not extract URL from Imagen 4 response.")
            
            print(f"   ✅ Flyer complet généré par Imagen 4 ! URL: {image_url}")
            return image_url
        except ReplicateError as re:
            print(f"   ❌ Erreur Replicate (Imagen 4): {re}")
            raise
        except Exception as e:
            print(f"   ❌ Erreur inattendue lors de la génération avec Imagen 4: {e}")
            raise

# Initialiser le générateur
flyer_gen = FlyerGenerator(api_key=OPENAI_API_KEY)

# --- ROUTES FLASK ---
@app.route('/api/generate-flyer-from-prototype', methods=['POST'])
def generate_flyer_from_prototype():
    try:
        print("\n🚀 Nouvelle requête de génération de flyer reçue (mode 100% IA texte/image) !")
        if 'image' not in request.files: return jsonify({'error': 'Aucun fichier image fourni.'}), 400

        style_image_file = request.files['image']
        style_image_bytes = style_image_file.read()

        content_data = {
            'headline1': request.form.get('headline1', ''),
            'short_description': request.form.get('short_description', ''),
            'event_info': request.form.get('event_info', ''),
            'footer_info': request.form.get('footer_info', '')
        }
        print(f"   📝 Données textuelles à intégrer : {content_data}")

        # Étape 1: Décrire le style avec GPT-4o
        style_description = flyer_gen.describe_image_style(style_image_bytes)

        # Étape 2: Générer le flyer complet avec tout le texte via Imagen 4 (Replicate)
        final_flyer_image_url = flyer_gen.generate_full_flyer_with_all_text(style_description, content_data)
        
        # Télécharger l'image finale générée par Imagen 4
        print(f"   📥 Téléchargement du flyer final depuis : {final_flyer_image_url}")
        response = requests.get(final_flyer_image_url)
        response.raise_for_status()
        final_flyer_image_bytes = io.BytesIO(response.content)
        final_flyer_image = Image.open(final_flyer_image_bytes).convert("RGB") # Convertir en RGB pour la sauvegarde JPG/PNG

        # Sauvegarder l'image finale sur notre serveur
        filename = f"flyer_{uuid.uuid4()}.png" # On sauve en PNG pour la qualité
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        final_flyer_image.save(filepath, 'PNG', quality=95)
        
        # Retourner l'URL de notre serveur
        server_url = request.host_url.rstrip('/')
        flyer_url = f"{server_url}/flyers/{filename}"
        print(f"✅ Processus de génération 100% IA terminé avec succès ! Flyer final : {flyer_url}")
        
        return jsonify({
            'success': True,
            'flyer_urls': [flyer_url],
            'message': 'Flyer généré avec succès avec tout le texte intégré par l\'IA.'
        })

    except Exception as e:
        print(f"❌ ERREUR FATALE dans la route principale : {e}")
        traceback.print_exc()
        return jsonify({'error': f"Une erreur interne est survenue : {str(e)}"}), 500

@app.route('/flyers/<filename>')
def serve_flyer(filename):
    return send_file(os.path.join(UPLOAD_FOLDER, filename), mimetype='image/png')

if __name__ == '__main__':
    print("🚀 Démarrage du serveur Flask (mode 100% IA texte/image avec Imagen 4)...")
    app.run(debug=True, port=5000)








# from flask import Flask, request, jsonify, send_file
# from flask_cors import CORS
# import openai 
# import requests
# import replicate
# from replicate.exceptions import ReplicateError
# from replicate.helpers import FileOutput
# # PIL n'est plus nécessaire pour le dessin de texte si Imagen fait tout,
# # mais on le garde pour ouvrir et sauvegarder l'image générée.
# from PIL import Image 
# import io
# import base64
# import os
# import uuid
# from dotenv import load_dotenv
# import traceback

# load_dotenv()

# app = Flask(__name__)
# CORS(app, resources={r"/api/*": {"origins": "*"}})

# # --- CONFIGURATION ---
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

# if not OPENAI_API_KEY:
#     raise ValueError("ERREUR: La variable d'environnement OPENAI_API_KEY n'est pas définie.")
# if not REPLICATE_API_TOKEN:
#     raise ValueError("ERREUR: La variable d'environnement REPLICATE_API_TOKEN n'est pas définie.")

# os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
# print("✅ Replicate/Imagen configuré")

# UPLOAD_FOLDER = 'generated_flyers'
# # FONT_FOLDER n'est plus nécessaire car Pillow ne dessinera plus le texte
# # if not os.path.exists(FONT_FOLDER): print(f"⚠️ ATTENTION: Le dossier des polices '{FONT_FOLDER}' est manquant.")
# if not os.path.exists(UPLOAD_FOLDER):
#     os.makedirs(UPLOAD_FOLDER)


# # --- CLASSE DE GÉNÉRATION (Version 100% IA pour l'image et le texte) ---
# class FlyerGenerator:
#     def __init__(self, api_key):
#         self.client = openai.OpenAI(api_key=api_key)
#         # self.fonts = self._load_fonts() # Plus besoin de charger les polices

#     # Plus besoin de _load_fonts() ni _draw_text_wrapped()

#     def describe_image_style(self, style_image_bytes):
#         print("   [Étape 1/2] Analyse du style de l'image par GPT-4o...")
#         img_base64 = base64.b64encode(style_image_bytes).decode('utf-8')
#         prompt = """
#         En tant que directeur artistique expert en design graphique, analysez l'image fournie.
#         Votre tâche est de générer une description concise et professionnelle du style visuel,
#         de l'ambiance générale, de la palette de couleurs dominante et des éléments graphiques clés
#         qui définissent son esthétique. Cette description servira de base pour générer une image de fond.
#         Concentrez-vous STRICTEMENT sur l'aspect visuel.
#         NE MENTIONNEZ AUCUN TEXTE, LOGO OU SYMBOLE QUI POURRAIT ÊTRE PRÉSENT DANS L'IMAGE.
#         Votre réponse doit être un paragraphe unique, détaillé et évocateur, d'une qualité comparable à celle d'un brief pour un graphiste.
#         """
#         try:
#             response = self.client.chat.completions.create(
#                 model="gpt-4o",
#                 messages=[{"role": "user","content": [{"type": "text", "text": prompt},{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}]}],
#                 max_tokens=300
#             )
#             description = response.choices[0].message.content
#             print(f"   🤖 Description générée par GPT-4o : {description}")
#             return description
#         except Exception as e:
#             print(f"❌ Erreur lors de la description de l'image par GPT-4o : {e}")
#             raise

#     def generate_full_flyer_with_all_text(self, style_description, content_data):
#         print("   [Étape 2/2] Génération de l'image complète du flyer avec TOUT le texte via Imagen 4 (Replicate)...")
        
#         headline = content_data.get('headline1', '')
#         description = content_data.get('short_description', '')
#         event_info = content_data.get('event_info', '')
#         footer_info = content_data.get('footer_info', '')

#         # Prompt pour Imagen 4: Inclure TOUS les champs de texte
#         imagen_prompt = f"""Create a professional vertical flyer in a 9:16 aspect ratio.

# Style and atmosphere: {style_description}

# 🔒 IMPORTANT INSTRUCTIONS:

# Do not add any extra symbols, logos, decorative characters, or placeholder text.

# Do not generate any text outside of the provided input.

# The flyer must include ONLY the following text, perfectly integrated and well-structured:

# MAIN TITLE: {headline}
# DESCRIPTION: {description}
# EVENT DETAILS: {event_info}
# FOOTER INFO: {footer_info}

# 🧩 Design Requirements:

# Ensure all text is clearly legible and free of spelling errors.

# Layout should be clean, elegant, and professional.

# Text should be visually well-positioned with a clear hierarchy (title, body, details, footer).

# Integrate text directly into the image with seamless alignment to the design.

# ❌ Absolutely no extra or unintended text, symbols, or unreadable artifacts in the image.
#         """
#         print(f"   🚀 Envoi du prompt complet à Imagen 4: '{imagen_prompt[:200]}...'")
        
#         try:
#             output = replicate.run(
#                 "google/imagen-4", # Le modèle Imagen 4 sur Replicate
#                 input={
#                     "prompt": imagen_prompt,
#                     "aspect_ratio": "9:16", # Garder le format vertical
#                     "output_format": "jpg",
#                     "safety_filter_level": "block_medium_and_above",
#                     # AJOUT DE NEGATIVE PROMPTS SPÉCIFIQUES POUR LE TEXTE
#                     "negative_prompt": "unreadable text, garbled text, misspelled text, incorrect text, text errors, extra text, overlapping text, poorly positioned text, blurry text, low quality text, bad typography, distorted text" 
#                 }
#             )
            
#             image_url = None
#             if not output: raise Exception("Replicate (Imagen 4) returned an empty response.")
#             if isinstance(output, list): 
#                 image_url = output[0] if output else None
#             elif isinstance(output, (str, FileOutput)): 
#                 image_url = str(output) # Pour FileOutput ou URL directe
            
#             if not image_url: raise Exception("Could not extract URL from Imagen 4 response.")
            
#             print(f"   ✅ Flyer complet généré par Imagen 4 ! URL: {image_url}")
#             return image_url
#         except ReplicateError as re:
#             print(f"   ❌ Erreur Replicate (Imagen 4): {re}")
#             raise
#         except Exception as e:
#             print(f"   ❌ Erreur inattendue lors de la génération avec Imagen 4: {e}")
#             raise

# # Initialiser le générateur
# flyer_gen = FlyerGenerator(api_key=OPENAI_API_KEY)

# # --- ROUTES FLASK ---
# @app.route('/api/generate-flyer-from-prototype', methods=['POST'])
# def generate_flyer_from_prototype():
#     try:
#         print("\n🚀 Nouvelle requête de génération de flyer reçue (mode 100% IA texte/image) !")
#         if 'image' not in request.files: return jsonify({'error': 'Aucun fichier image fourni.'}), 400

#         style_image_file = request.files['image']
#         style_image_bytes = style_image_file.read()

#         content_data = {
#             'headline1': request.form.get('headline1', ''),
#             'short_description': request.form.get('short_description', ''),
#             'event_info': request.form.get('event_info', ''),
#             'footer_info': request.form.get('footer_info', '')
#         }
#         print(f"   📝 Données textuelles à intégrer : {content_data}")

#         # Étape 1: Décrire le style avec GPT-4o
#         style_description = flyer_gen.describe_image_style(style_image_bytes)

#         # Étape 2: Générer le flyer complet avec tout le texte via Imagen 4 (Replicate)
#         final_flyer_image_url = flyer_gen.generate_full_flyer_with_all_text(style_description, content_data)
        
#         # Télécharger l'image finale générée par Imagen 4
#         print(f"   📥 Téléchargement du flyer final depuis : {final_flyer_image_url}")
#         response = requests.get(final_flyer_image_url)
#         response.raise_for_status()
#         final_flyer_image_bytes = io.BytesIO(response.content)
#         final_flyer_image = Image.open(final_flyer_image_bytes).convert("RGB") # Convertir en RGB pour la sauvegarde JPG/PNG

#         # Sauvegarder l'image finale sur notre serveur
#         filename = f"flyer_{uuid.uuid4()}.png" # On sauve en PNG pour la qualité
#         filepath = os.path.join(UPLOAD_FOLDER, filename)
#         final_flyer_image.save(filepath, 'PNG', quality=95)
        
#         # Retourner l'URL de notre serveur
#         server_url = request.host_url.rstrip('/')
#         flyer_url = f"{server_url}/flyers/{filename}"
#         print(f"✅ Processus de génération 100% IA terminé avec succès ! Flyer final : {flyer_url}")
        
#         return jsonify({
#             'success': True,
#             'flyer_urls': [flyer_url],
#             'message': 'Flyer généré avec succès avec tout le texte intégré par l\'IA.'
#         })

#     except Exception as e:
#         print(f"❌ ERREUR FATALE dans la route principale : {e}")
#         traceback.print_exc()
#         return jsonify({'error': f"Une erreur interne est survenue : {str(e)}"}), 500

# @app.route('/flyers/<filename>')
# def serve_flyer(filename):
#     return send_file(os.path.join(UPLOAD_FOLDER, filename), mimetype='image/png')

# if __name__ == '__main__':
#     print("🚀 Démarrage du serveur Flask (mode 100% IA texte/image avec Imagen 4)...")
#     app.run(debug=True, port=5000)























# import os
# import uuid
# import io
# import base64
# from flask import Flask, request, jsonify, send_from_directory
# from flask_cors import CORS
# from dotenv import load_dotenv

# # --- Importations pour Google Cloud Vertex AI (Imagen) ---
# # Assurez-vous d'avoir installé : pip install google-cloud-aiplatform vertexai
# from google.cloud import aiplatform
# from vertexai.preview.vision_models import ImageGenerationModel 
# from vertexai.generative_models import GenerationConfig as VertexAIGenerationConfig 
# from google.api_core.exceptions import GoogleAPIError

# from openai import OpenAI
# from PIL import Image
# import requests 


# # --- CONFIGURATION INITIALE ---
# load_dotenv()
# # Votre clé GOOGLE_API_KEY (pour les modèles Gemini publics) n'est PAS utilisée pour Imagen sur Vertex AI.
# # Votre clé OPENAI_API_KEY est utilisée pour GPT-4.
# OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# # --- CONFIGURATION SPECIFIQUE A GOOGLE CLOUD VERTEX AI (IMAGEN) ---
# # >>>>>> VOUS DEVEZ DEFINIR CES VARIABLES DANS VOTRE FICHIER .env <<<<<<
# # Project ID de votre projet Google Cloud (Ex: 'my-awesome-project-12345')
# GCP_PROJECT_ID = os.getenv('GCP_PROJECT_ID') 
# # Région où vous souhaitez utiliser Imagen (Ex: 'us-central1', 'europe-west4')
# GCP_LOCATION = os.getenv('GCP_LOCATION')

# if not OPENAI_API_KEY:
#     raise ValueError("La clé API OpenAI doit être définie dans le fichier .env")

# # Vérification OBLIGATOIRE pour Imagen via Vertex AI
# if not GCP_PROJECT_ID or not GCP_LOCATION:
#     raise ValueError(
#         "\nERREUR : Pour utiliser Imagen via Google Cloud Vertex AI, vous DEVEZ définir "
#         "GCP_PROJECT_ID et GCP_LOCATION dans votre fichier .env. "
#         "Votre clé 'f639...' n'est PAS compatible avec cette intégration directe."
#         "\nVeuillez vous référer à la documentation Google Cloud pour configurer Vertex AI correctement."
#     )

# # --- CORRECTION DE L'ERREUR SSL (MÉTHODE FORTE) ---
# if "SSL_CERT_FILE" in os.environ:
#     print("AVERTISSEMENT : Variable d'environnement SSL_CERT_FILE détectée. Suppression temporaire pour éviter l'erreur.")
#     del os.environ["SSL_CERT_FILE"]

# # On initialise le client OpenAI de manière standard.
# openai_client = OpenAI(api_key=OPENAI_API_KEY)

# # --- Initialisation de Vertex AI et du modèle Imagen ---
# # Cette étape nécessite une authentification Google Cloud valide (gcloud auth application-default login ou compte de service)
# # et que les variables GCP_PROJECT_ID et GCP_LOCATION soient correctement définies dans votre .env.
# try:
#     aiplatform.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)
#     # CHANGEMENT ICI : Utilisation du modèle Imagen 2.0 (imagegeneration@002)
#     # Note : Le nom 'imagen-3.0-generate-002' que vous avez mentionné pourrait être une référence interne.
#     # 'imagegeneration@002' est le nom couramment utilisé pour Imagen 2.0 via la bibliothèque Vertex AI.
#     imagen_model = ImageGenerationModel.from_pretrained("imagegeneration@002") 
#     print(f"Modèle Imagen '{imagen_model.model_name}' (Imagen 2.0) initialisé avec succès pour le projet {GCP_PROJECT_ID} dans la région {GCP_LOCATION}.")
# except Exception as e:
#     print(f"\n--- ERREUR CRITIQUE LORS DE L'INITIALISATION D'IMAGEN ---")
#     print(f"Détails de l'erreur : {e}")
#     print("Cause probable : L'accès à Imagen via Vertex AI nécessite une configuration Google Cloud Platform (GCP) complète.")
#     print("1. Assurez-vous que GCP_PROJECT_ID et GCP_LOCATION sont correctement définis dans votre .env.")
#     print("2. Vérifiez que la facturation est activée pour votre projet GCP.")
#     print("3. Assurez-vous que l'API 'Vertex AI API' est activée dans votre projet GCP.")
#     print("4. Configurez votre authentification Google Cloud :")
#     print("   - Pour le développement local : Exécutez `gcloud auth application-default login` dans votre terminal.")
#     print("   - Pour un déploiement : Utilisez un compte de service et la variable GOOGLE_APPLICATION_CREDENTIALS.")
#     print("Votre clé API 'f639...' n'est PAS utilisée pour cette intégration.")
#     print("---------------------------------------------------------")
#     raise # Relancer l'exception car sans Imagen, l'app ne peut pas fonctionner comme prévu.


# app = Flask(__name__)
# CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}})

# OUTPUT_DIR = os.path.join('static', 'generated_flyers')
# os.makedirs(OUTPUT_DIR, exist_ok=True)

# # --- ROUTE PRINCIPALE ---
# @app.route('/api/generate-flyer-from-prototype', methods=['POST'])
# def generate_flyer():
#     try:
#         if 'image' not in request.files:
#             return jsonify({'error': "Aucun fichier image n'a été fourni."}), 400

#         style_image_file = request.files['image']
#         headline = request.form.get('headline1', '')
#         description = request.form.get('short_description', '')
#         event_info = request.form.get('event_info', '')
#         footer_info = request.form.get('footer_info', '')
        
#         # --- 1. ANALYSE DE L'IMAGE AVEC GPT-4 ---
#         print("Étape 1 : Analyse de l'image de style avec GPT-4...")
#         image_bytes = style_image_file.read()
#         base64_image = base64.b64encode(image_bytes).decode('utf-8')
#         gpt4_prompt = "Tu es un directeur artistique. Décris cette image en utilisant des mots-clés très précis et évocateurs pour un générateur d'images. Concentre-toi sur le style, la palette de couleurs, la texture et l'ambiance générale. Ta réponse doit être une seule phrase percutante."
#         gpt4_response = openai_client.chat.completions.create(
#             model="gpt-4o",
#             messages=[{"role": "user","content": [{"type": "text", "text": gpt4_prompt},{"type": "image_url","image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},},],}],
#             max_tokens=100,
#         )
#         style_description = gpt4_response.choices[0].message.content
#         print(f"Description générée par GPT-4 : '{style_description}'")

#         # --- 2. GÉNÉRATION DE L'IMAGE FINALE AVEC IMAGEN 2.0 (imagegeneration@002) ---
#         print("Étape 2 : Génération de l'image finale avec Imagen 2.0 (imagegeneration@002)...")
        
#         # Concaténer toutes les informations dans un prompt pour Imagen
#         imagen_prompt = f"""
#         Crée un flyer promotionnel visuellement percutant et professionnel.
#         Le flyer doit avoir un format vertical (ratio 9:16).

#         **Style et Ambiance (inspiré par l'image fournie) :** {style_description}

#         **Contenu Texte à Intégrer (doit être lisible, esthétique et bien hiérarchisé sur le flyer) :**
#         - Titre Principal : "{headline}"
#         - Brève description : "{description}"
#         - Informations clés de l'événement/produit : "{event_info}"
#         - Coordonnées / informations de pied de page : "{footer_info}"

#         Assure-toi que le texte est bien fusionné avec l'image, sans chevauchement illisible.
#         Le style doit être moderne et accrocheur.
#         """
        
#         # Paramètres pour la génération d'images avec Imagen
#         # Les paramètres peuvent varier selon la version exacte d'Imagen.
#         # 'aspect_ratio' est généralement supporté. 'art_style' peut être utile.
#         imagen_params = VertexAIGenerationConfig(
#             number_of_images=1,
#             # seed=42, # Optionnel: pour la reproductibilité
#             # art_style="photographic", # Optionnel: peut aider à guider le style
#             aspect_ratio="9:16" # Spécifie un format vertical pour le flyer
#         )

#         imagen_response = imagen_model.generate_images(
#             prompt=imagen_prompt,
#             generation_config=imagen_params 
#         )

#         generated_image_data = None
#         if imagen_response.images and len(imagen_response.images) > 0:
#             # Imagen peut retourner l'image directement en base64_data ou via une URL temporaire.
#             # On vérifie d'abord base64_data car c'est plus direct.
#             if imagen_response.images[0].base64_data:
#                 generated_image_data = base64.b64decode(imagen_response.images[0].base64_data)
#             elif imagen_response.images[0].url:
#                 print(f"Téléchargement de l'image Imagen depuis : {imagen_response.images[0].url}")
#                 image_http_response = requests.get(imagen_response.images[0].url)
#                 image_http_response.raise_for_status() # Lève une erreur si le téléchargement échoue
#                 generated_image_data = image_http_response.content
        
#         if not generated_image_data:
#             # Gestion des erreurs plus détaillée d'Imagen
#             error_details = []
#             if hasattr(imagen_response, 'error') and imagen_response.error:
#                 error_details.append(f"API Error: {imagen_response.error.message} (Code: {imagen_response.error.code})")
#             if not imagen_response.images:
#                 error_details.append("Aucune image n'a été retournée par Imagen.")
            
#             raise ValueError(f"Imagen n'a pas généré de données d'image valides. " + " ".join(error_details))

#         final_image = Image.open(io.BytesIO(generated_image_data))

#         # --- 3. SAUVEGARDE ET ENVOI DE LA RÉPONSE ---
#         print("Étape 3 : Sauvegarde de l'image finale...")
#         final_filename = f"{uuid.uuid4()}.png"
#         final_filepath = os.path.join(OUTPUT_DIR, final_filename)
#         final_image.save(final_filepath, 'PNG')
        
#         server_url = request.host_url.rstrip('/')
#         flyer_url = f"{server_url}/static/generated_flyers/{final_filename}"
        
#         return jsonify({'flyer_urls': [flyer_url]}), 200

#     except GoogleAPIError as e:
#         # Erreurs spécifiques à l'API Google Cloud (authentification, permissions, quota, etc.)
#         print(f"ERREUR API GOOGLE CLOUD : {e.message} (Code: {e.code})")
#         return jsonify({'error': f"Erreur d'API Google Cloud : {e.message} (Code: {e.code}). Vérifiez votre configuration GCP et vos quotas."}), 500
#     except Exception as e:
#         # Toute autre erreur inattendue
#         print(f"Une erreur inattendue est survenue : {e}")
#         return jsonify({'error': str(e)}), 500

# @app.route('/static/generated_flyers/<filename>')
# def serve_flyer(filename):
#     return send_from_directory(OUTPUT_DIR, filename)

# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5000, debug=True)