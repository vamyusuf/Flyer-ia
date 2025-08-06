# FLYER-IA/flyer-ia/backend/app.py

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import openai
import replicate
from replicate.exceptions import ReplicateError
from replicate.helpers import FileOutput
from PIL import Image, ImageDraw, ImageFont
import io # Garder pour io.BytesIO dans describe_image_style (si non from io import BytesIO)
from io import BytesIO # <--- CORRECTION: Importation explicite de BytesIO
import base64
import os
from dotenv import load_dotenv
import traceback
import json
import time
import requests

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# --- CONFIGURATION ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

if not OPENAI_API_KEY:
    print("AVERTISSEMENT: OPENAI_API_KEY n'est pas défini. Les appels directs à l'API OpenAI pourraient échouer.")
if not REPLICATE_API_TOKEN:
    raise ValueError("ERREUR: La variable d'environnement REPLICATE_API_TOKEN n'est pas définie.")

os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
print("✅ Replicate/Imagen configuré")

# --- PARAMÈTRE GLOBAL DE TIMEOUT ET RETRY ---
REPLICATE_TIMEOUT = 600 # secondes (10 minutes), très généreux

# Paramètres pour la logique de réessai
MAX_RETRIES = 5
INITIAL_RETRY_DELAY_SECONDS = 2 # Premier délai avant de réessayer (en secondes)

class FlyerGenerator:
    def __init__(self, api_key_unused):
        try:
            print("✅ FlyerGenerator initialisé (utilisation de Replicate pour tous les modèles)")
        except Exception as e:
            print(f"❌ Erreur initialisation FlyerGenerator: {e}")
            raise

    def _replicate_run_with_retries(self, model_name, input_data, timeout, max_retries=MAX_RETRIES, initial_delay=INITIAL_RETRY_DELAY_SECONDS):
        current_delay = initial_delay
        for attempt in range(max_retries):
            try:
                print(f"   (Tentative {attempt + 1}/{max_retries}) Appel à Replicate modèle '{model_name}'...")
                output = replicate.run(
                    model_name,
                    input=input_data,
                    timeout=timeout
                )
                return output
            except ReplicateError as e:
                if e.status == 429:
                    print(f"   ⚠️ Replicate a renvoyé 429 (trop de requêtes). Réessai dans {current_delay:.1f}s...")
                    time.sleep(current_delay)
                    current_delay *= 2
                    if current_delay > 60:
                        current_delay = 60
                else:
                    print(f"   ❌ Erreur Replicate inattendue (non 429): {e}")
                    raise
            except Exception as e:
                print(f"   ❌ Erreur générale lors de l'appel Replicate (tentative {attempt + 1}): {e}")
                time.sleep(current_delay)
                current_delay *= 2
                if current_delay > 60:
                    current_delay = 60

        raise ReplicateError(f"Échec de l'appel au modèle '{model_name}' après {max_retries} tentatives en raison de problèmes de limitation de débit ou d'autres erreurs persistantes.")


    def describe_image_style(self, style_image_bytes):
        print("🔍 [Étape 1/3] Début analyse de l'image d'entrée pour le style...")
        
        try:
            img_base64 = base64.b64encode(style_image_bytes).decode('utf-8')
            image_url_for_replicate = f"data:image/jpeg;base64,{img_base64}"

            prompt_for_gpt_description = """
            Describe the visual style, color palette, atmosphere, and dominant elements of the provided image in detail. Focus on aspects relevant for generating a new image with a similar aesthetic. Be concise but comprehensive.
            """

            print("   🤖 Envoi à GPT-4o (via Replicate) pour description...")
            output = self._replicate_run_with_retries(
                "openai/gpt-4o",
                input_data={
                    "prompt": prompt_for_gpt_description,
                    "image_input": [image_url_for_replicate],
                    "max_completion_tokens": 300,
                    "temperature": 0.7
                },
                timeout=REPLICATE_TIMEOUT
            )
            description = "".join(output)
            print(f"   ✅ Description reçue: {len(description)} caractères. Aperçu: {description[:100]}...")
            return description

        except Exception as e:
            print(f"   ❌ Erreur dans describe_image_style: {e}")
            print(f"   📋 Traceback: {traceback.format_exc()}")
            raise

    def suggest_text_styles_for_flyer(self, image_style_description, generated_image_url, content_data):
        print("🎨 [Étape 3/3] Début suggestion de styles de texte en analysant l'image générée et le contenu...")
        try:
            headline_content = content_data.get('headline1', 'Headline')
            description_content = content_data.get('short_description', 'A concise description of your event, summarizing its purpose or key features.')
            event_info_content = content_data.get('event_info', 'Date, Time, and Location of the Event')
            footer_info_content = content_data.get('footer_info', 'Contact Information, Website, and Phone Number')

            full_prompt_text = f"""
            Based on the following visual style description:
            "{image_style_description}"

            And **critically, based on the attached image (which is the generated flyer background)**, suggest a cohesive, **highly legible**, and **professionally balanced** text style palette for a vertical flyer with a **9:16 aspect ratio (e.g., a canvas of 360px width, 640px height)**. The goal is to perfectly integrate text as if designed by a professional graphic designer.

            **Here is the actual text content that will be placed. Use this to determine optimal font sizes, line breaks, and overall space needed for each block:**
            Headline: "{headline_content}"
            Description: "{description_content}"
            Event Details: "{event_info_content}"
            Contact Info: "{footer_info_content}"

            **CRITICAL REQUIREMENTS FOR OPTIMAL TEXT INTEGRATION:**
            1.  **COLOR CONTRAST (HIGHEST PRIORITY):** Analyze the attached image. Determine its dominant light/dark areas and colors. Suggest text colors that provide **stark, undeniable contrast against the SPECIFIC BACKGROUND areas where text is placed.** Prioritize pure white (#FFFFFF) or pure black (#000000) for maximum legibility. If the image style suggests a vibrant color, ensure it still achieves very high contrast.
            2.  **FONT SELECTION & DESIGN:** Choose font families that complement the visual style while remaining highly readable. Consider the overall elegance and professionalism.
            3.  **FONT SIZE (`fontSizePx`):** Suggest pixel sizes that are perfectly scaled for the 360px width, ensuring all actual text content fits gracefully within the suggested `initialWidthPercentage` without truncation, and is clearly legible. The sizes should reflect a clear visual hierarchy (headline largest, footer smallest, etc.). **Consider the actual length of the text provided above when determining the optimal font size and potential line breaks.**
            4.  **LINE HEIGHT (`lineHeightEm`):** Provide `lineHeightEm` for excellent vertical spacing within multi-line text blocks.
            5.  **INITIAL POSITIONING (`initialTopPercentage`, `initialWidthPercentage`):**
                *   **Strategic Placement:** Analyze the attached image for clear, open, and less busy areas. Suggest `initialTopPercentage` and `initialWidthPercentage` values that position each text block in a visually prominent, uncluttered, and balanced way.
                *   **Avoid Graphic Conflicts:** Ensure text does NOT overlap with or get obscured by major graphic elements (like large moons, intricate buildings, or bright/dark transitions).
                *   **Visual Hierarchy & Flow:** Positions should create a natural reading flow (top-to-bottom) and visually distinct sections. Provide ample padding around text areas relative to the image edges.
            6.  **TEXT HIERARCHY:** The font sizes and weights should clearly distinguish between headline, description, event details, and footer.

            Provide your suggestions in a JSON format.

            For each text type (headline, body, event_info, footer), suggest:
            - `fontFamily`: (e.g., "Arial, sans-serif", "Roboto, sans-serif", "Open Sans, sans-serif", "Lato, sans-serif", "Merriweather, serif"). Prioritize common, legible web-safe or popular Google Fonts.
            - `color`: (a HEX code, based on image analysis).
            - `fontSizePx`: (a numerical value in pixels, perfectly scaled for 360px width).
            - `fontWeight`: (e.g., "bold", "normal", "lighter", "500", "700").
            - `textAlign`: (e.g., "center", "left", "right").
            - `lineHeightEm`: (a numerical value for line-height, e.g., 1.1, 1.2, 1.4, 1.5).
            - `initialTopPercentage`: (a number from 0 to 100).
            - `initialWidthPercentage`: (a number from 50 to 95).

            Example JSON structure (reflecting professional design principles):
            {{ # Outer JSON start
                "headline": {{{{ # Inner headline object start
                    "fontFamily": "Playfair Display, serif",
                    "color": "#000000",
                    "fontSizePx": 48,
                    "fontWeight": "bold",
                    "textAlign": "center",
                    "lineHeightEm": 1.1,
                    "initialTopPercentage": 8,
                    "initialWidthPercentage": 90
                }}}}, # Inner headline object end
                "body": {{{{ # Inner body object start
                    "fontFamily": "Roboto, sans-serif",
                    "color": "#000000",
                    "fontSizePx": 20,
                    "fontWeight": "normal",
                    "textAlign": "center",
                    "lineHeightEm": 1.4,
                    "initialTopPercentage": 25,
                    "initialWidthPercentage": 85
                }}}}, # Inner body object end
                "event_info": {{{{ # Inner event_info object start
                    "fontFamily": "Open Sans, sans-serif",
                    "color": "#000000",
                    "fontSizePx": 28,
                    "fontWeight": "bold",
                    "textAlign": "center",
                    "lineHeightEm": 1.2,
                    "initialTopPercentage": 60,
                    "initialWidthPercentage": 90
                }}}}, # Inner event_info object end
                "footer": {{{{ # Inner footer object start
                    "fontFamily": "Arial, sans-serif",
                    "color": "#000000",
                    "fontSizePx": 16,
                    "fontWeight": "normal",
                    "textAlign": "center",
                    "lineHeightEm": 1.5,
                    "initialTopPercentage": 90,
                    "initialWidthPercentage": 95
                }}}} # Inner footer object end
            }} # Outer JSON end
            """
            print("   🤖 Envoi à GPT-4o pour styles de texte (avec image générée et contenu réel)...")
            output = self._replicate_run_with_retries(
                "openai/gpt-4o",
                input_data={
                    "prompt": full_prompt_text,
                    "image_input": [generated_image_url],
                    "max_completion_tokens": 1500,
                    "temperature": 0.7
                },
                timeout=REPLICATE_TIMEOUT
            )
            suggestions_str = "".join(output)
            print(f"   ✅ Suggestions reçues: {len(suggestions_str)} caractères. Aperçu: {suggestions_str[:200]}...")

            try:
                suggestions = json.loads(suggestions_str)
                if isinstance(suggestions, str) and suggestions.startswith("```json") and suggestions.endswith("```"):
                    suggestions = json.loads(suggestions.strip("```json\n").strip("```"))
            except json.JSONDecodeError:
                print(f"   ⚠️ GPT-4o n'a pas retourné un JSON valide. Tentative de correction ou d'extraction.")
                json_start = suggestions_str.find('{')
                json_end = suggestions_str.rfind('}')
                if json_start != -1 and json_end != -1:
                    try:
                        suggestions = json.loads(suggestions_str[json_start:json_end+1])
                    except Exception as e:
                        print(f"   ❌ Échec de la correction JSON: {e}")
                        suggestions = {}
                else:
                    suggestions = {}

            return suggestions

        except Exception as e:
            print(f"   ❌ Erreur dans suggest_text_styles_for_flyer: {e}")
            print(f"   📋 Traceback: {traceback.format_exc()}")
            raise

    def generate_textless_flyer_background(self, style_description, content_data):
        print("🖼️ [Étape 2/3] Début génération image de fond sans texte avec Imagen...")

        headline_length_desc = "a short, prominent heading" if len(content_data.get('headline1', '')) < 25 else "a medium-length, multi-line prominent heading"
        description_length_desc = "a concise, short paragraph" if len(content_data.get('short_description', '')) < 150 else "a detailed, longer multi-line paragraph"
        event_info_length_desc = "a single line of important details"
        footer_info_length_desc = "one to two lines of contact information"

        imagen_prompt = f"""
        Generate a highly detailed and artistic flyer background in a vertical 9:16 aspect ratio.
        The visual style and atmosphere should be: {style_description}

        ⚠️ CRITICAL INSTRUCTION:
        DO NOT generate any text, letters, numbers, writing, words, symbols, glyphs, or anything that resembles text or typography.

        The image must be:
        - Fully graphical and artistic,
        - WITHOUT ANY visible or hidden text or shapes that look like placeholders or banners,
        - NO logos, no fake UI, no watermarks, no labels, no icons, no boxes for text.

        🧠 Imagine that this flyer will have 4 blocks of information added later:
        - A title,
        - A paragraph of description,
        - Event details (time and location),
        - Contact information.

        DO NOT include or imply these elements in the image. Instead, arrange the artistic composition to leave soft, natural zones that *could be used* for text overlay — but that look organic and part of the scene.

        🎯 The image must feel complete and beautiful WITHOUT any indication that text should be placed somewhere. No banners, no scrolls, no outlines, no boxes.

        ABSOLUTELY NO TEXT.
        """

        print(f"   📏 Longueur du prompt Imagen (purely artistic & text-aware via abstract zones): {len(imagen_prompt)} caractères")
        print("   🚀 Envoi à Imagen 4 (Replicate) pour fond sans texte et text-aware...")

        try:
            output = self._replicate_run_with_retries(
                "google/imagen-4",
                input_data={
                    "prompt": imagen_prompt,
                    "aspect_ratio": "9:16",
                    "output_format": "jpg",
                    "safety_filter_level": "block_medium_and_above",
                    "negative_prompt": "text, words, letters, numbers, typography, font, watermark, logo, symbol, unreadable text, garbled text, blurry text, bad typography, character, script, writing, hieroglyph, glyph, any textual element, text artifacts, corrupted text, latin text, arabic text, chinese text, japanese text, english text, any language text, inscription, sign, logo, brand, stamp, placeholder, text box, text field, rectangle, square, box, blank space for text, Lorem ipsum, banner, ribbon, scroll, label, badge, text bubble, speech bubble, blank form, form elements, table, chart, diagram, outline, border, shape, empty area with border, background with designated blank space for text, explicit text area, empty label, empty sign"
                },
                timeout=REPLICATE_TIMEOUT
            )

            image_url = None
            if not output:
                raise Exception("Replicate returned empty response")

            if isinstance(output, list) and output:
                image_url = output[0]
                print(f"   📋 URL extraite de liste: {image_url}")
            elif isinstance(output, (str, FileOutput)):
                image_url = str(output)
                print(f"   📋 URL directe: {image_url}")

            if not image_url:
                raise Exception(f"Could not extract URL from Replicate response. Output type: {type(output)}, content: {output}")

            print(f"   ✅ Image de fond générée avec succès ! URL: {image_url}")
            return image_url

        except Exception as e:
            print(f"   ❌ Erreur dans generate_textless_flyer_background: {e}")
            print(f"   📋 Traceback: {traceback.format_exc()}")
            raise

# Initialisation du générateur
try:
    flyer_gen = FlyerGenerator(api_key_unused=None)
    print("✅ Générateur initialisé avec succès")
except Exception as e:
    print(f"❌ ERREUR CRITIQUE lors de l'initialisation du générateur: {e}")
    raise

# --- Fonction utilitaire pour obtenir le chemin de la police ---
# IMPORTANT: Vous DEVEZ avoir les fichiers .ttf ou .otf des polices que vous utilisez
# sur votre serveur, idéalement dans un dossier 'fonts' à côté de app.py.
# Sinon, Pillow utilisera une police par défaut, ce qui affectera le rendu.
def _get_font_path(font_family):
    base_dir = os.path.dirname(__file__)
    project_fonts_dir = os.path.join(base_dir, 'fonts') # Créez ce dossier et mettez vos .ttf ici

    # Cartographie des noms de polices CSS aux noms de fichiers .ttf.
    # Ajoutez ici les noms exacts des fichiers .ttf que vous avez téléchargés.
    font_files_map = {
        "Arial": "arial.ttf",
        "Verdana": "verdana.ttf",
        "Helvetica": "arial.ttf", # Souvent remplacée par Arial
        "Georgia": "georgia.ttf",
        "Times New Roman": "times.ttf",
        "Courier New": "cour.ttf",
        "Impact": "impact.ttf",
        "Trebuchet MS": "trebuc.ttf",
        "Open Sans": "OpenSans-Regular.ttf", # Assurez-vous d'avoir ce fichier
        "Roboto": "Roboto-Regular.ttf",     # Assurez-vous d'avoir ce fichier
        "Playfair Display": "PlayfairDisplay-Regular.ttf", # Assurez-vous d'avoir ce fichier
        "Lato": "Lato-Regular.ttf",         # Assurez-vous d'avoir ce fichier
        "Merriweather": "Merriweather-Regular.ttf", # Assurez-vous d'avoir ce fichier
        # Pour les variantes (gras, italique), vous aurez besoin de fichiers spécifiques (ex: Roboto-Bold.ttf)
        # Ceci est une simplification pour l'exemple.
    }

    # Nettoyage du nom de la police pour la recherche
    clean_font_name = font_family.split(',')[0].strip()
    
    # Prioriser les polices du dossier 'fonts' du projet
    if clean_font_name in font_files_map:
        potential_path = os.path.join(project_fonts_dir, font_files_map[clean_font_name])
        if os.path.exists(potential_path):
            return potential_path
    
    # Fallback vers des polices système courantes (peut varier selon l'OS)
    system_font_paths = {
        "serif": ["times.ttf", "Georgia.ttf"],
        "sans-serif": ["arial.ttf", "OpenSans-Regular.ttf", "Roboto-Regular.ttf"],
        "monospace": ["cour.ttf"]
    }

    # Essayer de trouver une police générique si aucune correspondance directe
    if "serif" in font_family.lower():
        fallback_filenames = system_font_paths["serif"]
    elif "monospace" in font_family.lower():
        fallback_filenames = system_font_paths["monospace"]
    else:
        fallback_filenames = system_font_paths["sans-serif"]
    
    for filename in fallback_filenames:
        # Essayer dans le dossier de votre projet
        potential_path = os.path.join(project_fonts_dir, filename)
        if os.path.exists(potential_path):
            print(f"   Utilisation de la police de fallback du projet: {potential_path}")
            return potential_path
        
        # Essayer des chemins système courants (pour Linux/Windows)
        for sys_path_prefix in ["/usr/share/fonts/truetype/", "/Library/Fonts/", os.path.join(os.getenv("WINDIR") or "", "Fonts")]:
            potential_path = os.path.join(sys_path_prefix, filename)
            if os.path.exists(potential_path):
                print(f"   Utilisation de la police de fallback système: {potential_path}")
                return potential_path

    print(f"   AVERTISSEMENT: Police '{font_family}' ou une alternative appropriée non trouvée. Utilisation de la police par défaut de Pillow.")
    return None # Pillow utilisera sa police par défaut

def _text_wrap(text, font, max_width):
    lines = []
    if not text:
        return lines

    # Utilisez textbbox pour obtenir des mesures précises du texte
    # textbbox retourne (left, top, right, bottom)
    # text_width = bbox[2] - bbox[0]
    
    words = text.split(' ')
    current_line = []
    for word in words:
        test_line = ' '.join(current_line + [word])
        
        # Obtenir la largeur du texte de test
        try:
            # textbbox est plus fiable pour obtenir les dimensions exactes du texte
            bbox = font.getbbox(test_line)
            text_width = bbox[2] - bbox[0]
        except Exception as e:
            # Fallback si getbbox échoue (ex: caractères non supportés par la police)
            print(f"   AVERTISSEMENT: Échec de font.getbbox pour '{test_line}': {e}. Estimations utilisées.")
            # Estimation approximative si getbbox échoue
            text_width = len(test_line) * font.size * 0.6 # 0.6 est un facteur heuristique
            
        if text_width <= max_width:
            current_line.append(word)
        else:
            if current_line: # Si la ligne actuelle n'est pas vide, l'ajouter
                lines.append(' '.join(current_line))
            
            # Vérifier si le mot lui-même est plus large que la largeur max
            try:
                word_bbox = font.getbbox(word)
                word_width = word_bbox[2] - word_bbox[0]
            except Exception:
                word_width = len(word) * font.size * 0.6

            if word_width > max_width:
                # Si un seul mot est trop long, il doit être coupé. Pillow ne coupe pas le texte.
                # Pour l'instant, on ajoute le mot tel quel, il dépassera.
                # Une implémentation plus avancée devrait couper le mot.
                lines.append(word)
                current_line = []
            else:
                current_line = [word] # Commence une nouvelle ligne avec le mot
    
    if current_line:
        lines.append(' '.join(current_line))
    return lines


# --- ROUTES FLASK MODIFIÉES ---
@app.route('/api/generate-flyer-from-prototype', methods=['POST'])
def generate_flyer_from_prototype():
    print("\n" + "="*80)
    print("🚀 NOUVELLE REQUÊTE DE GÉNÉRATION API (Fond purement artistique + Styles Texte analysés)")
    print("="*80)

    try:
        print("🔍 Phase 1: Validation des données reçues")

        if 'image' not in request.files:
            error_msg = "Aucun fichier 'image' dans la requête"
            print(f"   ❌ {error_msg}")
            return jsonify({'error': error_msg}), 400

        style_image_file = request.files['image']
        print(f"   📁 Fichier reçu: {style_image_file.filename}")

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

        try:
            # Utilise io.BytesIO car BytesIO n'est pas importé directement pour cette partie
            # ou vous pouvez changer cette ligne aussi pour utiliser 'BytesIO(style_image_bytes)'
            Image.open(io.BytesIO(style_image_bytes))
            print(f"   ✅ Image d'entrée valide (test PIL)")
        except Exception as e:
            error_msg = f"L'image fournie est invalide ou corrompue: {e}"
            print(f"   ❌ {error_msg}")
            return jsonify({'error': error_msg}), 400
        
        content_data = {
            'headline1': request.form.get('headline1', 'Your Event Headline'),
            'short_description': request.form.get('short_description', 'A brief description of your event, summarizing its purpose and key features.'),
            'event_info': request.form.get('event_info', 'Date, Time, and Location'),
            'footer_info': request.form.get('footer_info', 'Contact Info | Website | Phone')
        }
        print(f"   📝 Données textuelles reçues: {content_data}")


        print("   ✅ Phase 1 terminée: Données valides")

        print("\n🔍 Phase 2: Analyse de l'image d'entrée avec GPT-4o (via Replicate)")
        try:
            style_description = flyer_gen.describe_image_style(style_image_bytes)
            print("   ✅ Phase 2 terminée: Image analysée")
        except Exception as e:
            error_msg = f'Erreur lors de l\'analyse du style de l\'image par GPT-4o (via Replicate): {str(e)}'
            print(f"   ❌ {error_msg}")
            return jsonify({'error': error_msg}), 500

        print("\n🖼️ Phase 3: Génération de l'image de fond purement artistique avec Imagen 4")
        try:
            flyer_background_image_url = flyer_gen.generate_textless_flyer_background(style_description, content_data)
            print("   ✅ Phase 3 terminée: Image de fond générée")
        except Exception as e:
            error_msg = f'Erreur lors de la génération de l\'image de fond par Imagen (Replicate): {str(e)}'
            print(f"   ❌ {error_msg}")
            return jsonify({'error': error_msg}), 500

        print("\n🎨 Nouvelle Phase: Suggestion de styles de texte avec GPT-4o VISION (sur l'image générée)")
        try:
            text_style_suggestions = flyer_gen.suggest_text_styles_for_flyer(style_description, flyer_background_image_url, content_data)
            print("   ✅ Styles de texte suggérés basés sur l'image générée et le contenu réel")
        except Exception as e:
            error_msg = f'Erreur lors de la suggestion des styles de texte par GPT-4o Vision (via Replicate): {str(e)}'
            print(f"   ❌ {error_msg}")
            return jsonify({'error': error_msg}), 500


        print(f"\n✅ SUCCÈS COMPLET!")
        print(f"   🎉 URL de l'image de fond (Replicate): {flyer_background_image_url}")
        print("="*80 + "\n")

        return jsonify({
            'success': True,
            'flyer_background_url': flyer_background_image_url,
            'text_style_suggestions': text_style_suggestions,
            'message': 'Image de fond et suggestions de style générées avec succès. Le texte doit être superposé côté client.'
        })

    except Exception as e:
        print(f"\n❌ ERREUR FATALE DANS LA ROUTE PRINCIPALE:")
        print(f"   🔥 Erreur: {e}")
        print(f"   📋 Type: {type(e).__name__}")
        print(f"   🗂️ Traceback complet:")
        traceback.print_exc()
        print("="*80 + "\n")

        return jsonify({
            'error': f"Une erreur interne est survenue sur le serveur: {str(e)}",
            'error_type': type(e).__name__,
            'debug_info_for_dev': "Vérifiez les logs du serveur pour plus de détails."
        }), 500

# --- NOUVELLE ROUTE POUR LA GÉNÉRATION FINALE DU FLYER CÔTÉ SERVEUR ---
@app.route('/api/generate-final-flyer', methods=['POST'])
def generate_final_flyer():
    print("\n" + "="*80)
    print("✨ NOUVELLE REQUÊTE DE GÉNÉRATION FINALE DE FLYER (Côté Serveur)")
    print("="*80)
    try:
        data = request.json
        background_url = data.get('background_url')
        text_components = data.get('text_components', [])
        flyer_dims = data.get('flyer_dimensions', {'width': 360, 'height': 640})

        if not background_url:
            return jsonify({'error': 'URL de l\'image de fond manquante.'}), 400

        print(f"   Téléchargement de l'image de fond depuis: {background_url}")
        response = requests.get(background_url, stream=True)
        response.raise_for_status()
        background_image_bytes = BytesIO(response.content) # <-- C'est ici que BytesIO était non défini
        background = Image.open(background_image_bytes).convert("RGBA")

        if background.width != flyer_dims['width'] or background.height != flyer_dims['height']:
            print(f"   Redimensionnement de l'image de fond de {background.size} à {flyer_dims['width']}x{flyer_dims['height']}")
            background = background.resize((flyer_dims['width'], flyer_dims['height']), Image.Resampling.LANCZOS)
        
        draw = ImageDraw.Draw(background)

        for comp in text_components:
            content = comp.get('content', '')
            x = comp.get('x', 0)
            y = comp.get('y', 0)
            style = comp.get('style', {})

            # Convertir la largeur en pixels basée sur le pourcentage
            width_percent = int(comp.get('width', '90%').replace('%', ''))
            max_text_width_px = (width_percent / 100) * flyer_dims['width']

            font_family = style.get('fontFamily', 'Arial, sans-serif').split(',')[0].strip()
            font_size_px = style.get('fontSizePx', 24)
            color_hex = style.get('color', '#000000')
            text_align = style.get('textAlign', 'center')
            line_height_em = style.get('lineHeightEm', 1.4)

            text_color_rgb = tuple(int(color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            text_color_rgba = (*text_color_rgb, 255) # Couleur du texte (opaque)

            font_path = _get_font_path(font_family)
            try:
                font = ImageFont.truetype(font_path, font_size_px) if font_path else ImageFont.load_default()
            except IOError:
                print(f"   AVERTISSEMENT: Impossible de charger la police '{font_family}'. Utilisation de la police par défaut.")
                font = ImageFont.load_default()

            # Calculer la couleur de l'ombre en fonction de la luminosité du texte principal
            # Utilise la formule de luminosité perçue (YIQ)
            is_light_text_color = (text_color_rgb[0] * 0.299 + text_color_rgb[1] * 0.587 + text_color_rgb[2] * 0.114) > 186
            shadow_color_rgba = (0, 0, 0, 180) if is_light_text_color else (255, 255, 255, 180) # Semi-transparent
            shadow_offset = 1 # Décalage de l'ombre en pixels

            lines = _text_wrap(content, font, max_text_width_px)
            
            current_y = y
            for line in lines:
                # Obtenir la bbox de la ligne pour calculer sa largeur réelle
                # textbbox((x,y), text, font) retourne (left, top, right, bottom)
                # Le premier (x,y) est juste un point de référence, les valeurs de la bbox sont relatives à ce point
                try:
                    bbox = font.getbbox(line)
                    line_width = bbox[2] - bbox[0] # Largeur réelle de la ligne de texte
                except Exception as e:
                    print(f"   AVERTISSEMENT: Échec de font.getbbox pour ligne '{line}': {e}. Estimations utilisées.")
                    line_width = len(line) * font.size * 0.6
                
                # Calculer la position X en fonction de l'alignement
                line_x = x # Point de départ du conteneur texte
                if text_align == 'center':
                    line_x += (max_text_width_px - line_width) / 2
                elif text_align == 'right':
                    line_x += (max_text_width_px - line_width)
                # else: (left) line_x reste x
                
                # Dessiner l'ombre
                draw.text((line_x + shadow_offset, current_y + shadow_offset), line, font=font, fill=shadow_color_rgba)
                # Dessiner le texte principal
                draw.text((line_x, current_y), line, font=font, fill=text_color_rgba)

                # Calculer la hauteur de la ligne suivante
                # La hauteur de la ligne est basée sur la taille de la police et le lineHeightEm
                # Une approximation est (hauteur_de_ligne_réelle_par_Pillow * lineHeightEm)
                # Ou simplement la taille de la police * lineHeightEm
                next_line_height = font_size_px * line_height_em
                current_y += next_line_height


        img_io = BytesIO()
        background.save(img_io, 'PNG', quality=95)
        img_io.seek(0)

        print("   ✅ Flyer final généré avec succès !")
        return send_file(img_io, mimetype='image/png')

    except Exception as e:
        print(f"\n❌ ERREUR LORS DE LA GÉNÉRATION FINALE DU FLYER:")
        print(f"   🔥 Erreur: {e}")
        print(f"   📋 Type: {type(e).__name__}")
        print(f"   🗂️ Traceback complet:")
        traceback.print_exc()
        print("="*80 + "\n")
        return jsonify({'error': f"Une erreur interne est survenue lors de la génération du flyer final: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)































# # FLYER-IA/flyer-ia/backend/app.py

# from flask import Flask, request, jsonify
# from flask_cors import CORS
# import openai
# import replicate
# from replicate.exceptions import ReplicateError
# from replicate.helpers import FileOutput
# from PIL import Image
# import io
# import base64
# import os
# from dotenv import load_dotenv
# import traceback
# import json
# import time # Importation ajoutée pour la gestion des délais

# load_dotenv()

# app = Flask(__name__)
# CORS(app, resources={r"/api/*": {"origins": "*"}})

# # --- CONFIGURATION ---
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

# if not OPENAI_API_KEY:
#     print("AVERTISSEMENT: OPENAI_API_KEY n'est pas défini. Les appels directs à l'API OpenAI pourraient échouer.")
# if not REPLICATE_API_TOKEN:
#     raise ValueError("ERREUR: La variable d'environnement REPLICATE_API_TOKEN n'est pas définie.")

# os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
# print("✅ Replicate/Imagen configuré")

# # --- PARAMÈTRE GLOBAL DE TIMEOUT ET RETRY ---
# REPLICATE_TIMEOUT = 600 # secondes (10 minutes), très généreux

# # Paramètres pour la logique de réessai
# MAX_RETRIES = 5
# INITIAL_RETRY_DELAY_SECONDS = 2 # Premier délai avant de réessayer (en secondes)

# class FlyerGenerator:
#     def __init__(self, api_key_unused):
#         try:
#             print("✅ FlyerGenerator initialisé (utilisation de Replicate pour tous les modèles)")
#         except Exception as e:
#             print(f"❌ Erreur initialisation FlyerGenerator: {e}")
#             raise

#     # Nouvelle méthode privée pour gérer les appels Replicate avec réessais
#     def _replicate_run_with_retries(self, model_name, input_data, timeout, max_retries=MAX_RETRIES, initial_delay=INITIAL_RETRY_DELAY_SECONDS):
#         current_delay = initial_delay
#         for attempt in range(max_retries):
#             try:
#                 print(f"   (Tentative {attempt + 1}/{max_retries}) Appel à Replicate modèle '{model_name}'...")
#                 output = replicate.run(
#                     model_name,
#                     input=input_data,
#                     timeout=timeout
#                 )
#                 return output
#             except ReplicateError as e:
#                 # Si c'est une erreur 429 (trop de requêtes), on attend et on réessaie
#                 if e.status == 429:
#                     print(f"   ⚠️ Replicate a renvoyé 429 (trop de requêtes). Réessai dans {current_delay:.1f}s...")
#                     time.sleep(current_delay)
#                     current_delay *= 2  # Augmente le délai de manière exponentielle
#                     # Limite le délai maximum pour éviter des attentes trop longues
#                     if current_delay > 60:
#                         current_delay = 60
#                 else:
#                     # Pour toute autre erreur Replicate, on ne réessaie pas et on lève l'exception
#                     print(f"   ❌ Erreur Replicate inattendue (non 429): {e}")
#                     raise
#             except Exception as e:
#                 # Pour toute autre erreur (réseau, etc.), on réessaie aussi
#                 print(f"   ❌ Erreur générale lors de l'appel Replicate (tentative {attempt + 1}): {e}")
#                 time.sleep(current_delay)
#                 current_delay *= 2
#                 if current_delay > 60:
#                     current_delay = 60

#         # Si toutes les tentatives ont échoué, on lève une exception
#         raise ReplicateError(f"Échec de l'appel au modèle '{model_name}' après {max_retries} tentatives en raison de problèmes de limitation de débit ou d'autres erreurs persistantes.")


#     def describe_image_style(self, style_image_bytes):
#         print("🔍 [Étape 1/3] Début analyse de l'image d'entrée pour le style...")
        
#         try:
#             img_base64 = base64.b64encode(style_image_bytes).decode('utf-8')
#             image_url_for_replicate = f"data:image/jpeg;base64,{img_base64}"

#             prompt_for_gpt_description = """
#             Describe the visual style, color palette, atmosphere, and dominant elements of the provided image in detail. Focus on aspects relevant for generating a new image with a similar aesthetic. Be concise but comprehensive.
#             """

#             print("   🤖 Envoi à GPT-4o (via Replicate) pour description...")
#             # Utilise la nouvelle méthode avec réessais
#             output = self._replicate_run_with_retries(
#                 "openai/gpt-4o",
#                 input_data={
#                     "prompt": prompt_for_gpt_description,
#                     "image_input": [image_url_for_replicate],
#                     "max_completion_tokens": 300,
#                     "temperature": 0.7
#                 },
#                 timeout=REPLICATE_TIMEOUT
#             )
#             description = "".join(output)
#             print(f"   ✅ Description reçue: {len(description)} caractères. Aperçu: {description[:100]}...")
#             return description

#         except Exception as e:
#             print(f"   ❌ Erreur dans describe_image_style: {e}")
#             print(f"   📋 Traceback: {traceback.format_exc()}")
#             raise

#     def suggest_text_styles_for_flyer(self, image_style_description, generated_image_url, content_data):
#         print("🎨 [Étape 3/3] Début suggestion de styles de texte en analysant l'image générée et le contenu...")
#         try:
#             # Formater le texte à inclure dans le prompt de GPT-4o Vision pour l'estimation de taille
#             headline_content = content_data.get('headline1', 'Headline')
#             description_content = content_data.get('short_description', 'A concise description of your event, summarizing its purpose or key features.')
#             event_info_content = content_data.get('event_info', 'Date, Time, and Location of the Event')
#             footer_info_content = content_data.get('footer_info', 'Contact Information, Website, and Phone Number')

#             # PROMPT DE GPT-4o VISION AMÉLIORÉ POUR LA QUALITÉ PROFESSIONNELLE ET LE CONTENU SPÉCIFIQUE
#             full_prompt_text = f"""
#             Based on the following visual style description:
#             "{image_style_description}"

#             And **critically, based on the attached image (which is the generated flyer background)**, suggest a cohesive, **highly legible**, and **professionally balanced** text style palette for a vertical flyer with a **9:16 aspect ratio (e.g., a canvas of 360px width, 640px height)**. The goal is to perfectly integrate text as if designed by a professional graphic designer.

#             **Here is the actual text content that will be placed. Use this to determine optimal font sizes, line breaks, and overall space needed for each block:**
#             Headline: "{headline_content}"
#             Description: "{description_content}"
#             Event Details: "{event_info_content}"
#             Contact Info: "{footer_info_content}"

#             **CRITICAL REQUIREMENTS FOR OPTIMAL TEXT INTEGRATION:**
#             1.  **COLOR CONTRAST (HIGHEST PRIORITY):** Analyze the attached image. Determine its dominant light/dark areas and colors. Suggest text colors that provide **stark, undeniable contrast against the SPECIFIC BACKGROUND areas where text is placed.** Prioritize pure white (#FFFFFF) or pure black (#000000) for maximum legibility. If the image style suggests a vibrant color, ensure it still achieves very high contrast.
#             2.  **FONT SELECTION & DESIGN:** Choose font families that complement the visual style while remaining highly readable. Consider the overall elegance and professionalism.
#             3.  **FONT SIZE (`fontSizePx`):** Suggest pixel sizes that are perfectly scaled for the 360px width, ensuring all actual text content fits gracefully within the suggested `initialWidthPercentage` without truncation, and is clearly legible. The sizes should reflect a clear visual hierarchy (headline largest, footer smallest, etc.). **Consider the actual length of the text provided above when determining the optimal font size and potential line breaks.**
#             4.  **LINE HEIGHT (`lineHeightEm`):** Provide `lineHeightEm` for excellent vertical spacing within multi-line text blocks.
#             5.  **INITIAL POSITIONING (`initialTopPercentage`, `initialWidthPercentage`):**
#                 *   **Strategic Placement:** Analyze the attached image for clear, open, and less busy areas. Suggest `initialTopPercentage` and `initialWidthPercentage` values that position each text block in a visually prominent, uncluttered, and balanced way.
#                 *   **Avoid Graphic Conflicts:** Ensure text does NOT overlap with or get obscured by major graphic elements (like large moons, intricate buildings, or bright/dark transitions).
#                 *   **Visual Hierarchy & Flow:** Positions should create a natural reading flow (top-to-bottom) and visually distinct sections. Provide ample padding around text areas relative to the image edges.
#             6.  **TEXT HIERARCHY:** The font sizes and weights should clearly distinguish between headline, description, event details, and footer.

#             Provide your suggestions in a JSON format.

#             For each text type (headline, body, event_info, footer), suggest:
#             - `fontFamily`: (e.g., "Arial, sans-serif", "Roboto, sans-serif", "Open Sans, sans-serif", "Lato, sans-serif", "Merriweather, serif"). Prioritize common, legible web-safe or popular Google Fonts.
#             - `color`: (a HEX code, based on image analysis).
#             - `fontSizePx`: (a numerical value in pixels, perfectly scaled for 360px width).
#             - `fontWeight`: (e.g., "bold", "normal", "lighter", "500", "700").
#             - `textAlign`: (e.g., "center", "left", "right").
#             - `lineHeightEm`: (a numerical value for line-height, e.g., 1.1, 1.2, 1.4, 1.5).
#             - `initialTopPercentage`: (a number from 0 to 100).
#             - `initialWidthPercentage`: (a number from 50 to 95).

#             Example JSON structure (reflecting professional design principles):
#             {{ # Outer JSON start
#                 "headline": {{{{ # Inner headline object start
#                     "fontFamily": "Playfair Display, serif",
#                     "color": "#000000",
#                     "fontSizePx": 48,
#                     "fontWeight": "bold",
#                     "textAlign": "center",
#                     "lineHeightEm": 1.1,
#                     "initialTopPercentage": 8,
#                     "initialWidthPercentage": 90
#                 }}}}, # Inner headline object end
#                 "body": {{{{ # Inner body object start
#                     "fontFamily": "Roboto, sans-serif",
#                     "color": "#000000",
#                     "fontSizePx": 20,
#                     "fontWeight": "normal",
#                     "textAlign": "center",
#                     "lineHeightEm": 1.4,
#                     "initialTopPercentage": 25,
#                     "initialWidthPercentage": 85
#                 }}}}, # Inner body object end
#                 "event_info": {{{{ # Inner event_info object start
#                     "fontFamily": "Open Sans, sans-serif",
#                     "color": "#000000",
#                     "fontSizePx": 28,
#                     "fontWeight": "bold",
#                     "textAlign": "center",
#                     "lineHeightEm": 1.2,
#                     "initialTopPercentage": 60,
#                     "initialWidthPercentage": 90
#                 }}}}, # Inner event_info object end
#                 "footer": {{{{ # Inner footer object start
#                     "fontFamily": "Arial, sans-serif",
#                     "color": "#000000",
#                     "fontSizePx": 16,
#                     "fontWeight": "normal",
#                     "textAlign": "center",
#                     "lineHeightEm": 1.5,
#                     "initialTopPercentage": 90,
#                     "initialWidthPercentage": 95
#                 }}}} # Inner footer object end
#             }} # Outer JSON end
#             """
#             print("   🤖 Envoi à GPT-4o pour styles de texte (avec image générée et contenu réel)...")
#             # Utilise la nouvelle méthode avec réessais
#             output = self._replicate_run_with_retries(
#                 "openai/gpt-4o",
#                 input_data={
#                     "prompt": full_prompt_text,
#                     "image_input": [generated_image_url],
#                     "max_completion_tokens": 1500,
#                     "temperature": 0.7
#                 },
#                 timeout=REPLICATE_TIMEOUT
#             )
#             suggestions_str = "".join(output)
#             print(f"   ✅ Suggestions reçues: {len(suggestions_str)} caractères. Aperçu: {suggestions_str[:200]}...")

#             try:
#                 suggestions = json.loads(suggestions_str)
#                 # Handle cases where GPT-4o wraps JSON in markdown
#                 if isinstance(suggestions, str) and suggestions.startswith("```json") and suggestions.endswith("```"):
#                     suggestions = json.loads(suggestions.strip("```json\n").strip("```"))
#             except json.JSONDecodeError:
#                 print(f"   ⚠️ GPT-4o n'a pas retourné un JSON valide. Tentative de correction ou d'extraction.")
#                 json_start = suggestions_str.find('{')
#                 json_end = suggestions_str.rfind('}')
#                 if json_start != -1 and json_end != -1:
#                     try:
#                         suggestions = json.loads(suggestions_str[json_start:json_end+1])
#                     except Exception as e:
#                         print(f"   ❌ Échec de la correction JSON: {e}")
#                         suggestions = {}
#                 else:
#                     suggestions = {}

#             return suggestions

#         except Exception as e:
#             print(f"   ❌ Erreur dans suggest_text_styles_for_flyer: {e}")
#             print(f"   📋 Traceback: {traceback.format_exc()}")
#             raise

#     def generate_textless_flyer_background(self, style_description, content_data):
#         print("🖼️ [Étape 2/3] Début génération image de fond sans texte avec Imagen...")

#         # Formater les descriptions abstraites des longueurs de texte basées sur la longueur réelle du contenu
#         headline_length_desc = "a short, prominent heading" if len(content_data.get('headline1', '')) < 25 else "a medium-length, multi-line prominent heading"
#         description_length_desc = "a concise, short paragraph" if len(content_data.get('short_description', '')) < 150 else "a detailed, longer multi-line paragraph"
#         event_info_length_desc = "a single line of important details"
#         footer_info_length_desc = "one to two lines of contact information"

#         # CONSTRUIT LE PROMPT IMAGEN AVEC DES DESCRIPTIONS ABSTRAITES DES ZONES DE TEXTE
#         imagen_prompt = f"""
#         Generate a highly detailed and artistic flyer background in a vertical 9:16 aspect ratio.
#         The visual style and atmosphere should be: {style_description}

#         ⚠️ CRITICAL INSTRUCTION:
#         DO NOT generate any text, letters, numbers, writing, words, symbols, glyphs, or anything that resembles text or typography.

#         The image must be:
#         - Fully graphical and artistic,
#         - WITHOUT ANY visible or hidden text or shapes that look like placeholders or banners,
#         - NO logos, no fake UI, no watermarks, no labels, no icons, no boxes for text.

#         🧠 Imagine that this flyer will have 4 blocks of information added later:
#         - A title,
#         - A paragraph of description,
#         - Event details (time and location),
#         - Contact information.

#         DO NOT include or imply these elements in the image. Instead, arrange the artistic composition to leave soft, natural zones that *could be used* for text overlay — but that look organic and part of the scene.

#         🎯 The image must feel complete and beautiful WITHOUT any indication that text should be placed somewhere. No banners, no scrolls, no outlines, no boxes.

#         ABSOLUTELY NO TEXT.
#         """

#         print(f"   📏 Longueur du prompt Imagen (purely artistic & text-aware via abstract zones): {len(imagen_prompt)} caractères")
#         print("   🚀 Envoi à Imagen 4 (Replicate) pour fond sans texte et text-aware...")

#         try:
#             # Utilise la nouvelle méthode avec réessais
#             output = self._replicate_run_with_retries(
#                 "google/imagen-4",
#                 input_data={
#                     "prompt": imagen_prompt,
#                     "aspect_ratio": "9:16",
#                     "output_format": "jpg",
#                     "safety_filter_level": "block_medium_and_above",
#                     # Négatif prompt EXTREAMEMENT renforcé pour éviter tout texte ou symbole
#                     "negative_prompt": "text, words, letters, numbers, typography, font, watermark, logo, symbol, unreadable text, garbled text, blurry text, bad typography, character, script, writing, hieroglyph, glyph, any textual element, text artifacts, corrupted text, latin text, arabic text, chinese text, japanese text, english text, any language text, inscription, sign, logo, brand, stamp, placeholder, text box, text field, rectangle, square, box, blank space for text, Lorem ipsum, banner, ribbon, scroll, label, badge, text bubble, speech bubble, blank form, form elements, table, chart, diagram, outline, border, shape, empty area with border, background with designated blank space for text, explicit text area, empty label, empty sign"
#                 },
#                 timeout=REPLICATE_TIMEOUT
#             )

#             image_url = None
#             if not output:
#                 raise Exception("Replicate returned empty response")

#             if isinstance(output, list) and output:
#                 image_url = output[0]
#                 print(f"   📋 URL extraite de liste: {image_url}")
#             elif isinstance(output, (str, FileOutput)):
#                 image_url = str(output)
#                 print(f"   📋 URL directe: {image_url}")

#             if not image_url:
#                 raise Exception(f"Could not extract URL from Replicate response. Output type: {type(output)}, content: {output}")

#             print(f"   ✅ Image de fond générée avec succès ! URL: {image_url}")
#             return image_url

#         except Exception as e:
#             print(f"   ❌ Erreur dans generate_textless_flyer_background: {e}")
#             print(f"   📋 Traceback: {traceback.format_exc()}")
#             raise

# # Initialisation du générateur
# try:
#     flyer_gen = FlyerGenerator(api_key_unused=None)
#     print("✅ Générateur initialisé avec succès")
# except Exception as e:
#     print(f"❌ ERREUR CRITIQUE lors de l'initialisation du générateur: {e}")
#     raise

# # --- ROUTES FLASK MODIFIÉES ---
# @app.route('/api/generate-flyer-from-prototype', methods=['POST'])
# def generate_flyer_from_prototype():
#     print("\n" + "="*80)
#     print("🚀 NOUVELLE REQUÊTE DE GÉNÉRATION API (Fond purement artistique + Styles Texte analysés)")
#     print("="*80)

#     try:
#         # === PHASE 1: RÉCEPTION ET VALIDATION ===
#         print("🔍 Phase 1: Validation des données reçues")

#         if 'image' not in request.files:
#             error_msg = "Aucun fichier 'image' dans la requête"
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 400

#         style_image_file = request.files['image']
#         print(f"   📁 Fichier reçu: {style_image_file.filename}")

#         if style_image_file.filename == '':
#             error_msg = "Nom de fichier vide"
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 400

#         style_image_bytes = style_image_file.read()
#         print(f"   📏 Taille du fichier: {len(style_image_bytes)} bytes")

#         if len(style_image_bytes) == 0:
#             error_msg = "Fichier image vide"
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 400

#         try:
#             Image.open(io.BytesIO(style_image_bytes))
#             print(f"   ✅ Image d'entrée valide (test PIL)")
#         except Exception as e:
#             error_msg = f"L'image fournie est invalide ou corrompue: {e}"
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 400
        
#         # Extraire toutes les données textuelles du formulaire (POUR GPT-4o Vision et initialisation frontend)
#         content_data = {
#             'headline1': request.form.get('headline1', 'Your Event Headline'),
#             'short_description': request.form.get('short_description', 'A brief description of your event, summarizing its purpose and key features.'),
#             'event_info': request.form.get('event_info', 'Date, Time, and Location'),
#             'footer_info': request.form.get('footer_info', 'Contact Info | Website | Phone')
#         }
#         print(f"   📝 Données textuelles reçues: {content_data}")


#         print("   ✅ Phase 1 terminée: Données valides")

#         # === PHASE 2: ANALYSE DE L'IMAGE D'ENTRÉE AVEC GPT-4o (via Replicate) ===
#         print("\n🔍 Phase 2: Analyse de l'image d'entrée avec GPT-4o (via Replicate)")
#         try:
#             style_description = flyer_gen.describe_image_style(style_image_bytes)
#             print("   ✅ Phase 2 terminée: Image analysée")
#         except Exception as e:
#             error_msg = f'Erreur lors de l\'analyse du style de l\'image par GPT-4o (via Replicate): {str(e)}'
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 500

#         # === PHASE 3: GÉNÉRATION DE L'IMAGE DE FOND SANS TEXTE ET PUREMENT ARTISTIQUE AVEC IMAGEN ===
#         print("\n🖼️ Phase 3: Génération de l'image de fond purement artistique avec Imagen 4")
#         try:
#             # Passe content_data à generate_textless_flyer_background pour les descriptions abstraites
#             flyer_background_image_url = flyer_gen.generate_textless_flyer_background(style_description, content_data)
#             print("   ✅ Phase 3 terminée: Image de fond générée")
#         except Exception as e:
#             error_msg = f'Erreur lors de la génération de l\'image de fond par Imagen (Replicate): {str(e)}'
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 500

#         # === NOUVELLE PHASE: SUGGESTION DE STYLES DE TEXTE AVEC GPT-4o VISION (sur l'image générée) ===
#         print("\n🎨 Nouvelle Phase: Suggestion de styles de texte avec GPT-4o VISION (sur l'image générée)")
#         try:
#             # Passage de content_data à suggest_text_styles_for_flyer
#             text_style_suggestions = flyer_gen.suggest_text_styles_for_flyer(style_description, flyer_background_image_url, content_data)
#             print("   ✅ Styles de texte suggérés basés sur l'image générée et le contenu réel")
#         except Exception as e:
#             error_msg = f'Erreur lors de la suggestion des styles de texte par GPT-4o Vision (via Replicate): {str(e)}'
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 500


#         # === PHASE FINALE: RÉPONSE AU CLIENT ===
#         print(f"\n✅ SUCCÈS COMPLET!")
#         print(f"   🎉 URL de l'image de fond (Replicate): {flyer_background_image_url}")
#         print("="*80 + "\n")

#         return jsonify({
#             'success': True,
#             'flyer_background_url': flyer_background_image_url,
#             'text_style_suggestions': text_style_suggestions,
#             'message': 'Image de fond et suggestions de style générées avec succès. Le texte doit être superposé côté client.'
#         })

#     except Exception as e:
#         print(f"\n❌ ERREUR FATALE DANS LA ROUTE PRINCIPALE:")
#         print(f"   🔥 Erreur: {e}")
#         print(f"   📋 Type: {type(e).__name__}")
#         print(f"   🗂️ Traceback complet:")
#         traceback.print_exc()
#         print("="*80 + "\n")

#         return jsonify({
#             'error': f"Une erreur interne est survenue sur le serveur: {str(e)}",
#             'error_type': type(e).__name__,
#             'debug_info_for_dev': "Vérifiez les logs du serveur pour plus de détails."
#         }), 500

# if __name__ == '__main__':
#     app.run(debug=True, port=5000)













###################################""
# FLYER-IA/flyer-ia/backend/app.py

# from flask import Flask, request, jsonify
# from flask_cors import CORS
# import openai
# import replicate
# from replicate.exceptions import ReplicateError
# from replicate.helpers import FileOutput
# from PIL import Image
# import io
# import base64
# import os
# from dotenv import load_dotenv
# import traceback
# import json
# # Removed 'requests' as it was only for Flux's potential use case

# load_dotenv()

# app = Flask(__name__)
# CORS(app, resources={r"/api/*": {"origins": "*"}})

# # --- CONFIGURATION ---
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

# if not OPENAI_API_KEY:
#     print("AVERTISSEMENT: OPENAI_API_KEY n'est pas défini. Les appels directs à l'API OpenAI pourraient échouer.")
# if not REPLICATE_API_TOKEN:
#     raise ValueError("ERREUR: La variable d'environnement REPLICATE_API_TOKEN n'est pas définie.")

# os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
# print("✅ Replicate/DALL-E 3 configuré") # Mise à jour du message

# # --- PARAMÈTRE GLOBAL DE TIMEOUT ---
# REPLICATE_TIMEOUT = 600 # secondes (10 minutes), très généreux

# class FlyerGenerator:
#     def __init__(self, api_key_unused):
#         try:
#             print("✅ FlyerGenerator initialisé (utilisation de Replicate pour tous les modèles)")
#         except Exception as e:
#             print(f"❌ Erreur initialisation FlyerGenerator: {e}")
#             raise

#     def describe_image_style(self, style_image_bytes):
#         print("🔍 [Étape 1/3] Début analyse de l'image d'entrée pour le style...")
        
#         try:
#             img_base64 = base64.b64encode(style_image_bytes).decode('utf-8')
#             image_url_for_replicate = f"data:image/jpeg;base64,{img_base64}"

#             prompt_for_gpt_description = """
#             Describe the visual style, color palette, atmosphere, and dominant elements of the provided image in detail. Focus on aspects relevant for generating a new image with a similar aesthetic. Be concise but comprehensive.
#             """

#             print("   🤖 Envoi à GPT-4o (via Replicate) pour description...")
#             output = replicate.run(
#                 "openai/gpt-4o",
#                 input={
#                     "prompt": prompt_for_gpt_description,
#                     "image_input": [image_url_for_replicate],
#                     "max_completion_tokens": 300,
#                     "temperature": 0.7
#                 },
#                 timeout=REPLICATE_TIMEOUT
#             )
#             description = "".join(output)
#             print(f"   ✅ Description reçue: {len(description)} caractères. Aperçu: {description[:100]}...")
#             return description

#         except Exception as e:
#             print(f"   ❌ Erreur dans describe_image_style: {e}")
#             print(f"   📋 Traceback: {traceback.format_exc()}")
#             raise

#     def suggest_text_styles_for_flyer(self, image_style_description, generated_image_url, content_data):
#         print("🎨 [Étape 3/3] Début suggestion de styles de texte en analysant l'image générée et le contenu...")
#         try:
#             # Formater le texte à inclure dans le prompt de GPT-4o Vision pour l'estimation de taille
#             headline_content = content_data.get('headline1', 'Headline')
#             description_content = content_data.get('short_description', 'A concise description of your event, summarizing its purpose or key features.')
#             event_info_content = content_data.get('event_info', 'Date, Time, and Location of the Event')
#             footer_info_content = content_data.get('footer_info', 'Contact Information, Website, and Phone Number')

#             # PROMPT DE GPT-4o VISION AMÉLIORÉ POUR LA QUALITÉ PROFESSIONNELLE ET LE CONTENU SPÉCIFIQUE
#             # ATTENTION: Toutes les accolades LITTÉRALES dans le JSON d'exemple doivent être doublées {{ et }}
#             full_prompt_text = f"""
#             Based on the following visual style description:
#             "{image_style_description}"

#             And **critically, based on the attached image (which is the generated flyer background)**, suggest a cohesive, **highly legible**, and **professionally balanced** text style palette for a vertical flyer with a **9:16 aspect ratio (e.g., a canvas of 360px width, 640px height)**. The goal is to perfectly integrate text as if designed by a professional graphic designer.

#             **Here is the actual text content that will be placed. Use this to determine optimal font sizes, line breaks, and overall space needed for each block:**
#             Headline: "{headline_content}"
#             Description: "{description_content}"
#             Event Details: "{event_info_content}"
#             Contact Info: "{footer_info_content}"

#             **CRITICAL REQUIREMENTS FOR OPTIMAL TEXT INTEGRATION:**
#             1.  **COLOR CONTRAST (HIGHEST PRIORITY):** Analyze the attached image. Determine its dominant light/dark areas and colors. Suggest text colors that provide **stark, undeniable contrast against the SPECIFIC BACKGROUND areas where text is placed.** Prioritize pure white (#FFFFFF) or pure black (#000000) for maximum legibility. If the image style suggests a vibrant color, ensure it still achieves very high contrast.
#             2.  **FONT SELECTION & DESIGN:** Choose font families that complement the visual style while remaining highly readable. Consider the overall elegance and professionalism.
#             3.  **FONT SIZE (`fontSizePx`):** Suggest pixel sizes that are perfectly scaled for the 360px width, ensuring all actual text content fits gracefully within the suggested `initialWidthPercentage` without truncation, and is clearly legible. The sizes should reflect a clear visual hierarchy (headline largest, footer smallest, etc.). **Consider the actual length of the text provided above when determining the optimal font size and potential line breaks.**
#             4.  **LINE HEIGHT (`lineHeightEm`):** Provide `lineHeightEm` for excellent vertical spacing within multi-line text blocks.
#             5.  **INITIAL POSITIONING (`initialTopPercentage`, `initialWidthPercentage`):**
#                 *   **Strategic Placement:** Analyze the attached image for clear, open, and less busy areas. Suggest `initialTopPercentage` and `initialWidthPercentage` values that position each text block in a visually prominent, uncluttered, and balanced way.
#                 *   **Avoid Graphic Conflicts:** Ensure text does NOT overlap with or get obscured by major graphic elements (like large moons, intricate buildings, or bright/dark transitions).
#                 *   **Visual Hierarchy & Flow:** Positions should create a natural reading flow (top-to-bottom) and visually distinct sections. Provide ample padding around text areas relative to the image edges.
#             6.  **TEXT HIERARCHY:** The font sizes and weights should clearly distinguish between headline, description, event details, and footer.

#             Provide your suggestions in a JSON format.

#             For each text type (headline, body, event_info, footer), suggest:
#             - `fontFamily`: (e.g., "Arial, sans-serif", "Roboto, sans-serif", "Open Sans, sans-serif", "Lato, sans-serif", "Merriweather, serif"). Prioritize common, legible web-safe or popular Google Fonts.
#             - `color`: (a HEX code,based on image analysis).
#             - `fontSizePx`: (a numerical value in pixels, perfectly scaled for 360px width).
#             - `fontWeight`: (e.g., "bold", "normal", "lighter", "500", "700").
#             - `textAlign`: (e.g., "center", "left", "right").
#             - `lineHeightEm`: (a numerical value for line-height, e.g., 1.1, 1.2, 1.4, 1.5).
#             - `initialTopPercentage`: (a number from 0 to 100).
#             - `initialWidthPercentage`: (a number from 50 to 95).

#             Example JSON structure (reflecting professional design principles):
#             {{ # Outer JSON start
#                 "headline": {{{{ # Inner headline object start
#                     "fontFamily": "Playfair Display, serif",
#                     "color": "#000000",
#                     "fontSizePx": 48,
#                     "fontWeight": "bold",
#                     "textAlign": "center",
#                     "lineHeightEm": 1.1,
#                     "initialTopPercentage": 8,
#                     "initialWidthPercentage": 90
#                 }}}}, # Inner headline object end
#                 "body": {{{{ # Inner body object start
#                     "fontFamily": "Roboto, sans-serif",
#                     "color": "#000000",
#                     "fontSizePx": 20,
#                     "fontWeight": "normal",
#                     "textAlign": "center",
#                     "lineHeightEm": 1.4,
#                     "initialTopPercentage": 25,
#                     "initialWidthPercentage": 85
#                 }}}}, # Inner body object end
#                 "event_info": {{{{ # Inner event_info object start
#                     "fontFamily": "Open Sans, sans-serif",
#                     "color": "#000000",
#                     "fontSizePx": 28,
#                     "fontWeight": "bold",
#                     "textAlign": "center",
#                     "lineHeightEm": 1.2,
#                     "initialTopPercentage": 60,
#                     "initialWidthPercentage": 90
#                 }}}}, # Inner event_info object end
#                 "footer": {{{{ # Inner footer object start
#                     "fontFamily": "Arial, sans-serif",
#                     "color": "#000000",
#                     "fontSizePx": 16,
#                     "fontWeight": "normal",
#                     "textAlign": "center",
#                     "lineHeightEm": 1.5,
#                     "initialTopPercentage": 90,
#                     "initialWidthPercentage": 95
#                 }}}} # Inner footer object end
#             }} # Outer JSON end
#             """
#             print("   🤖 Envoi à GPT-4o pour styles de texte (avec image générée et contenu réel)...")
#             output = replicate.run(
#                 "openai/gpt-4o",
#                 input={
#                     "prompt": full_prompt_text,
#                     # Correction ici: assurez-vous que generated_image_url est bien une chaîne (URL)
#                     "image_input": [generated_image_url], 
#                     "max_completion_tokens": 1500,
#                     "temperature": 0.7
#                 },
#                 timeout=REPLICATE_TIMEOUT
#             )
#             suggestions_str = "".join(output)
#             print(f"   ✅ Suggestions reçues: {len(suggestions_str)} caractères. Aperçu: {suggestions_str[:200]}...")

#             try:
#                 suggestions = json.loads(suggestions_str)
#                 # Handle cases where GPT-4o wraps JSON in markdown
#                 if isinstance(suggestions, str) and suggestions.startswith("```json") and suggestions.endswith("```"):
#                     suggestions = json.loads(suggestions.strip("```json\n").strip("```"))
#             except json.JSONDecodeError:
#                 print(f"   ⚠️ GPT-4o n'a pas retourné un JSON valide. Tentative de correction ou d'extraction.")
#                 json_start = suggestions_str.find('{')
#                 json_end = suggestions_str.rfind('}')
#                 if json_start != -1 and json_end != -1:
#                     try:
#                         suggestions = json.loads(suggestions_str[json_start:json_end+1])
#                     except Exception as e:
#                         print(f"   ❌ Échec de la correction JSON: {e}")
#                         suggestions = {}
#                 else:
#                     suggestions = {}

#             return suggestions

#         except Exception as e:
#             print(f"   ❌ Erreur dans suggest_text_styles_for_flyer: {e}")
#             print(f"   📋 Traceback: {traceback.format_exc()}")
#             raise

#     def generate_textless_flyer_background(self, style_description, content_data):
#         print("🖼️ [Étape 2/3] Début génération image de fond sans texte avec DALL-E 3...") # Mise à jour du message

#         # Formater les descriptions abstraites des longueurs de texte basées sur la longueur réelle du contenu
#         headline_length_desc = "a short, prominent heading" if len(content_data.get('headline1', '')) < 25 else "a medium-length, multi-line prominent heading"
#         description_length_desc = "a concise, short paragraph" if len(content_data.get('short_description', '')) < 150 else "a detailed, longer multi-line paragraph"
#         event_info_length_desc = "a single line of important details"
#         footer_info_length_desc = "one to two lines of contact information"

#         # CONSTRUIT LE PROMPT POUR DALL-E 3 AVEC DES DESCRIPTIONS ABSTRAITES DES ZONES DE TEXTE
#         dalle3_prompt = f"""
#         Generate a highly detailed and artistic flyer background in a vertical 2:3 aspect ratio.
#         The visual style and atmosphere should be: {style_description}

#         ⚠️ CRITICAL INSTRUCTION:
#         DO NOT generate any text, letters, numbers, writing, words, symbols, glyphs, or anything that resembles text or typography.

#         The image must be:
#         - Fully graphical and artistic,
#         - WITHOUT ANY visible or hidden text or shapes that look like placeholders or banners,
#         - NO logos, no fake UI, no watermarks, no labels, no icons, no boxes for text.

#         🧠 Imagine that this flyer will have 4 blocks of information added later:
#         - A title,
#         - A paragraph of description,
#         - Event details (time and location),
#         - Contact information.

#         DO NOT include or imply these elements in the image. Instead, arrange the artistic composition to leave soft, natural zones that *could be used* for text overlay — but that look organic and part of the scene. Ensure the layout subtly suggests areas for: a prominent top heading, a central descriptive paragraph, event details below that, and contact info at the very bottom.

#         🎯 The image must feel complete and beautiful WITHOUT any indication that text should be placed somewhere. No banners, no scrolls, no outlines, no boxes.

#         ABSOLUTELY NO TEXT.
#         """

#         print(f"   📏 Longueur du prompt DALL-E 3 (purely artistic & text-aware via abstract zones): {len(dalle3_prompt)} caractères")
#         print("   🚀 Envoi à DALL-E 3 (Replicate) pour fond sans texte et text-aware...") # Mise à jour du message

#         try:
#             output = replicate.run(
#                 "openai/dall-e-3", # <-- Changé pour DALL-E 3
#                 input={
#                     "prompt": dalle3_prompt,
#                     "aspect_ratio": "2:3", # <-- Corrigé pour utiliser un format supporté par DALL-E 3
#                     "output_format": "jpg",
#                     # "safety_filter_level": "block_medium_and_above", # DALL-E 3 n'a pas cet argument sur Replicate
#                     # Négatif prompt EXTREAMEMENT renforcé pour éviter tout texte ou symbole
#                     "negative_prompt": "text, words, letters, numbers, typography, font, watermark, logo, symbol, unreadable text, garbled text, blurry text, bad typography, character, script, writing, hieroglyph, glyph, any textual element, text artifacts, corrupted text, latin text, arabic text, chinese text, japanese text, english text, any language text, inscription, sign, logo, brand, stamp, placeholder, text box, text field, rectangle, square, box, blank space for text, Lorem ipsum, banner, ribbon, scroll, label, badge, text bubble, speech bubble, blank form, form elements, table, chart, diagram, outline, border, shape, empty area with border, background with designated blank space for text, explicit text area, empty label, empty sign, bad text, ugly text"
#                 },
#                 timeout=REPLICATE_TIMEOUT
#             )

#             image_url = None
#             if not output:
#                 raise Exception("Replicate returned empty response")

#             # --- CORRECTION ICI: Assurer que image_url est toujours une chaîne ---
#             if isinstance(output, list) and output:
#                 # Iterate through list to find a FileOutput or direct URL string
#                 for item in output:
#                     if isinstance(item, FileOutput):
#                         image_url = item.url
#                         break
#                     elif isinstance(item, str) and item.startswith("https://"):
#                         image_url = item
#                         break
#                 if not image_url and output: # Fallback if list has other types or is empty list of something
#                     image_url = str(output[0]) # Last resort, attempt conversion
#             elif isinstance(output, FileOutput):
#                 image_url = output.url # Directly get URL from FileOutput object
#             elif isinstance(output, str) and output.startswith("https://"):
#                 image_url = output # It's already a direct URL string
#             else:
#                 # Handle unexpected types, attempt string conversion as a last resort
#                 image_url = str(output)
#                 print(f"   ⚠️ Unexpected output type from DALL-E 3, attempting str() conversion: {type(output)}")
#             # --- FIN DE CORRECTION ---

#             if not image_url:
#                 raise Exception(f"Could not extract URL from Replicate response. Output type: {type(output)}, content: {output}")

#             print(f"   ✅ Image de fond générée avec succès ! URL: {image_url}")
#             return image_url

#         except Exception as e:
#             print(f"   ❌ Erreur dans generate_textless_flyer_background: {e}")
#             print(f"   📋 Traceback: {traceback.format_exc()}")
#             raise

#     # Removed all helper functions for text rendering, as Flux is no longer used for final text rendering


# # Initialisation du générateur
# try:
#     flyer_gen = FlyerGenerator(api_key_unused=None)
#     print("✅ Générateur initialisé avec succès")
# except Exception as e:
#     print(f"❌ ERREURE CRITIQUE lors de l'initialisation du générateur: {e}")
#     raise

# # --- ROUTES FLASK MODIFIÉES ---
# @app.route('/api/generate-flyer-from-prototype', methods=['POST'])
# def generate_flyer_from_prototype():
#     print("\n" + "="*80)
#     print("🚀 NOUVELLE REQUÊTE DE GÉNÉRATION API (Fond purement artistique + Styles Texte analysés)")
#     print("="*80)

#     try:
#         # === PHASE 1: RÉCEPTION ET VALIDATION ===
#         print("🔍 Phase 1: Validation des données reçues")

#         if 'image' not in request.files:
#             error_msg = "Aucun fichier 'image' dans la requête"
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 400

#         style_image_file = request.files['image']
#         print(f"   📁 Fichier reçu: {style_image_file.filename}")

#         if style_image_file.filename == '':
#             error_msg = "Nom de fichier vide"
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 400

#         style_image_bytes = style_image_file.read()
#         print(f"   📏 Taille du fichier: {len(style_image_bytes)} bytes")

#         if len(style_image_bytes) == 0:
#             error_msg = "Fichier image vide"
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 400

#         try:
#             Image.open(io.BytesIO(style_image_bytes))
#             print(f"   ✅ Image d'entrée valide (test PIL)")
#         except Exception as e:
#             error_msg = f"L'image fournie est invalide ou corrompue: {e}"
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 400
        
#         # Extraire toutes les données textuelles du formulaire (POUR GPT-4o Vision et initialisation frontend)
#         content_data = {
#             'headline1': request.form.get('headline1', 'Your Event Headline'),
#             'short_description': request.form.get('short_description', 'A brief description of your event, summarizing its purpose and key features.'),
#             'event_info': request.form.get('event_info', 'Date, Time, and Location'),
#             'footer_info': request.form.get('footer_info', 'Contact Info | Website | Phone')
#         }
#         print(f"   📝 Données textuelles reçues: {content_data}")


#         print("   ✅ Phase 1 terminée: Données valides")

#         # === PHASE 2: ANALYSE DE L'IMAGE D'ENTRÉE AVEC GPT-4o (via Replicate) ===
#         print("\n🔍 Phase 2: Analyse de l'image d'entrée avec GPT-4o (via Replicate)")
#         try:
#             style_description = flyer_gen.describe_image_style(style_image_bytes)
#             print("   ✅ Phase 2 terminée: Image analysée")
#         except Exception as e:
#             error_msg = f'Erreur lors de l\'analyse du style de l\'image par GPT-4o (via Replicate): {str(e)}'
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 500

#         # === PHASE 3: GÉNÉRATION DE L'IMAGE DE FOND SANS TEXTE ET PUREMENT ARTISTIQUE AVEC DALL-E 3 ===
#         print("\n🖼️ Phase 3: Génération de l'image de fond purement artistique avec DALL-E 3") # Mise à jour du message
#         try:
#             # Passe content_data à generate_textless_flyer_background pour les descriptions abstraites
#             flyer_background_image_url = flyer_gen.generate_textless_flyer_background(style_description, content_data)
#             print("   ✅ Phase 3 terminée: Image de fond générée")
#         except Exception as e:
#             error_msg = f'Erreur lors de la génération de l\'image de fond par DALL-E 3 (Replicate): {str(e)}' # Mise à jour du message
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 500

#         # === NOUVELLE PHASE: SUGGESTION DE STYLES DE TEXTE AVEC GPT-4o VISION (sur l'image générée) ===
#         print("\n🎨 Nouvelle Phase: Suggestion de styles de texte avec GPT-4o VISION (sur l'image générée)")
#         try:
#             # Passage de content_data à suggest_text_styles_for_flyer
#             text_style_suggestions = flyer_gen.suggest_text_styles_for_flyer(style_description, flyer_background_image_url, content_data)
#             print("   ✅ Styles de texte suggérés basés sur l'image générée et le contenu réel")
#         except Exception as e:
#             error_msg = f'Erreur lors de la suggestion des styles de texte par GPT-4o Vision (via Replicate): {str(e)}'
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 500


#         # === PHASE FINALE: RÉPONSE AU CLIENT ===
#         print(f"\n✅ SUCCÈS COMPLET!")
#         print(f"   🎉 URL de l'image de fond (Replicate): {flyer_background_image_url}")
#         print("="*80 + "\n")

#         return jsonify({
#             'success': True,
#             'flyer_background_url': flyer_background_image_url,
#             'text_style_suggestions': text_style_suggestions,
#             'message': 'Image de fond et suggestions de style générées avec succès. Le texte doit être superposé côté client.'
#         })

#     except Exception as e:
#         print(f"\n❌ ERREUR FATALE DANS LA ROUTE PRINCIPALE:")
#         print(f"   🔥 Erreur: {e}")
#         print(f"   📋 Type: {type(e).__name__}")
#         print(f"   🗂️ Traceback complet:")
#         traceback.print_exc()
#         print("="*80 + "\n")

#         return jsonify({
#             'error': f"Une erreur interne est survenue sur le serveur: {str(e)}",
#             'error_type': type(e).__name__,
#             'debug_info_for_dev': "Vérifiez les logs du serveur pour plus de détails."
#         }), 500

# if __name__ == '__main__':
#     app.run(debug=True, port=5000)






#########################################""



























# # FLYER-IA/flyer-ia/backend/app.py fonctionnele

# from flask import Flask, request, jsonify
# from flask_cors import CORS
# import openai
# import replicate
# from replicate.exceptions import ReplicateError
# from replicate.helpers import FileOutput
# from PIL import Image
# import io
# import base64
# import os
# from dotenv import load_dotenv
# import traceback
# import json

# load_dotenv()

# app = Flask(__name__)
# CORS(app, resources={r"/api/*": {"origins": "*"}})

# # --- CONFIGURATION ---
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

# if not OPENAI_API_KEY:
#     print("AVERTISSEMENT: OPENAI_API_KEY n'est pas défini. Les appels directs à l'API OpenAI pourraient échouer.")
# if not REPLICATE_API_TOKEN:
#     raise ValueError("ERREUR: La variable d'environnement REPLICATE_API_TOKEN n'est pas définie.")

# os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
# print("✅ Replicate/Imagen configuré")

# # --- PARAMÈTRE GLOBAL DE TIMEOUT ---
# # Augmentez la valeur si les timeouts persistent. 600 secondes (10 minutes) est très généreux.
# REPLICATE_TIMEOUT = 600 # secondes

# class FlyerGenerator:
#     def __init__(self, api_key_unused):
#         try:
#             print("✅ FlyerGenerator initialisé (utilisation de Replicate pour tous les modèles)")
#         except Exception as e:
#             print(f"❌ Erreur initialisation FlyerGenerator: {e}")
#             raise

#     def describe_image_style(self, style_image_bytes):
#         print("🔍 [Étape 1/3] Début analyse de l'image d'entrée...")
        
#         # --- RECOMMANDATION : Redimensionner l'image si trop grande avant d'envoyer ---
#         # Cette partie est plus avancée et nécessiterait des librairies comme Pillow (PIL)
#         # pour la gestion d'images. Pour l'instant, c'est une recommandation.
#         # Vous pouvez vérifier la taille de style_image_bytes. S'il est > quelques MB,
#         # il faudrait le compresser ou le redimensionner côté client/backend.
#         # Exemple basique de relecture pour diagnostics:
#         try:
#             img = Image.open(io.BytesIO(style_image_bytes))
#             print(f"   Image d'entrée (PIL info): {img.format}, {img.size}, {len(style_image_bytes)/1024:.2f} KB")
#             # Si vous avez besoin de redimensionner (nécessite PIL installée):
#             # max_dim = 1024 # px
#             # if img.width > max_dim or img.height > max_dim:
#             #     img.thumbnail((max_dim, max_dim), Image.LANCZOS)
#             #     new_img_byte_arr = io.BytesIO()
#             #     img.save(new_img_byte_arr, format=img.format if img.format else 'JPEG') # Conserve le format
#             #     style_image_bytes = new_img_byte_arr.getvalue()
#             #     print(f"   Image redimensionnée à: {img.size}, {len(style_image_bytes)/1024:.2f} KB")
#         except Exception as e:
#             print(f"   ⚠️ Impossible de lire l'image d'entrée avec PIL pour diagnostics: {e}")
#         # --- Fin recommandation ---


#         try:
#             img_base64 = base64.b64encode(style_image_bytes).decode('utf-8')
#             image_url_for_replicate = f"data:image/jpeg;base64,{img_base64}"

#             prompt_for_gpt_description = """
#             Describe the visual style, color palette, atmosphere, and dominant elements of the provided image in detail. Focus on aspects relevant for generating a new image with a similar aesthetic. Be concise but comprehensive.
#             """

#             print("   🤖 Envoi à GPT-4o (via Replicate) pour description...")
#             output = replicate.run(
#                 "openai/gpt-4o",
#                 input={
#                     "prompt": prompt_for_gpt_description,
#                     "image_input": [image_url_for_replicate],
#                     "max_completion_tokens": 300,
#                     "temperature": 0.7
#                 },
#                 timeout=REPLICATE_TIMEOUT # AJOUT DU TIMEOUT ICI
#             )
#             description = "".join(output)
#             print(f"   ✅ Description reçue: {len(description)} caractères. Aperçu: {description[:100]}...")
#             return description

#         except Exception as e:
#             print(f"   ❌ Erreur dans describe_image_style: {e}")
#             print(f"   📋 Traceback: {traceback.format_exc()}")
#             raise

#     # MODIFICATION: Garde 'content_data' pour GPT-4o Vision pour estimer la taille du texte
#     def suggest_text_styles_for_flyer(self, image_style_description, generated_image_url, content_data):
#         print("🎨 [Étape 2/3] Début suggestion de styles de texte en analysant l'image générée et le contenu...")
#         try:
#             # Formater le texte à inclure dans le prompt de GPT-4o Vision pour l'estimation de taille
#             headline_content = content_data.get('headline1', 'Headline')
#             description_content = content_data.get('short_description', 'A concise description of your event, summarizing its purpose or key features.')
#             event_info_content = content_data.get('event_info', 'Date, Time, and Location of the Event')
#             footer_info_content = content_data.get('footer_info', 'Contact Information, Website, and Phone Number')

#             # PROMPT DE GPT-4o VISION AMÉLIORÉ POUR LA QUALITÉ PROFESSIONNELLE ET LE CONTENU SPÉCIFIQUE
#             full_prompt_text = f"""
#             Based on the following visual style description:
#             "{image_style_description}"

#             And **critically, based on the attached image (which is the generated flyer background)**, suggest a cohesive, **highly legible**, and **professionally balanced** text style palette for a vertical flyer with a **9:16 aspect ratio (e.g., a canvas of 360px width, 640px height)**. The goal is to perfectly integrate text as if designed by a professional graphic designer.

#             **Here is the actual text content that will be placed. Use this to determine optimal font sizes, line breaks, and overall space needed for each block:**
#             Headline: "{headline_content}"
#             Description: "{description_content}"
#             Event Details: "{event_info_content}"
#             Contact Info: "{footer_info_content}"

#             **CRITICAL REQUIREMENTS FOR OPTIMAL TEXT INTEGRATION:**
#             1.  **COLOR CONTRAST (HIGHEST PRIORITY):** Analyze the attached image. Determine its dominant light/dark areas and colors. Suggest text colors that provide **stark, undeniable contrast against the SPECIFIC BACKGROUND areas where text is placed.** Prioritize pure white (#FFFFFF) or pure black (#000000) for maximum legibility. If the image style suggests a vibrant color, ensure it still achieves very high contrast.
#             2.  **FONT SELECTION & DESIGN:** Choose font families that complement the visual style while remaining highly readable. Consider the overall elegance and professionalism.
#             3.  **FONT SIZE (`fontSizePx`):** Suggest pixel sizes that are perfectly scaled for the 360px width, ensuring all actual text content fits gracefully within the suggested `initialWidthPercentage` without truncation, and is clearly legible. The sizes should reflect a clear visual hierarchy (headline largest, footer smallest, etc.). **Consider the actual length of the text provided above when determining the optimal font size and potential line breaks.**
#             4.  **LINE HEIGHT (`lineHeightEm`):** Provide `lineHeightEm` for excellent vertical spacing within multi-line text blocks.
#             5.  **INITIAL POSITIONING (`initialTopPercentage`, `initialWidthPercentage`):**
#                 *   **Strategic Placement:** Analyze the attached image for clear, open, and less busy areas. Suggest `initialTopPercentage` and `initialWidthPercentage` values that position each text block in a visually prominent, uncluttered, and balanced way.
#                 *   **Avoid Graphic Conflicts:** Ensure text does NOT overlap with or get obscured by major graphic elements (like large moons, buildings, intricate patterns, or bright/dark transitions).
#                 *   **Visual Hierarchy & Flow:** Positions should create a natural reading flow (top-to-bottom) and visually distinct sections. Provide ample padding around text areas relative to the image edges.
#             6.  **TEXT HIERARCHY:** The font sizes and weights should clearly distinguish between headline, description, event details, and footer.

#             Provide your suggestions in a JSON format.

#             For each text type (headline, body, event_info, footer), suggest:
#             - `fontFamily`: (e.g., "Arial, sans-serif", "Roboto, sans-serif", "Open Sans, sans-serif", "Lato, sans-serif", "Merriweather, serif"). Prioritize common, legible web-safe or popular Google Fonts.
#             - `color`: (a HEX code, #FFFFFF or #000000 are highly preferred for optimal contrast, based on image analysis).
#             - `fontSizePx`: (a numerical value in pixels, perfectly scaled for 360px width).
#             - `fontWeight`: (e.g., "bold", "normal", "lighter", "500", "700").
#             - `textAlign`: (e.g., "center", "left", "right").
#             - `lineHeightEm`: (a numerical value for line-height, e.g., 1.1, 1.2, 1.4, 1.5).
#             - `initialTopPercentage`: (a number from 0 to 100).
#             - `initialWidthPercentage`: (a number from 50 to 95).

#             Example JSON structure (reflecting professional design principles):
#             {{
#                 "headline": {{
#                     "fontFamily": "Playfair Display, serif",
#                     "color": "#000000",
#                     "fontSizePx": 48,
#                     "fontWeight": "bold",
#                     "textAlign": "center",
#                     "lineHeightEm": 1.1,
#                     "initialTopPercentage": 8,
#                     "initialWidthPercentage": 90
#                 }},
#                 "body": {{
#                     "fontFamily": "Roboto, sans-serif",
#                     "color": "#000000",
#                     "fontSizePx": 20,
#                     "fontWeight": "normal",
#                     "textAlign": "center",
#                     "lineHeightEm": 1.4,
#                     "initialTopPercentage": 25,
#                     "initialWidthPercentage": 85
#                 }},
#                 "event_info": {{
#                     "fontFamily": "Open Sans, sans-serif",
#                     "color": "#000000",
#                     "fontSizePx": 28,
#                     "fontWeight": "bold",
#                     "textAlign": "center",
#                     "lineHeightEm": 1.2,
#                     "initialTopPercentage": 60,
#                     "initialWidthPercentage": 90
#                 }},
#                 "footer": {{
#                     "fontFamily": "Arial, sans-serif",
#                     "color": "#000000",
#                     "fontSizePx": 16,
#                     "fontWeight": "normal",
#                     "textAlign": "center",
#                     "lineHeightEm": 1.5,
#                     "initialTopPercentage": 90,
#                     "initialWidthPercentage": 95
#                 }}
#             }}
#             """
#             print("   🤖 Envoi à GPT-4o pour styles de texte (avec image générée et contenu réel)...")
#             output = replicate.run(
#                 "openai/gpt-4o",
#                 input={
#                     "prompt": full_prompt_text,
#                     "image_input": [generated_image_url],
#                     "max_completion_tokens": 1500,
#                     "temperature": 0.7
#                 },
#                 timeout=REPLICATE_TIMEOUT # AJOUT DU TIMEOUT ICI
#             )
#             suggestions_str = "".join(output)
#             print(f"   ✅ Suggestions reçues: {len(suggestions_str)} caractères. Aperçu: {suggestions_str[:200]}...")

#             try:
#                 suggestions = json.loads(suggestions_str)
#                 if isinstance(suggestions, str) and suggestions.startswith("```json") and suggestions.endswith("```"):
#                     suggestions = json.loads(suggestions.strip("```json\n").strip("```"))
#             except json.JSONDecodeError:
#                 print(f"   ⚠️ GPT-4o n'a pas retourné un JSON valide. Tentative de correction ou d'extraction.")
#                 json_start = suggestions_str.find('{')
#                 json_end = suggestions_str.rfind('}')
#                 if json_start != -1 and json_end != -1:
#                     try:
#                         suggestions = json.loads(suggestions_str[json_start:json_end+1])
#                     except Exception as e:
#                         print(f"   ❌ Échec de la correction JSON: {e}")
#                         suggestions = {}
#                 else:
#                     suggestions = {}

#             return suggestions

#         except Exception as e:
#             print(f"   ❌ Erreur dans suggest_text_styles_for_flyer: {e}")
#             print(f"   📋 Traceback: {traceback.format_exc()}")
#             raise

#     # generate_textless_flyer_background reste le même que dans la dernière optimisation
#     # car il doit générer une image artistique PURE, sans aucune suggestion de texte ou de zones.
#     def generate_textless_flyer_background(self, style_description, content_data):
#         print("🖼️ [Étape 3/3] Début génération image de fond sans texte avec Imagen...")

#         # Formater les descriptions abstraites des longueurs de texte basées sur la longueur réelle du contenu
#         headline_length_desc = "a short, prominent heading" if len(content_data.get('headline1', '')) < 25 else "a medium-length, multi-line prominent heading"
#         description_length_desc = "a concise, short paragraph" if len(content_data.get('short_description', '')) < 150 else "a detailed, longer multi-line paragraph"
#         event_info_length_desc = "a single line of important details"
#         footer_info_length_desc = "one to two lines of contact information"

#         # CONSTRUIT LE PROMPT IMAGEN AVEC DES DESCRIPTIONS ABSTRAITES DES ZONES DE TEXTE
#         imagen_prompt = f"""
#         Create a professional vertical flyer background in a 9:16 aspect ratio.
#         The visual style and atmosphere should be: {style_description}

#         **CRITICAL REQUIREMENT: Generate a beautiful, artistic, and visually balanced flyer background. The image must be COMPLETELY FREE of any text, text-like shapes, text placeholders, or any empty zones that explicitly suggest text placement.**
#         **The composition should be a seamless and coherent artistic scene, NOT a template or a layout with designated blank areas or text forms.**

#         **The background should be composed to aesthetically accommodate the following types of information blocks:**
#         - At the top: Space for {headline_length_desc}.
#         - In the upper-middle area: Space for {description_length_desc}.
#         - In the lower-middle area: Space for {event_info_length_desc}.
#         - At the bottom: Space for {footer_info_length_desc}.

#         - Ensure prominent, distinct, and relatively plain or subtly textured areas suitable for these abstract information blocks. These areas must offer high contrast for text.
#         - **ABSOLUTELY AVOID placing any busy, ornate, dark, or obscuring graphic elements (like large moons, intricate buildings, or complex patterns) DIRECTLY within these implicitly planned information placement zones.** Graphic elements should be artistically arranged in the periphery or occupy less critical areas.
#         - The background must feel like a complete, polished flyer ready for text overlay, with all elements perfectly aligned to leave optimal space for information.

#         🔒 EXTREMELY IMPORTANT INSTRUCTIONS (PREVENTING ALL FORMS OF UNWANTED TEXT AND PLACEHOLDERS):
#         **DO NOT, UNDER ANY CIRCUMSTANCE, GENERATE ANY TEXT, WORDS, LETTERS, NUMBERS, SYMBOLS, GLYPHS, TYPOGRAPHY, WRITING, LOREM IPSUM, OR ANY FORM OF CHARACTER OR TEXTUAL ARTIFACT within the image, legible or otherwise.**
#         **DO NOT generate any rectangular blocks, rounded rectangles, squares, or lines that resemble text placeholders or text fields. NO BLANK BOXES FOR TEXT. NO OUTLINES OR SHAPES FOR TEXT.**
#         **The image must be purely graphical and ready for text overlay, COMPLETELY DEVOID OF ANY GENERATED TEXT OR TEXT-RELATED GRAPHIC ELEMENTS.**
#         **Ensure the background is a natural, artistic scene/pattern, not a template with empty boxes or implied text areas. Avoid banners, scrolls, labels, empty forms, or any elements that look like they are designed for text.**
#         """

#         print(f"   📏 Longueur du prompt Imagen (purely artistic & text-aware via abstract zones): {len(imagen_prompt)} caractères")
#         print("   🚀 Envoi à Imagen 4 (Replicate) pour fond sans texte et text-aware...")

#         try:
#             output = replicate.run(
#                 "google/imagen-4",
#                 input={
#                     "prompt": imagen_prompt,
#                     "aspect_ratio": "9:16",
#                     "output_format": "jpg",
#                     "safety_filter_level": "block_medium_and_above",
#                     # Négatif prompt EXTREAMEMENT renforcé pour éviter tout texte ou symbole
#                     "negative_prompt": "text, words, letters, numbers, typography, font, watermark, logo, symbol, unreadable text, garbled text, blurry text, bad typography, character, script, writing, hieroglyph, glyph, any textual element, text artifacts, corrupted text, latin text, arabic text, chinese text, japanese text, english text, any language text, inscription, sign, logo, brand, stamp, placeholder, text box, text field, rectangle, square, box, blank space for text, Lorem ipsum, banner, ribbon, scroll, label, badge, text bubble, speech bubble, blank form, form elements, table, chart, diagram, outline, border, shape, empty area with border, background with designated blank space for text, explicit text area, empty label, empty sign"
#                 },
#                 timeout=REPLICATE_TIMEOUT # AJOUT DU TIMEOUT ICI
#             )

#             image_url = None
#             if not output:
#                 raise Exception("Replicate returned empty response")

#             if isinstance(output, list) and output:
#                 image_url = output[0]
#                 print(f"   📋 URL extraite de liste: {image_url}")
#             elif isinstance(output, (str, FileOutput)):
#                 image_url = str(output)
#                 print(f"   📋 URL directe: {image_url}")

#             if not image_url:
#                 raise Exception(f"Could not extract URL from Replicate response. Output type: {type(output)}, content: {output}")

#             print(f"   ✅ Image de fond générée avec succès ! URL: {image_url}")
#             return image_url

#         except Exception as e:
#             print(f"   ❌ Erreur dans generate_textless_flyer_background: {e}")
#             print(f"   📋 Traceback: {traceback.format_exc()}")
#             raise


# # Initialisation du générateur
# try:
#     flyer_gen = FlyerGenerator(api_key_unused=None)
#     print("✅ Générateur initialisé avec succès")
# except Exception as e:
#     print(f"❌ ERREUR CRITIQUE lors de l'initialisation du générateur: {e}")
#     raise

# # --- ROUTES FLASK MODIFIÉES ---
# @app.route('/api/generate-flyer-from-prototype', methods=['POST'])
# def generate_flyer_from_prototype():
#     print("\n" + "="*80)
#     print("🚀 NOUVELLE REQUÊTE DE GÉNÉRATION API (Fond purement artistique + Styles Texte analysés sur fond)")
#     print("="*80)

#     try:
#         # === PHASE 1: RÉCEPTION ET VALIDATION ===
#         print("🔍 Phase 1: Validation des données reçues")

#         if 'image' not in request.files:
#             error_msg = "Aucun fichier 'image' dans la requête"
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 400

#         style_image_file = request.files['image']
#         print(f"   📁 Fichier reçu: {style_image_file.filename}")

#         if style_image_file.filename == '':
#             error_msg = "Nom de fichier vide"
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 400

#         style_image_bytes = style_image_file.read()
#         print(f"   📏 Taille du fichier: {len(style_image_bytes)} bytes")

#         if len(style_image_bytes) == 0:
#             error_msg = "Fichier image vide"
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 400

#         try:
#             Image.open(io.BytesIO(style_image_bytes))
#             print(f"   ✅ Image d'entrée valide (test PIL)")
#         except Exception as e:
#             error_msg = f"L'image fournie est invalide ou corrompue: {e}"
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 400
        
#         # Extraire toutes les données textuelles du formulaire (POUR GPT-4o Vision et initialisation frontend)
#         content_data = {
#             'headline1': request.form.get('headline1', ''),
#             'short_description': request.form.get('short_description', ''),
#             'event_info': request.form.get('event_info', ''),
#             'footer_info': request.form.get('footer_info', '')
#         }
#         print(f"   📝 Données textuelles reçues: {content_data}")


#         print("   ✅ Phase 1 terminée: Données valides")

#         # === PHASE 2: ANALYSE DE L'IMAGE D'ENTRÉE AVEC GPT-4o (via Replicate) ===
#         print("\n🔍 Phase 2: Analyse de l'image d'entrée avec GPT-4o (via Replicate)")
#         try:
#             style_description = flyer_gen.describe_image_style(style_image_bytes)
#             print("   ✅ Phase 2 terminée: Image analysée")
#         except Exception as e:
#             error_msg = f'Erreur lors de l\'analyse du style de l\'image par GPT-4o (via Replicate): {str(e)}'
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 500

#         # === PHASE 3: GÉNÉRATION DE L'IMAGE DE FOND SANS TEXTE ET PUREMENT ARTISTIQUE AVEC IMAGEN ===
#         print("\n🖼️ Phase 3: Génération de l'image de fond purement artistique avec Imagen 4")
#         try:
#             # Passe content_data à generate_textless_flyer_background pour les descriptions abstraites
#             flyer_background_image_url = flyer_gen.generate_textless_flyer_background(style_description, content_data)
#             print("   ✅ Phase 3 terminée: Image de fond générée")
#         except Exception as e:
#             error_msg = f'Erreur lors de la génération de l\'image de fond par Imagen (Replicate): {str(e)}'
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 500

#         # === NOUVELLE PHASE CRUCIALE: SUGGESTION DE STYLES DE TEXTE AVEC GPT-4o VISION (sur l'image générée) ===
#         print("\n🎨 Nouvelle Phase: Suggestion de styles de texte avec GPT-4o VISION (sur l'image générée)")
#         try:
#             # Passage de content_data à suggest_text_styles_for_flyer
#             text_style_suggestions = flyer_gen.suggest_text_styles_for_flyer(style_description, flyer_background_image_url, content_data)
#             print("   ✅ Styles de texte suggérés basés sur l'image générée et le contenu réel")
#         except Exception as e:
#             error_msg = f'Erreur lors de la suggestion des styles de texte par GPT-4o Vision (via Replicate): {str(e)}'
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 500


#         # === PHASE FINALE: RÉPONSE AU CLIENT ===
#         print(f"\n✅ SUCCÈS COMPLET!")
#         print(f"   🎉 URL de l'image de fond (Replicate): {flyer_background_image_url}")
#         print("="*80 + "\n")

#         return jsonify({
#             'success': True,
#             'flyer_background_url': flyer_background_image_url,
#             'text_style_suggestions': text_style_suggestions,
#             'message': 'Image de fond et suggestions de style générées avec succès.'
#         })

#     except Exception as e:
#         print(f"\n❌ ERREUR FATALE DANS LA ROUTE PRINCIPALE:")
#         print(f"   🔥 Erreur: {e}")
#         print(f"   📋 Type: {type(e).__name__}")
#         print(f"   🗂️ Traceback complet:")
#         traceback.print_exc()
#         print("="*80 + "\n")

#         return jsonify({
#             'error': f"Une erreur interne est survenue sur le serveur: {str(e)}",
#             'error_type': type(e).__name__,
#             'debug_info_for_dev': "Vérifiez les logs du serveur pour plus de détails."
#         }), 500

# if __name__ == '__main__':
#     app.run(debug=True, port=5000)







































# # FLYER-IA/flyer-ia/backend/app.py

# from flask import Flask, request, jsonify
# from flask_cors import CORS
# import openai
# import replicate
# from replicate.exceptions import ReplicateError
# from replicate.helpers import FileOutput
# from PIL import Image
# import io
# import base64
# import os
# from dotenv import load_dotenv
# import traceback
# import json

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

# class FlyerGenerator:
#     def __init__(self, api_key):
#         try:
#             self.client = openai.OpenAI(api_key=api_key)
#             print("✅ FlyerGenerator initialisé")
#         except Exception as e:
#             print(f"❌ Erreur initialisation FlyerGenerator: {e}")
#             raise

#     def describe_image_style(self, style_image_bytes):
#         print("🔍 [Étape 1/3] Début analyse de l'image d'entrée...")
#         try:
#             img_base64 = base64.b64encode(style_image_bytes).decode('utf-8')

#             prompt_for_gpt = """
#             Describe the visual style, color palette, atmosphere, and dominant elements of the provided image in detail. Focus on aspects relevant for generating a new image with a similar aesthetic. Be concise but comprehensive.
#             """

#             print("   🤖 Envoi à GPT-4o pour description...")
#             response = self.client.chat.completions.create(
#                 model="gpt-4o",
#                 messages=[{
#                     "role": "user",
#                     "content": [
#                         {"type": "text", "text": prompt_for_gpt},
#                         {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
#                     ]
#                 }],
#                 max_tokens=300
#             )

#             description = response.choices[0].message.content
#             print(f"   ✅ Description reçue: {len(description)} caractères. Aperçu: {description[:100]}...")
#             return description

#         except Exception as e:
#             print(f"   ❌ Erreur dans describe_image_style: {e}")
#             print(f"   📋 Traceback: {traceback.format_exc()}")
#             raise

#     def suggest_text_styles_for_flyer(self, image_style_description, generated_image_url):
#         print("🎨 [Étape 2/3] Début suggestion de styles de texte en analysant l'image générée...")
#         try:
#             prompt_content = [
#                 {"type": "text", "text": f"""
#                 Based on the following visual style description:
#                 "{image_style_description}"

#                 And **critically, based on the attached image (which is the generated flyer background)**, suggest a cohesive and **highly legible** text style palette for a professional vertical flyer with a **9:16 aspect ratio (e.g., a canvas of 360px width, 640px height)**.

#                 **CRITICAL REQUIREMENTS FOR TEXT READABILITY, FIT, AND POSITIONING:**
#                 1.  **COLOR CONTRAST (HIGHEST PRIORITY):** Analyze the attached image. Determine its dominant light/dark areas and colors. Suggest text colors that provide **stark, undeniable contrast against THIS SPECIFIC BACKGROUND.** For example, if the background has light/gold tones, strongly suggest pure black (#000000). If it has dark/blue tones, strongly suggest pure white (#FFFFFF). Avoid subtle colors that blend in with the background.
#                 2.  **FONT SIZE (`fontSizePx`):** Sizes must ensure the entire provided content fits within the suggested `initialWidthPercentage` and without truncating vertically. Account for typical content lengths: 'headline' is usually 2-4 words, 'description' can be 2-4 sentences, 'event info' is a short line, 'footer' is 1-2 lines of contact.
#                 3.  **LINE HEIGHT (`lineHeightEm`):** Provide a `lineHeightEm` value (e.g., 1.2, 1.4) for good vertical spacing between lines for readability.
#                 4.  **INITIAL POSITIONING (`initialTopPercentage`, `initialWidthPercentage`):**
#                     *   **Analyze for Open Space:** Analyze the attached image for clear, open, and less busy areas where text can be placed without obscuring key graphic elements or being unreadable.
#                     *   **Logical Flow:** Ensure enough vertical space between sections and a logical reading order.
#                     *   `initialTopPercentage`: (a number from 0 to 100).
#                     *   `initialWidthPercentage`: (a number from 50 to 95, ensuring ample horizontal space for text, especially descriptions).

#                 Provide your suggestions in a JSON format.

#                 For each text type (headline, body, event_info, footer), suggest:
#                 - `fontFamily`: (e.g., "Arial, sans-serif", "Roboto, sans-serif", "Open Sans, sans-serif"). Prioritize common, legible web-safe fonts.
#                 - `color`: (a HEX code, #FFFFFF or #000000 are highly preferred for contrast, based on image analysis).
#                 - `fontSizePx`: (a numerical value in pixels, e.g., 48, 24, 18, 14).
#                 - `fontWeight`: (e.g., "bold", "normal", "lighter").
#                 - `textAlign`: (e.g., "center", "left", "right").
#                 - `lineHeightEm`: (a numerical value for line-height, e.g., 1.2, 1.4).
#                 - `initialTopPercentage`: (a number from 0 to 100).
#                     - **For Islamic/mosque themes, specifically target open sky areas, clear foregrounds, or less textured backgrounds. Avoid heavily textured or central object areas for primary text placement.**
#                 - `initialWidthPercentage`: (a number from 50 to 95).

#                 Example JSON structure (using high contrast colors and smart positioning):
#                 {{
#                     "headline": {{
#                         "fontFamily": "Playfair Display, serif",
#                         "color": "#000000",
#                         "fontSizePx": 48,
#                         "fontWeight": "bold",
#                         "textAlign": "center",
#                         "lineHeightEm": 1.1,
#                         "initialTopPercentage": 8,
#                         "initialWidthPercentage": 90
#                     }},
#                     "body": {{
#                         "fontFamily": "Roboto, sans-serif",
#                         "color": "#000000",
#                         "fontSizePx": 20,
#                         "fontWeight": "normal",
#                         "textAlign": "center",
#                         "lineHeightEm": 1.4,
#                         "initialTopPercentage": 25,
#                         "initialWidthPercentage": 85
#                     }},
#                     "event_info": {{
#                         "fontFamily": "Open Sans, sans-serif",
#                         "color": "#000000",
#                         "fontSizePx": 28,
#                         "fontWeight": "bold",
#                         "textAlign": "center",
#                         "lineHeightEm": 1.2,
#                         "initialTopPercentage": 60,
#                         "initialWidthPercentage": 90
#                     }},
#                     "footer": {{
#                         "fontFamily": "Arial, sans-serif",
#                         "color": "#000000",
#                         "fontSizePx": 16,
#                         "fontWeight": "normal",
#                         "textAlign": "center",
#                         "lineHeightEm": 1.5,
#                         "initialTopPercentage": 90,
#                         "initialWidthPercentage": 95
#                     }}
#                 }}
#                 """},
#                 {"type": "image_url", "image_url": {"url": generated_image_url}}
#             ]

#             print("   🤖 Envoi à GPT-4o pour styles de texte (avec image générée)...")
#             response = self.client.chat.completions.create(
#                 model="gpt-4o",
#                 messages=[{
#                     "role": "user",
#                     "content": prompt_content
#                 }],
#                 max_tokens=1000
#             )

#             suggestions_str = response.choices[0].message.content
#             print(f"   ✅ Suggestions reçues (aperçu): {suggestions_str[:200]}...")

#             try:
#                 suggestions = json.loads(suggestions_str)
#                 if isinstance(suggestions, str) and suggestions.startswith("```json") and suggestions.endswith("```"):
#                     suggestions = json.loads(suggestions.strip("```json\n").strip("```"))
#             except json.JSONDecodeError:
#                 print(f"   ⚠️ GPT-4o n'a pas retourné un JSON valide. Tentative de correction ou d'extraction.")
#                 json_start = suggestions_str.find('{')
#                 json_end = suggestions_str.rfind('}')
#                 if json_start != -1 and json_end != -1:
#                     try:
#                         suggestions = json.loads(suggestions_str[json_start:json_end+1])
#                     except Exception as e:
#                         print(f"   ❌ Échec de la correction JSON: {e}")
#                         suggestions = {}
#                 else:
#                     suggestions = {}

#             return suggestions

#         except Exception as e:
#             print(f"   ❌ Erreur dans suggest_text_styles_for_flyer: {e}")
#             print(f"   📋 Traceback: {traceback.format_exc()}")
#             raise

#     # MODIFICATION: Ne prend PLUS 'content_data' pour Imagen, juste la description du style
#     def generate_textless_flyer_background(self, style_description): # content_data n'est plus un paramètre
#         print("🖼️ [Étape 3/3] Début génération image de fond sans texte avec Imagen...")

#         # Formater le prompt d'Imagen pour être PUREMENT artistique et SANS AUCUNE FORME DE TEXTE IMPLICITE
#         imagen_prompt = f"""
#         Create a professional vertical flyer background in a 9:16 aspect ratio.
#         The visual style and atmosphere should be: {style_description}

#         **CRITICAL REQUIREMENT: Generate a beautiful, artistic, and visually balanced flyer background. The image must be COMPLETELY FREE of any text, text-like shapes, text placeholders, or any empty zones that explicitly suggest text placement.**
#         **The composition should be a seamless and coherent artistic scene, NOT a template or a layout with designated blank areas.**

#         - The background should be a unified artistic composition.
#         - **ABSOLUTELY DO NOT generate any distinct rectangular blocks, rounded rectangles, squares, bubbles, banners, ribbons, or any shapes/areas that explicitly resemble text fields, text boxes, or information placeholders.**
#         - The image should naturally provide some clear, less busy areas suitable for text overlay, without making these areas look like intentional blank spaces for text. Focus on the overall artistic quality.

#         🔒 EXTREMELY IMPORTANT INSTRUCTIONS (PREVENTING ALL FORMS OF UNWANTED TEXT AND PLACEHOLDERS):
#         **DO NOT, UNDER ANY CIRCUMSTANCE, GENERATE ANY TEXT, WORDS, LETTERS, NUMBERS, SYMBOLS, GLYPHS, TYPOGRAPHY, WRITING, LOREM IPSUM, OR ANY FORM OF CHARACTER OR TEXTUAL ARTIFACT within the image, legible or otherwise.**
#         **DO NOT generate any rectangular blocks, rounded rectangles, squares, or lines that resemble text placeholders or text fields. NO BLANK BOXES FOR TEXT.**
#         **The image must be purely graphical and ready for text overlay, COMPLETELY DEVOID OF ANY GENERATED TEXT OR TEXT-RELATED GRAPHIC ELEMENTS.**
#         **Ensure the background is a natural, artistic scene/pattern, not a template with empty boxes or implied text areas.**
#         """

#         print(f"   📏 Longueur du prompt Imagen (purely artistic & text-agnostic): {len(imagen_prompt)} caractères")
#         print("   🚀 Envoi à Imagen 4 (Replicate) pour fond sans texte et text-aware...")

#         try:
#             output = replicate.run(
#                 "google/imagen-4",
#                 input={
#                     "prompt": imagen_prompt,
#                     "aspect_ratio": "9:16",
#                     "output_format": "jpg",
#                     "safety_filter_level": "block_medium_and_above",
#                     # Négatif prompt EXTREAMEMENT renforcé pour éviter tout texte ou symbole
#                     "negative_prompt": "text, words, letters, numbers, typography, font, watermark, logo, symbol, unreadable text, garbled text, blurry text, bad typography, character, script, writing, hieroglyph, glyph, any textual element, text artifacts, corrupted text, latin text, arabic text, chinese text, japanese text, english text, any language text, inscription, sign, logo, brand, stamp, placeholder, text box, text field, rectangle, square, box, blank space for text, Lorem ipsum, banner, ribbon, scroll, label, badge, text bubble, speech bubble, blank form, form elements, table, chart, diagram"
#                 }
#             )
#             # output = openai.images.generate(
#             #     model="dall-e-3",
#             #     prompt=imagen_prompt,
#             #     n=1,
#             #     size="1024x1792",  # 9:16 aspect ratio
#             #     response_format="url",
#             #     quality="standard",
#             # )
#             # image_url = output.data[0].url

#             image_url = None
#             if not output:
#                 raise Exception("Replicate returned empty response")

#             if isinstance(output, list) and output:
#                 image_url = output[0]
#                 print(f"   📋 URL extraite de liste: {image_url}")
#             elif isinstance(output, (str, FileOutput)):
#                 image_url = str(output)
#                 print(f"   📋 URL directe: {image_url}")

#             if not image_url:
#                 raise Exception(f"Could not extract URL from Replicate response. Output type: {type(output)}, content: {output}")

#             print(f"   ✅ Image de fond générée avec succès ! URL: {image_url}")
#             return image_url

#         except Exception as e:
#             print(f"   ❌ Erreur dans generate_textless_flyer_background: {e}")
#             print(f"   📋 Traceback: {traceback.format_exc()}")
#             raise


# # Initialisation du générateur
# try:
#     flyer_gen = FlyerGenerator(api_key=OPENAI_API_KEY)
#     print("✅ Générateur initialisé avec succès")
# except Exception as e:
#     print(f"❌ ERREUR CRITIQUE lors de l'initialisation du générateur: {e}")
#     raise

# # --- ROUTES FLASK MODIFIÉES ---
# @app.route('/api/generate-flyer-from-prototype', methods=['POST'])
# def generate_flyer_from_prototype():
#     print("\n" + "="*80)
#     print("🚀 NOUVELLE REQUÊTE DE GÉNÉRATION API (Fond text-aware + Styles Texte analysés sur fond)")
#     print("="*80)

#     try:
#         # === PHASE 1: RÉCEPTION ET VALIDATION ===
#         print("🔍 Phase 1: Validation des données reçues")

#         if 'image' not in request.files:
#             error_msg = "Aucun fichier 'image' dans la requête"
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 400

#         style_image_file = request.files['image']
#         print(f"   📁 Fichier reçu: {style_image_file.filename}")

#         if style_image_file.filename == '':
#             error_msg = "Nom de fichier vide"
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 400

#         style_image_bytes = style_image_file.read()
#         print(f"   📏 Taille du fichier: {len(style_image_bytes)} bytes")

#         if len(style_image_bytes) == 0:
#             error_msg = "Fichier image vide"
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 400

#         try:
#             Image.open(io.BytesIO(style_image_bytes))
#             print(f"   ✅ Image d'entrée valide (test PIL)")
#         except Exception as e:
#             error_msg = f"L'image fournie est invalide ou corrompue: {e}"
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 400
        
#         # Extraire toutes les données textuelles du formulaire (pour GPT-4o Vision et initialisation frontend)
#         content_data = {
#             'headline1': request.form.get('headline1', ''),
#             'short_description': request.form.get('short_description', ''),
#             'event_info': request.form.get('event_info', ''),
#             'footer_info': request.form.get('footer_info', '')
#         }
#         print(f"   📝 Données textuelles reçues: {content_data}")


#         print("   ✅ Phase 1 terminée: Données valides")

#         # === PHASE 2: ANALYSE DE L'IMAGE D'ENTRÉE AVEC GPT-4o ===
#         print("\n🔍 Phase 2: Analyse de l'image d'entrée avec GPT-4o")
#         try:
#             style_description = flyer_gen.describe_image_style(style_image_bytes)
#             print("   ✅ Phase 2 terminée: Image analysée")
#         except Exception as e:
#             error_msg = f'Erreur lors de l\'analyse du style de l\'image par GPT-4o: {str(e)}'
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 500

#         # === PHASE 3: GÉNÉRATION DE L'IMAGE DE FOND SANS TEXTE ET PUREMENT ARTISTIQUE AVEC IMAGEN ===
#         print("\n🖼️ Phase 3: Génération de l'image de fond purement artistique avec Imagen 4")
#         try:
#             # IMPORTANT: Imagen ne reçoit PAS de données textuelles. Son prompt est agnostique au texte.
#             flyer_background_image_url = flyer_gen.generate_textless_flyer_background(style_description)
#             print("   ✅ Phase 3 terminée: Image de fond générée")
#         except Exception as e:
#             error_msg = f'Erreur lors de la génération de l\'image de fond par Imagen (Replicate): {str(e)}'
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 500

#         # === NOUVELLE PHASE CRUCIALE: SUGGESTION DE STYLES DE TEXTE AVEC GPT-4o VISION (sur l'image générée) ===
#         print("\n🎨 Nouvelle Phase: Suggestion de styles de texte avec GPT-4o VISION (sur l'image générée)")
#         try:
#             # GPT-4o Vision reçoit l'URL de l'image générée ET la description de style.
#             # Il DOIT aussi recevoir les données textuelles complètes pour estimer les tailles/positions.
#             text_style_suggestions = flyer_gen.suggest_text_styles_for_flyer(style_description, flyer_background_image_url)
#             print("   ✅ Styles de texte suggérés basés sur l'image générée")
#         except Exception as e:
#             error_msg = f'Erreur lors de la suggestion des styles de texte par GPT-4o Vision: {str(e)}'
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 500


#         # === PHASE FINALE: RÉPONSE AU CLIENT ===
#         print(f"\n✅ SUCCÈS COMPLET!")
#         print(f"   🎉 URL de l'image de fond (Replicate): {flyer_background_image_url}")
#         print("="*80 + "\n")

#         return jsonify({
#             'success': True,
#             'flyer_background_url': flyer_background_image_url,
#             'text_style_suggestions': text_style_suggestions,
#             'message': 'Image de fond et suggestions de style générées avec succès.'
#         })

#     except Exception as e:
#         print(f"\n❌ ERREUR FATALE DANS LA ROUTE PRINCIPALE:")
#         print(f"   🔥 Erreur: {e}")
#         print(f"   📋 Type: {type(e).__name__}")
#         print(f"   🗂️ Traceback complet:")
#         traceback.print_exc()
#         print("="*80 + "\n")

#         return jsonify({
#             'error': f"Une erreur interne est survenue sur le serveur: {str(e)}",
#             'error_type': type(e).__name__,
#             'debug_info_for_dev': "Vérifiez les logs du serveur pour plus de détails."
#         }), 500

# if __name__ == '__main__':
#     app.run(debug=True, port=5000)








############################################################################""



# # FLYER-IA/flyer-ia/backend/app.py

# from flask import Flask, request, jsonify # send_file n'est plus nécessaire car les fichiers sont servis par Replicate
# from flask_cors import CORS
# import openai 
# # requests n'est plus nécessaire car on ne télécharge pas l'image de Replicate pour la sauvegarder
# import replicate
# from replicate.exceptions import ReplicateError
# from replicate.helpers import FileOutput 
# # PIL, io, uuid ne sont plus nécessaires pour la gestion du résultat final (sauvegarde locale)
# # mais PIL et io peuvent être gardés si vous avez besoin de lire/traiter l'image d'ENTREE.
# from PIL import Image 
# import io 
# import base64
# import os
# # uuid n'est plus utilisé car on ne nomme pas de fichiers locaux pour les flyers générés
# # sys n'est plus utilisé car les vérifications critiques sont gérées par les exceptions Flask
# from dotenv import load_dotenv
# import traceback

# load_dotenv()

# app = Flask(__name__)
# # ATTENTION: '*' est très permissif. En production, remplacez par l'URL exacte de votre frontend déployé (ex: 'https://votre-frontend.vercel.app')
# CORS(app, resources={r"/api/*": {"origins": "*"}}) 

# # --- CONFIGURATION ---
# # Suppression des diagnostics de démarrage pour la production, car Vercel gère l'environnement.
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

# if not OPENAI_API_KEY:
#     # Utilisez une exception qui sera capturée par le FlaskErrorHandler si l'API est appelée
#     raise ValueError("ERREUR: La variable d'environnement OPENAI_API_KEY n'est pas définie.")
# if not REPLICATE_API_TOKEN:
#     raise ValueError("ERREUR: La variable d'environnement REPLICATE_API_TOKEN n'est pas définie.")

# os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
# print("✅ Replicate/Imagen configuré")

# # CORRECTION MAJEURE: Suppression de toute logique de création de dossier local ou de stockage
# # UPLOAD_FOLDER n'est plus nécessaire. Vous pouvez le supprimer ou le laisser sans l'utiliser.
# # if not os.path.exists(UPLOAD_FOLDER):
# #     os.makedirs(UPLOAD_FOLDER)
# # Ces lignes sont commentées car le système de fichiers Vercel est en lecture seule.

# class FlyerGenerator:
#     def __init__(self, api_key):
#         try:
#             self.client = openai.OpenAI(api_key=api_key)
#             print("✅ FlyerGenerator initialisé")
#         except Exception as e:
#             print(f"❌ Erreur initialisation FlyerGenerator: {e}")
#             raise # Remonter l'erreur pour la gestion Flask

#     def describe_image_style(self, style_image_bytes):
#         print("🔍 [Étape 1/2] Début analyse de l'image...")
        
#         try:
#             # Diagnostics utiles pour le débogage (peut être retiré en production)
#             # print(f"   📏 Taille de l'image: {len(style_image_bytes)} bytes")
#             # try:
#             #     test_image = Image.open(io.BytesIO(style_image_bytes))
#             #     print(f"   ✅ Image valide: {test_image.size}, format: {test_image.format}")
#             # except Exception as e:
#             #     print(f"   ⚠️ L'image d'entrée n'a pas pu être lue par PIL: {e}") # Non bloquant si GPT-4o peut la traiter
            
#             img_base64 = base64.b64encode(style_image_bytes).decode('utf-8')
#             # print(f"   ✅ Image encodée en base64: {len(img_base64)} caractères")
            
#             # CORRECTION: Revertir le prompt pour qu'il soit dynamique
#             prompt = """
#             The visual style is elegant and contemplative, blending refined Islamic architectural elements with celestial symbolism to evoke a serene yet festive nocturnal atmosphere. The composition is airy and balanced, featuring softly illuminated domes and slender minarets silhouetted against a twilight gradient sky. A stylized crescent moon, delicate and luminous, serves as a central visual anchor, subtly radiating a sense of spiritual elevation. The color palette is dominated by warm, muted tones—amber golds, deep indigos, and soft terracotta—layered with gentle highlights of pearl and ivory to create depth and sophistication. Ornamental patterns are used sparingly and with finesse, ensuring the overall aesthetic remains modern, dignified, and imbued with quiet reverence. This background sets the perfect tone for a prestigious evening celebration steeped in cultural richness and celestial harmony.
# """
            
#             print("   🤖 Envoi à GPT-4o pour description...")
#             response = self.client.chat.completions.create(
#                 model="gpt-4o",
#                 messages=[{
#                     "role": "user",
#                     "content": [
#                         {"type": "text", "text": prompt},
#                         {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
#                     ]
#                 }],
#                 max_tokens=300
#             )
            
#             description = response.choices[0].message.content
#             print(f"   ✅ Description reçue: {len(description)} caractères. Aperçu: {description[:100]}...")
#             return description
            
#         except Exception as e:
#             print(f"   ❌ Erreur dans describe_image_style: {e}")
#             print(f"   📋 Traceback: {traceback.format_exc()}")
#             raise

#     def generate_full_flyer_with_all_text(self, style_description, content_data):
#         print("🔍 [Étape 2/2] Début génération avec Imagen...")
        
#         try:
#             headline = content_data.get('headline1', '')
#             description = content_data.get('short_description', '')
#             event_info = content_data.get('event_info', '')
#             footer_info = content_data.get('footer_info', '')

#             print(f"   📝 Contenu à intégrer:")
#             print(f"      - Titre: {headline[:50]}{'...' if len(headline) > 50 else ''}")
#             print(f"      - Description: {description[:50]}{'...' if len(description) > 50 else ''}")
#             print(f"      - Événement: {event_info[:50]}{'...' if len(event_info) > 50 else ''}")
#             print(f"      - Footer: {footer_info[:50]}{'...' if len(footer_info) > 50 else ''}")

#             imagen_prompt = f"""Create a professional vertical flyer in a 9:16 aspect ratio.

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

# ❌ Absolutely no extra or unintended text, symbols, or unreadable artifacts in the image.
# """

#             print(f"   📏 Longueur du prompt: {len(imagen_prompt)} caractères")
#             print("   🚀 Envoi à Imagen 4 (Replicate)...")
            
#             output = replicate.run(
#                 "google/imagen-4",
#                 input={
#                     "prompt": imagen_prompt,
#                     "aspect_ratio": "9:16",
#                     "output_format": "jpg",
#                     "safety_filter_level": "block_medium_and_above",
#                     "negative_prompt": "unreadable text, garbled text, blurry text, bad typography"
#                 }
#             )

            
            
#             print(f"   📨 Type de réponse Imagen: {type(output)}")
#             print(f"   📋 Contenu réponse (extrait): {str(output)[:200]}...")
            
#             image_url = None
#             if not output: 
#                 raise Exception("Replicate returned empty response")
            
#             # Extraction de l'URL de l'image
#             if isinstance(output, list) and output: 
#                 image_url = output[0]
#                 print(f"   📋 URL extraite de liste: {image_url}")
#             elif isinstance(output, (str, FileOutput)): 
#                 image_url = str(output)
#                 print(f"   📋 URL directe: {image_url}")
            
#             if not image_url: 
#                 raise Exception(f"Could not extract URL from Replicate response. Output type: {type(output)}, content: {output}")
            
#             print(f"   ✅ Image générée avec succès ! URL: {image_url}")
#             return image_url # <-- C'est l'URL externe hébergée par Replicate
            
#         except Exception as e:
#             print(f"   ❌ Erreur dans generate_full_flyer_with_all_text: {e}")
#             print(f"   📋 Traceback: {traceback.format_exc()}")
#             raise

# # Initialisation du générateur
# try:
#     flyer_gen = FlyerGenerator(api_key=OPENAI_API_KEY)
#     print("✅ Générateur initialisé avec succès")
# except Exception as e:
#     print(f"❌ ERREUR CRITIQUE lors de l'initialisation du générateur: {e}")
#     # Ne pas sys.exit(1) ici pour permettre à Flask de démarrer et de renvoyer une erreur 500
#     # Cela permet à Vercel de mieux diagnostiquer le problème.
#     raise

# # --- ROUTES FLASK AVEC DIAGNOSTICS COMPLETS ---
# @app.route('/api/generate-flyer-from-prototype', methods=['POST'])
# def generate_flyer_from_prototype():
#     print("\n" + "="*80)
#     print("🚀 NOUVELLE REQUÊTE DE GÉNÉRATION API")
#     print("="*80)
    
#     try:
#         # === PHASE 1: RÉCEPTION ET VALIDATION ===
#         print("🔍 Phase 1: Validation des données reçues")
        
#         # Diagnostics de la requête
#         print(f"   📋 Méthode: {request.method}")
#         print(f"   📋 Content-Type: {request.content_type}")
#         print(f"   📋 Form keys: {list(request.form.keys())}")
#         print(f"   📋 Files keys: {list(request.files.keys())}")
        
#         if 'image' not in request.files: 
#             error_msg = "Aucun fichier 'image' dans la requête"
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 400

#         style_image_file = request.files['image']
#         print(f"   📁 Fichier reçu: {style_image_file.filename}")
#         print(f"   📏 Content-Type: {style_image_file.content_type}")
        
#         if style_image_file.filename == '':
#             error_msg = "Nom de fichier vide"
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 400
            
#         style_image_bytes = style_image_file.read()
#         print(f"   📏 Taille du fichier: {len(style_image_bytes)} bytes")
        
#         if len(style_image_bytes) == 0:
#             error_msg = "Fichier image vide"
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 400

#         # Test ouverture image d'entrée (peut être bloquant si l'image est corrompue)
#         try:
#             Image.open(io.BytesIO(style_image_bytes))
#             print(f"   ✅ Image d'entrée valide (test PIL)")
#         except Exception as e:
#             # Cette erreur doit être renvoyée au client pour une meilleure UX
#             error_msg = f"L'image fournie est invalide ou corrompue: {e}"
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 400

#         content_data = {
#             'headline1': request.form.get('headline1', ''),
#             'short_description': request.form.get('short_description', ''),
#             'event_info': request.form.get('event_info', ''),
#             'footer_info': request.form.get('footer_info', '')
#         }
#         print(f"   📝 Données textuelles reçues:")
#         for key, value in content_data.items():
#             print(f"      - {key}: {value[:50]}{'...' if len(value) > 50 else ''}")

#         if not any(content_data.values()) and not style_image_bytes: # Vérifier au moins une donnée significative
#             error_msg = "Aucun contenu (image ou texte) fourni. Veuillez au moins fournir une image."
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 400

#         print("   ✅ Phase 1 terminée: Données valides")

#         # === PHASE 2: ANALYSE DE L'IMAGE ===
#         print("\n🔍 Phase 2: Analyse de l'image avec GPT-4o")
#         try:
#             style_description = flyer_gen.describe_image_style(style_image_bytes)
#             print("   ✅ Phase 2 terminée: Image analysée")
#         except Exception as e:
#             error_msg = f'Erreur lors de l\'analyse du style de l\'image par GPT-4o: {str(e)}'
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 500

#         # === PHASE 3: GÉNÉRATION AVEC IMAGEN ===
#         print("\n🔍 Phase 3: Génération avec Imagen 4")
#         try:
#             # final_flyer_image_url contiendra directement l'URL de Replicate
#             final_flyer_image_url = flyer_gen.generate_full_flyer_with_all_text(style_description, content_data)
#             print("   ✅ Phase 3 terminée: Flyer généré")
#         except Exception as e:
#             error_msg = f'Erreur lors de la génération du flyer avec Imagen (Replicate): {str(e)}'
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 500
        
#         # === PAS DE PHASE 4 (téléchargement/sauvegarde locale), CAR SERVI DIRECTEMENT PAR REPLICATE ===
#         # Les lignes suivantes sont supprimées pour un déploiement Vercel avec Replicate:
#         # response = requests.get(final_flyer_image_url, timeout=30)
#         # final_flyer_image = Image.open(io.BytesIO(response.content))
#         # filename = f"flyer_{uuid.uuid4()}.png"
#         # final_flyer_image.save(filepath, 'PNG', quality=95)
#         # server_url = request.host_url.rstrip('/')
#         # flyer_url = f"{server_url}/flyers/{filename}"
        
#         # === PHASE FINALE: RÉPONSE AU CLIENT ===
#         # L'URL retournée est l'URL de Replicate directement
#         flyer_url_for_frontend = final_flyer_image_url
        
#         print(f"\n✅ SUCCÈS COMPLET!")
#         print(f"   🎉 URL finale du flyer (Replicate): {flyer_url_for_frontend}")
#         print("="*80 + "\n")
        
#         return jsonify({
#             'success': True,
#             'flyer_urls': [flyer_url_for_frontend],
#             'message': 'Flyer généré avec succès avec l\'IA et hébergé par Replicate.'
#         })

#     except Exception as e:
#         # Gérer toutes les erreurs non capturées pour renvoyer un JSON
#         print(f"\n❌ ERREUR FATALE DANS LA ROUTE PRINCIPALE:")
#         print(f"   🔥 Erreur: {e}")
#         print(f"   📋 Type: {type(e).__name__}")
#         print(f"   🗂️ Traceback complet:")
#         traceback.print_exc()
#         print("="*80 + "\n")
        
#         # S'assurer que le client reçoit toujours un JSON même pour les erreurs inattendues
#         return jsonify({
#             'error': f"Une erreur interne est survenue sur le serveur: {str(e)}",
#             'error_type': type(e).__name__,
#             'debug_info_for_dev': "Vérifiez les logs du serveur pour plus de détails."
#         }), 500

# # CORRECTION MAJEURE: Suppression de la route de service des fichiers locaux, car les images sont servies par Replicate.
# # @app.route('/flyers/<filename>')
# # def serve_flyer(filename):
# #     # ... (code précédent de cette route)
# #     pass # Laisser vide ou supprimer complètement

# # CORRECTION MAJEURE: Suppression du bloc de démarrage local pour le déploiement sur Vercel.
# # if __name__ == '__main__':
# #    # ... (code précédent de démarrage local)
# #    pass # Laisser vide ou supprimer complètement



# if __name__ == '__main__':
#     # Vous pouvez changer le port si 5000 est déjà utilisé
#     # app.run(debug=True, host='0.0.0.0', port=5000) 
#     app.run(debug=True, port=5000) 






















################################################################################################################################################""


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



