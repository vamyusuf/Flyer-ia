from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import openai 
import requests
import replicate
from replicate.exceptions import ReplicateError
from replicate.helpers import FileOutput
from PIL import Image 
import io
import base64
import os
import uuid
from dotenv import load_dotenv
import traceback
import sys

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# --- CONFIGURATION AVEC DIAGNOSTICS ---
print("🔍 Vérification des variables d'environnement...")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

print(f"OPENAI_API_KEY: {'✅ Définie' if OPENAI_API_KEY else '❌ Manquante'}")
print(f"REPLICATE_API_TOKEN: {'✅ Définie' if REPLICATE_API_TOKEN else '❌ Manquante'}")

if not OPENAI_API_KEY:
    print("❌ ERREUR CRITIQUE: OPENAI_API_KEY manquante")
    print("💡 Créez un fichier .env avec: OPENAI_API_KEY=votre_cle")
    sys.exit(1)

if not REPLICATE_API_TOKEN:
    print("❌ ERREUR CRITIQUE: REPLICATE_API_TOKEN manquante")
    print("💡 Créez un fichier .env avec: REPLICATE_API_TOKEN=votre_token")
    sys.exit(1)

# Test de connexion aux APIs
print("🔍 Test des connexions API...")

try:
    # Test OpenAI
    test_client = openai.OpenAI(api_key=OPENAI_API_KEY)
    print("✅ OpenAI: Connexion OK")
except Exception as e:
    print(f"❌ OpenAI: Erreur de connexion: {e}")

try:
    # Test Replicate
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
    print("✅ Replicate: Token configuré")
except Exception as e:
    print(f"❌ Replicate: Erreur de configuration: {e}")

UPLOAD_FOLDER = 'generated_flyers'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    print(f"✅ Dossier créé: {UPLOAD_FOLDER}")
else:
    print(f"✅ Dossier existant: {UPLOAD_FOLDER}")

class FlyerGenerator:
    def __init__(self, api_key):
        try:
            self.client = openai.OpenAI(api_key=api_key)
            print("✅ FlyerGenerator initialisé")
        except Exception as e:
            print(f"❌ Erreur initialisation FlyerGenerator: {e}")
            raise

    def describe_image_style(self, style_image_bytes):
        print("🔍 [Étape 1/2] Début analyse de l'image...")
        
        try:
            print(f"   📏 Taille de l'image: {len(style_image_bytes)} bytes")
            
            # Vérifier que l'image est valide
            test_image = Image.open(io.BytesIO(style_image_bytes))
            print(f"   ✅ Image valide: {test_image.size}, format: {test_image.format}")
            
            img_base64 = base64.b64encode(style_image_bytes).decode('utf-8')
            print(f"   ✅ Image encodée en base64: {len(img_base64)} caractères")
            
            prompt = """
            Analyze this image and describe its visual style in detail. Focus on:
            - Color palette and lighting
            - Architectural or design elements
            - Overall mood and atmosphere
            - Typography style (if any text is visible)
            - Layout and composition
            
            Provide a detailed description that could be used to recreate a similar visual style.
            """
            
            print("   🤖 Envoi à GPT-4o...")
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
                    ]
                }],
                max_tokens=300
            )
            
            description = response.choices[0].message.content
            print(f"   ✅ Description reçue: {len(description)} caractères")
            print(f"   📝 Aperçu: {description[:100]}...")
            return description
            
        except Exception as e:
            print(f"   ❌ Erreur dans describe_image_style: {e}")
            print(f"   📋 Traceback: {traceback.format_exc()}")
            raise

    def generate_full_flyer_with_all_text(self, style_description, content_data):
        print("🔍 [Étape 2/2] Début génération avec Imagen...")
        
        try:
            headline = content_data.get('headline1', '')
            description = content_data.get('short_description', '')
            event_info = content_data.get('event_info', '')
            footer_info = content_data.get('footer_info', '')

            print(f"   📝 Contenu à intégrer:")
            print(f"      - Titre: {headline[:50]}...")
            print(f"      - Description: {description[:50]}...")
            print(f"      - Événement: {event_info[:50]}...")
            print(f"      - Footer: {footer_info[:50]}...")

            imagen_prompt = f"""Create a professional vertical flyer in a 9:16 aspect ratio.

Style and atmosphere: {style_description}

The flyer must include ONLY the following text, perfectly integrated:

Title: {headline}
Description: {description}
Event details: {event_info}
Contact: {footer_info}

Requirements:
- Clean, elegant, professional layout
- Clear text hierarchy
- Legible typography
- No extra text or symbols"""

            print(f"   📏 Longueur du prompt: {len(imagen_prompt)} caractères")
            print("   🚀 Envoi à Imagen 4...")
            
            output = replicate.run(
                "google/imagen-4",
                input={
                    "prompt": imagen_prompt,
                    "aspect_ratio": "9:16",
                    "output_format": "jpg",
                    "safety_filter_level": "block_medium_and_above",
                    "negative_prompt": "unreadable text, garbled text, blurry text, bad typography"
                }
            )
            
            print(f"   📨 Type de réponse Imagen: {type(output)}")
            print(f"   📋 Contenu réponse: {str(output)[:200]}...")
            
            image_url = None
            if not output: 
                raise Exception("Replicate returned empty response")
            
            if isinstance(output, list): 
                image_url = output[0] if output else None
                print(f"   📋 URL extraite de liste: {image_url}")
            elif isinstance(output, (str, FileOutput)): 
                image_url = str(output)
                print(f"   📋 URL directe: {image_url}")
            
            if not image_url: 
                raise Exception(f"Could not extract URL. Output type: {type(output)}, content: {output}")
            
            print(f"   ✅ Image générée avec succès: {image_url}")
            return image_url
            
        except Exception as e:
            print(f"   ❌ Erreur dans generate_full_flyer_with_all_text: {e}")
            print(f"   📋 Traceback: {traceback.format_exc()}")
            raise

# Initialisation avec gestion d'erreur
try:
    flyer_gen = FlyerGenerator(api_key=OPENAI_API_KEY)
    print("✅ Générateur initialisé avec succès")
except Exception as e:
    print(f"❌ ERREUR CRITIQUE lors de l'initialisation: {e}")
    sys.exit(1)

# --- ROUTES FLASK AVEC DIAGNOSTICS COMPLETS ---
@app.route('/api/generate-flyer-from-prototype', methods=['POST'])
def generate_flyer_from_prototype():
    print("\n" + "="*80)
    print("🚀 NOUVELLE REQUÊTE DE GÉNÉRATION")
    print("="*80)
    
    try:
        # === PHASE 1: RÉCEPTION ET VALIDATION ===
        print("🔍 Phase 1: Validation des données reçues")
        
        # Diagnostics de la requête
        print(f"   📋 Méthode: {request.method}")
        print(f"   📋 Content-Type: {request.content_type}")
        print(f"   📋 Form keys: {list(request.form.keys())}")
        print(f"   📋 Files keys: {list(request.files.keys())}")
        
        if 'image' not in request.files: 
            error_msg = "Aucun fichier 'image' dans la requête"
            print(f"   ❌ {error_msg}")
            return jsonify({'error': error_msg}), 400

        style_image_file = request.files['image']
        print(f"   📁 Fichier reçu: {style_image_file.filename}")
        print(f"   📏 Content-Type: {style_image_file.content_type}")
        
        if style_image_file.filename == '':
            error_msg = "Nom de fichier vide"
            print(f"   ❌ {error_msg}")
            return jsonify({'error': error_msg}), 400
            
        style_image_bytes = style_image_file.read()
        print(f"   📏 Taille du fichier: {len(style_image_bytes)} bytes")
        
        if len(style_image_bytes) == 0:
            error_msg = "Fichier image vide"
            print(f"   ❌ {error_msg}")
            return jsonify({'error': error_msg}), 400

        # Test ouverture image
        try:
            test_img = Image.open(io.BytesIO(style_image_bytes))
            print(f"   ✅ Image valide: {test_img.size}, mode: {test_img.mode}")
        except Exception as e:
            error_msg = f"Image corrompue ou format invalide: {e}"
            print(f"   ❌ {error_msg}")
            return jsonify({'error': error_msg}), 400

        content_data = {
            'headline1': request.form.get('headline1', ''),
            'short_description': request.form.get('short_description', ''),
            'event_info': request.form.get('event_info', ''),
            'footer_info': request.form.get('footer_info', '')
        }
        print(f"   📝 Données textuelles reçues:")
        for key, value in content_data.items():
            print(f"      - {key}: {value[:50]}{'...' if len(value) > 50 else ''}")

        if not any(content_data.values()):
            error_msg = "Aucun contenu textuel fourni"
            print(f"   ❌ {error_msg}")
            return jsonify({'error': error_msg}), 400

        print("   ✅ Phase 1 terminée: Données valides")

        # === PHASE 2: ANALYSE DE L'IMAGE ===
        print("\n🔍 Phase 2: Analyse de l'image avec GPT-4o")
        try:
            style_description = flyer_gen.describe_image_style(style_image_bytes)
            print("   ✅ Phase 2 terminée: Image analysée")
        except Exception as e:
            error_msg = f'Erreur analyse GPT-4o: {str(e)}'
            print(f"   ❌ {error_msg}")
            return jsonify({'error': error_msg}), 500

        # === PHASE 3: GÉNÉRATION AVEC IMAGEN ===
        print("\n🔍 Phase 3: Génération avec Imagen 4")
        try:
            final_flyer_image_url = flyer_gen.generate_full_flyer_with_all_text(style_description, content_data)
            print("   ✅ Phase 3 terminée: Flyer généré")
        except Exception as e:
            error_msg = f'Erreur génération Imagen: {str(e)}'
            print(f"   ❌ {error_msg}")
            return jsonify({'error': error_msg}), 500
        
        # === PHASE 4: TÉLÉCHARGEMENT ET SAUVEGARDE ===
        print("\n🔍 Phase 4: Téléchargement et sauvegarde")
        try:
            print(f"   📥 Téléchargement depuis: {final_flyer_image_url}")
            response = requests.get(final_flyer_image_url, timeout=30)
            response.raise_for_status()
            print(f"   ✅ Téléchargement réussi: {len(response.content)} bytes")
            
            final_flyer_image_bytes = io.BytesIO(response.content)
            final_flyer_image = Image.open(final_flyer_image_bytes).convert("RGB")
            print(f"   ✅ Image ouverte: {final_flyer_image.size}")
        except Exception as e:
            error_msg = f'Erreur téléchargement: {str(e)}'
            print(f"   ❌ {error_msg}")
            return jsonify({'error': error_msg}), 500

        # Sauvegarde
        filename = f"flyer_{uuid.uuid4()}.png"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
        try:
            final_flyer_image.save(filepath, 'PNG', quality=95)
            print(f"   ✅ Sauvegarde réussie: {filepath}")
        except Exception as e:
            error_msg = f'Erreur sauvegarde: {str(e)}'
            print(f"   ❌ {error_msg}")
            return jsonify({'error': error_msg}), 500
        
        # === PHASE 5: RÉPONSE FINALE ===
        server_url = request.host_url.rstrip('/')
        flyer_url = f"{server_url}/flyers/{filename}"
        
        print(f"\n✅ SUCCÈS COMPLET!")
        print(f"   🎉 URL finale: {flyer_url}")
        print("="*80 + "\n")
        
        return jsonify({
            'success': True,
            'flyer_urls': [flyer_url],
            'message': 'Flyer généré avec succès!',
            'debug_info': {
                'filename': filename,
                'image_size': final_flyer_image.size,
                'file_size_bytes': len(response.content)
            }
        })

    except Exception as e:
        print(f"\n❌ ERREUR FATALE DANS LA ROUTE PRINCIPALE:")
        print(f"   🔥 Erreur: {e}")
        print(f"   📋 Type: {type(e).__name__}")
        print(f"   🗂️ Traceback complet:")
        traceback.print_exc()
        print("="*80 + "\n")
        
        return jsonify({
            'error': f"Erreur interne: {str(e)}",
            'error_type': type(e).__name__,
            'debug': True
        }), 500

@app.route('/flyers/<filename>')
def serve_flyer(filename):
    try:
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        print(f"📁 Demande de fichier: {filename}")
        print(f"   📍 Chemin: {filepath}")
        print(f"   ✅ Existe: {os.path.exists(filepath)}")
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'Fichier non trouvé'}), 404
            
        return send_file(filepath, mimetype='image/png')
    except Exception as e:
        print(f"❌ Erreur service fichier {filename}: {e}")
        return jsonify({'error': 'Erreur lors de la récupération du fichier'}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    try:
        # Test des composants
        health_status = {
            'status': 'OK',
            'timestamp': str(uuid.uuid4()),
            'components': {
                'openai': 'OK' if OPENAI_API_KEY else 'ERROR - No API key',
                'replicate': 'OK' if REPLICATE_API_TOKEN else 'ERROR - No token',
                'upload_folder': 'OK' if os.path.exists(UPLOAD_FOLDER) else 'ERROR - Missing folder'
            }
        }
        return jsonify(health_status)
    except Exception as e:
        return jsonify({'status': 'ERROR', 'error': str(e)}), 500

if __name__ == '__main__':
    print("\n🚀 DÉMARRAGE DU SERVEUR FLASK")
    print(f"📁 Dossier de sauvegarde: {os.path.abspath(UPLOAD_FOLDER)}")
    print(f"🌐 Serveur accessible sur: http://localhost:5000")
    print(f"🔧 Mode debug: Activé")
    print("="*80)
    
    app.run(debug=True, port=5000, host='0.0.0.0')





























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
#         The visual style is elegant and contemplative, blending refined Islamic architectural elements with celestial symbolism to evoke a serene yet festive nocturnal atmosphere. The composition is airy and balanced, featuring softly illuminated domes and slender minarets silhouetted against a twilight gradient sky. A stylized crescent moon, delicate and luminous, serves as a central visual anchor, subtly radiating a sense of spiritual elevation. The color palette is dominated by warm, muted tones—amber golds, deep indigos, and soft terracotta—layered with gentle highlights of pearl and ivory to create depth and sophistication. Ornamental patterns are used sparingly and with finesse, ensuring the overall aesthetic remains modern, dignified, and imbued with quiet reverence. This background sets the perfect tone for a prestigious evening celebration steeped in cultural richness and celestial harmony.
# """
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

# The flyer must include ONLY the following text, perfectly integrated and well-structured, with **absolute fidelity to spelling and grammar**:

#  {headline}
#  {description}
#  {event_info}
#  {footer_info}

# 🧩 Design Requirements:

# Ensure all text is clearly legible and **free of any spelling or grammatical errors**.

# Layout should be clean, elegant, and professional.

# Text should be visually well-positioned with a clear hierarchy (title, body, details, footer).

# Integrate text directly into the image with seamless alignment to the design.

# ❌ Absolutely no extra or unintended text, symbols, or unreadable artifacts in the image."""
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



