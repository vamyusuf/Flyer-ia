import flask
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import openai
import replicate
from replicate.exceptions import ReplicateError
from replicate.helpers import FileOutput
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io
from io import BytesIO
import base64
import os
from dotenv import load_dotenv
import traceback
import json
import time
import requests
import re # Importation nécessaire pour les expressions régulières

load_dotenv()

app = Flask(__name__)
# CORS for development and deployment (adjust origins as needed for production)
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:3000", "https://your-frontend-domain.com"]}})


# --- CONFIGURATION ---
# Assurez-vous que ces variables d'environnement sont définies
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

if not OPENAI_API_KEY:
    print("AVERTISSEMENT: OPENAI_API_KEY n'est pas défini. Les appels directs à l'API OpenAI pourraient échouer.")
if not REPLICATE_API_TOKEN:
    raise ValueError("ERREUR: La variable d'environnement REPLICATE_API_TOKEN n'est pas définie.")

# Replicate utilise REPLICATE_API_TOKEN de l'environnement, pas besoin de le définir ici si déjà en env
os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
print("✅ Replicate configuré.")

# --- PARAMÈTRE GLOBAL DE TIMEOUT ET RETRY ---
REPLICATE_TIMEOUT = 600 # secondes (10 minutes) pour les opérations longues comme Imagen

# Paramètres pour la logique de réessai
MAX_RETRIES = 5
INITIAL_RETRY_DELAY_SECONDS = 2

class IslamicFlyerGenerator:
    def __init__(self, api_key_unused):
        try:
            print("✅ IslamicFlyerGenerator initialisé.")
        except Exception as e:
            print(f"❌ Erreur initialisation IslamicFlyerGenerator: {e}")
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
                    current_delay *= 2 # Backoff exponentiel
                    if current_delay > 60: # Cap à 60 secondes
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

        raise ReplicateError(f"Échec de l'appel au modèle '{model_name}' après {max_retries} tentatives.")

    def extract_logo_colors_and_styles_with_gpt4o(self, logo_image_bytes):
        """
        Extrait les couleurs dominantes du logo et fournit une analyse de style générale
        avec GPT-4o, incluant des suggestions pour les couleurs d'arrière-plan Imagen.
        """
        print("🎨 Extraction des couleurs et styles du logo avec GPT-4o...")

        try:
            # Convertir l'image en base64 pour GPT-4o
            logo_base64 = base64.b64encode(logo_image_bytes).decode('utf-8')
            logo_data_url = f"data:image/png;base64,{logo_base64}"

            prompt = """
            Analyze this organization logo image and provide:

            1.  **COLOR EXTRACTION**: Extract the 5-8 most dominant and visually significant HEX colors from this logo. Focus on:
                -   Primary brand colors that define the organization's identity.
                -   Secondary colors that complement the design.
                -   Avoid pure black (#000000) or pure white (#FFFFFF) unless they are clearly intentional brand colors.
                -   Prefer rich, saturated colors that work well for Islamic-themed designs.
                -   Include both lighter and darker variations for design flexibility.

            2.  **LOGO DOMINANT COLOR**: Identify the single most dominant color from the extracted list (as HEX).

            3.  **READABLE TEXT COLORS**: Suggest 2-3 HEX colors from the extracted logo palette that would provide good contrast and readability for text placed on a flyer, especially considering potential light or dark backgrounds.

            4.  **IMAGEN COLOR DESCRIPTIONS**: For the colors identified (both extracted and suggested Islamic palette), provide **natural language descriptions** (e.g., "deep forest green", "vibrant emerald", "warm gold", "sky blue", "subtle beige"). These will be used to instruct an image generation AI about colors, *without using HEX codes*. These descriptions should be short and evocative.

            5.  **ISLAMIC PALETTE SUGGESTIONS**: Beyond the logo colors, suggest 2-3 additional HEX colors that are culturally compatible with Islamic design (e.g., specific greens, golds, blues, browns) and would harmonize with the logo's palette.

            6.  **DESIGN ANALYSIS**: Analyze the logo's visual characteristics:
                -   Overall style (modern, traditional, elegant, bold, etc.)
                -   Typography style if text is present
                -   Visual weight and balance
                -   Cultural appropriateness for Islamic events.

            7.  **BACKGROUND COLOR SUGGESTIONS (for Imagen/AI Image Generation)**: Based on the logo's colors, style, and general Islamic aesthetics, suggest specific HEX codes for an Islamic flyer's *generated background image*. These should be harmonious with the logo but suitable for a decorative background. Suggest a dominant background color and 1-2 complementary accent colors for gradients or subtle patterns *within the generated image*.

            Provide your response in this exact JSON format. DO NOT include any other text, markdown, or explanation outside the JSON. Ensure all color values are valid HEX codes (e.g., "#RRGGBB").

            {
                "extracted_colors": ["#RRGGBB", "#RRGGBB", "#RRGGBB", "#RRGGBB", "#RRGGBB"],
                "logo_dominant_color": "#RRGGBB",
                "readable_text_colors": ["#RRGGBB", "#RRGGBB"],
                "imagen_color_descriptions": {
                    "dominant_bg": "description",
                    "complementary_bg_accents": ["description1", "description2"],
                    "extracted_logo_colors": ["description1", "description2", "description3"]
                },
                "islamic_palette_suggestions": ["#RRGGBB", "#RRGGBB", "#RRGGBB"],
                "color_analysis": {
                    "primary_color": "#RRGGBB",
                    "secondary_color": "#RRGGBB",
                    "accent_color": "#RRGGBB"
                },
                "design_recommendations": {
                    "headline_colors": ["#RRGGBB", "#RRGGBB"],
                    "body_text_colors": ["#RRGGBB", "#RRGGBB"],
                    "islamic_compatible_colors": ["#RRGGBB", "#RRGGBB", "#RRGGBB"]
                },
                "logo_style_analysis": {
                    "style_type": "modern/traditional/elegant/bold",
                    "visual_weight": "light/medium/heavy",
                    "recommended_text_style": "serif/sans-serif/decorative"
                },
                "ai_suggested_background_colors": {
                    "dominant_background_color": "#RRGGBB",
                    "complementary_background_accents": ["#RRGGBB", "#RRGGBB"]
                }
            }

            Focus on extracting colors that will create beautiful, professional Islamic-themed flyers.
            """

            print("   🤖 Envoi à GPT-4o pour analyse du logo...")
            output = self._replicate_run_with_retries(
                "openai/gpt-4o",
                input_data={
                    "prompt": prompt,
                    "image_input": [logo_data_url],
                    "max_completion_tokens": 1000,
                    "temperature": 0.3
                },
                timeout=REPLICATE_TIMEOUT
            )

            response_str = "".join(output)
            print(f"   ✅ Réponse GPT-4o reçue: {len(response_str)} caractères")

            try:
                # Tente de nettoyer la réponse si elle contient du markdown JSON
                if response_str.strip().startswith("```json"):
                    response_str = response_str.strip("```json\n").strip("```")

                analysis = json.loads(response_str)

                # Validation basique des données
                if not isinstance(analysis, dict) or 'extracted_colors' not in analysis:
                    raise ValueError("Format de réponse invalide ou données manquantes.")

                # S'assurer que imagen_color_descriptions existe ou ajouter un défaut
                if 'imagen_color_descriptions' not in analysis:
                    print("   ⚠️ 'imagen_color_descriptions' manquant, ajout des valeurs par défaut.")
                    analysis['imagen_color_descriptions'] = self._get_default_logo_analysis()['imagen_color_descriptions']


                print(f"   ✅ {len(analysis['extracted_colors'])} couleurs extraites avec GPT-4o: {analysis['extracted_colors']}")

                return analysis

            except json.JSONDecodeError as e:
                print(f"   ⚠️ Erreur de parsing JSON pour l'analyse du logo: {e}")
                print(f"   Réponse GPT-4o brute qui a échoué: \n{response_str[:500]}...") # Log part of the failing response
                return self._get_default_logo_analysis()

        except Exception as e:
            print(f"   ❌ Erreur lors de l'analyse du logo avec GPT-4o: {e}")
            print(f"   📋 Traceback: {traceback.format_exc()}")
            return self._get_default_logo_analysis()


    def _get_default_logo_analysis(self):
        """Analyse par défaut si GPT-4o échoue"""
        print("   ⚠️ Utilisation de l'analyse de logo par défaut.")
        return {
            "extracted_colors": ["#1B4332", "#2D6A4F", "#40916C", "#D4AF37", "#8B4513"],
            "logo_dominant_color": "#2D6A4F",
            "readable_text_colors": ["#D4AF37", "#40916C"],
            "imagen_color_descriptions": { # Default descriptions for Imagen
                "dominant_bg": "deep dark blue",
                "complementary_bg_accents": ["dark forest green", "emerald green"],
                "extracted_logo_colors": ["deep green", "teal green", "light green", "golden yellow", "brown"]
            },
            "islamic_palette_suggestions": ["#1B4332", "#2D6A4F", "#D4AF37"],
            "color_analysis": {
                "primary_color": "#1B4332",
                "secondary_color": "#2D6A4F",
                "accent_color": "#D4AF37"
            },
            "design_recommendations": {
                "headline_colors": ["#1B4332", "#D4AF37"],
                "body_text_colors": ["#2D6A4F", "#40916C"],
                "islamic_compatible_colors": ["#1B4332", "#2D6A4F", "#D4AF37"]
            },
            "logo_style_analysis": {
                "style_type": "traditional",
                "visual_weight": "medium",
                "recommended_text_style": "serif"
            },
            "ai_suggested_background_colors": {
                "dominant_background_color": "#0A202A",
                "complementary_background_accents": ["#1B4332", "#40916C"]
            }
        }

    def generate_islamic_background(self, background_description, logo_analysis, content_data):
        """
        Génère un arrière-plan islamique avec Imagen, inspiré de l'analyse du logo.
        """
        print("🕌 [Étape 2/3] Génération de l'arrière-plan islamique inspiré du logo...")

        # --- UTILISER LES DESCRIPTIONS DE COULEURS POUR IMAGEN, PAS LES HEX BRUTS ---
        imagen_color_descs = logo_analysis.get('imagen_color_descriptions', self._get_default_logo_analysis()['imagen_color_descriptions'])
        dominant_bg_desc = imagen_color_descs['dominant_bg']
        complementary_bg_accents_descs = ', '.join(imagen_color_descs['complementary_bg_accents'])
        extracted_logo_colors_descs = ', '.join(imagen_color_descs['extracted_logo_colors'])

        # Utilisation des descriptions naturelles pour le prompt Imagen
        color_description_for_imagen = f"Dominant: {dominant_bg_desc}. Accents: {complementary_bg_accents_descs}. Logo colors: {extracted_logo_colors_descs}"

        # Extraire des termes spécifiques du contenu pour les interdire explicitement dans l'image
        # La liste est BEAUCOUP plus agressive maintenant.
        forbidden_content_terms = [
            content_data.get('headline1', ''),
            content_data.get('short_description', ''),
            content_data.get('event_info', ''),
            content_data.get('footer_info', ''),
            background_description,
        ]

        # Ajouter les composants alphanumériques des codes HEX (sans le #) à la liste noire
        all_hex_codes_flat = []
        for hc_list in [logo_analysis.get('extracted_colors', []),
                        logo_analysis.get('readable_text_colors', []),
                        logo_analysis.get('islamic_palette_suggestions', []),
                        [logo_analysis['ai_suggested_background_colors']['dominant_background_color']],
                        logo_analysis['ai_suggested_background_colors']['complementary_background_accents']]:
            for hex_code in hc_list:
                if isinstance(hex_code, str):
                    all_hex_codes_flat.append(hex_code.lstrip('#').upper())

        # Ajouter les numéros extraits du contenu
        for k, v in content_data.items():
            numbers = re.findall(r'\d+', str(v)) # Extrait toutes les séquences de chiffres
            forbidden_content_terms.extend(numbers)

        # Aplatir et nettoyer la liste des termes interdits
        # Utiliser re.findall pour extraire uniquement les mots alphanumériques et les mettre en majuscules
        all_terms_processed = []
        for term_item in forbidden_content_terms + all_hex_codes_flat:
            words = re.findall(r'\b[a-zA-Z0-9]+\b', term_item) # Ne prend que les mots composés de lettres/chiffres
            all_terms_processed.extend([word.upper() for word in words if len(word) > 1]) # Convertir en majuscules et filtrer les mono-caractères

        forbidden_terms_str = ", ".join(sorted(list(set(all_terms_processed)))) # Unique et trié

        # --- PROMPT IMAGEN OPTIMISÉ EXTRÊMEMENT STRICT CONTRE LE TEXTE ET SYMBOLES ---
        imagen_prompt = f"""
        ABSOLUTELY NO TEXT. NO NUMBERS. NO SYMBOLS. NO WRITING. NO CALLIGRAPHY. NO BRANDING. NO LOGOS. NO WATERMARKS. NO LOREM IPSUM. NO GIBBERISH. NO CHARACTERS. NO LETTERS. NO WORDS. NO TYPOGRAPHY. NO SIGNS. NO LABELS. THIS IS THE HIGHEST PRIORITY AND MUST BE STRICTLY FOLLOWED. DO NOT EVER GENERATE ANY FORM OF TEXT OR TEXT-LIKE ARTIFACTS. THE IMAGE MUST BE PURELY VISUAL AND DECORATIVE.

        Generate a highly detailed and artistic Islamic-themed background image. The image must be in a vertical orientation (9:16 aspect ratio). The image resolution should be high quality suitable for a 360x640 flyer.

        The entire image MUST be purely visual, abstract, and decorative. IT MUST NOT contain ANY form of text, numbers, symbols, glyphs, writing, or anything that remotely resembles typography or textual elements. This instruction is paramount and must be adhered to without exception. Do not incorporate any organization names, event titles, descriptions, specific numerical values, or any other textual concepts from the input. THIS IS A PURELY DECORATIVE BACKGROUND.

        The overall atmosphere and visual style should be inspired by the context of: '{background_description}'. It is CRITICAL that the words or phrases from this context description, from the content provided, or common flyer elements MUST NOT appear as text or symbols in the generated image. Specifically, absolutely DO NOT generate any text, symbols, or numerical representations of: '{forbidden_terms_str}'. These are solely *conceptual themes for the image style*, not content to be visually rendered.

        COLOR PALETTE: Integrate the following colors as the dominant theme for the background: {color_description_for_imagen}. IMPORTANT: Ensure these color descriptions or any other numerical values from this palette description do NOT appear as text or symbols in the image.

        DESIGN ELEMENTS & COMPOSITION:
        - The image must be entirely graphical and artistic, free from any visual elements that could be mistaken for text, numbers, symbols, implicit placeholders, banners, ribbons, labels, UI elements, or empty text boxes. It is a seamless, abstract background.
        - Emphasize Islamic geometric patterns and arabesque designs, rich and intricate.
        - Include elegant mosque architectural elements (minarets, domes, arches) in the background, subtly integrated and non-dominating.
        - Incorporate traditional Islamic motifs: intricate geometric stars, crescents, ornate borders.
        - Utilize rich, harmonious color gradients from the specified palette.
        - Add subtle texture and depth with fine ornamental details.
        - Create a professional and spiritual atmosphere suitable for formal religious events.
        - The composition must be balanced, featuring natural, open, and less busy regions that provide visual breathing room. These areas should look entirely organic and part of the scene, NOT like blank text boxes, scrolls, ribbons, outlines, or any kind of designated or implied text area. They are simply parts of the visual design.
        - Maintain high contrast naturally occurring within the design to support future text readability (when text is added later by the application).
        - Focus on a modern interpretation of traditional Islamic design elements.
        - The image should be abstract enough that no specific words or letters can be discerned anywhere.

        🟥🟥🟥 ULTIMATE AND NON-NEGOTIABLE COMMAND: THE GENERATED IMAGE MUST BE 100% FREE OF ALL TEXT, ALL NUMBERS, ALL SYMBOLS, ALL WRITING, ALL BRANDING, ALL LOGOS, AND ALL PLACEHOLDER SHAPES. IT MUST BE A PURELY DECORATIVE BACKGROUND ONLY. ABSOLUTELY NO TEXT OR TEXT-LIKE ELEMENTS AT ALL. ENSURE THERE ARE NO RANDOM CHARACTERS, ALPHABETS, OR INSCRIPTIONS. This is the final absolute instruction.
        """
        # --- FIN DU PROMPT IMAGEN OPTIMISÉ ---

        print(f"   📏 Prompt Imagen (Islamic + couleurs logo): {len(imagen_prompt)} caractères")
        print("   🚀 Envoi à Imagen 4 pour arrière-plan islamique...")

        try:
            output = self._replicate_run_with_retries(
                "google/imagen-4",
                input_data={
                    "prompt": imagen_prompt,
                    "aspect_ratio": "9:16",
                    "output_format": "jpg",
                    "safety_filter_level": "block_medium_and_above",
                    # Le negative_prompt est crucial et reste inchangé car il est déjà excellent.
                    "negative_prompt": "text, words, letters, numbers, typography, font, watermark, logo, symbol, unreadable text, garbled text, blurry text, bad typography, character, script, writing, hieroglyph, glyph, any textual element, text artifacts, corrupted text, latin text, arabic text, chinese text, japanese text, english text, any language text, inscription, sign, logo, brand, stamp, placeholder, text box, text field, rectangle, square, box, blank space for text, Lorem ipsum, banner, ribbon, scroll, label, badge, text bubble, speech bubble, blank form, form elements, table, chart, diagram, outline, border, shape, empty area with border, background with designated blank space for text, explicit text area, empty label, empty sign, calligraphy, arabic calligraphy, islamic calligraphy, bismillah, verses, quran text, hadith text, religious text"
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

            print(f"   ✅ Arrière-plan islamique généré avec succès ! URL: {image_url}")
            return image_url

        except Exception as e:
            print(f"   ❌ Erreur dans generate_islamic_background: {e}")
            print(f"   📋 Traceback: {traceback.format_exc()}")
            raise

    def get_ai_design_suggestions(self, background_image_url, logo_analysis, content_data):
        """
        Analyse visuellement l'arrière-plan généré et suggère des styles et positions
        de texte et de logo optimaux via GPT-4o.
        """
        print("📝 [Étape 3/3] Suggestion de styles de texte et position du logo (analyse visuelle IA)...")

        try:
            headline_content = content_data.get('headline1', 'Annual Gala')
            description_content = content_data.get('short_description', 'Evening of Celebration and Networking')
            event_info_content = content_data.get('event_info', 'Date: May 15, 2024 - Time: 7:00 PM - Venue: The Grand Palace, Paris')
            footer_info_content = content_data.get('footer_info', 'Contact: info@mosque-event.com | www.mosque-event.com | +212-522-12-34-56')

            # Utiliser les couleurs et recommandations de l'analyse du logo
            extracted_colors = logo_analysis.get('extracted_colors', [])
            readable_text_colors = logo_analysis.get('readable_text_colors', ["#FFFFFF", "#000000"]) # Fallback
            islamic_palette_suggestions = logo_analysis.get('islamic_palette_suggestions', ["#D4AF37", "#40916C"]) # Fallback
            logo_style = logo_analysis.get('logo_style_analysis', {})
            logo_dominant_color = logo_analysis.get('logo_dominant_color', "#FFFFFF")


            color_palette_str = ", ".join(extracted_colors + readable_text_colors + islamic_palette_suggestions)

            full_prompt_text = f"""
            You are an AI flyer designer. Your task is to analyze the attached vertical flyer background image (360px width × 640px height, 9:16 ratio) and the provided logo, then return optimal **design suggestions** for text and logo placement and styling. The goal: maximum readability, balance, and visual harmony with an Islamic-themed aesthetic.

**LOGO ANALYSIS INPUT:**
- Extracted Colors: {", ".join(extracted_colors)}
- Dominant Color: {logo_dominant_color}
- Suggested Readable Text Colors: {", ".join(readable_text_colors)}
- Islamic Palette Suggestions: {", ".join(islamic_palette_suggestions)}
- Logo Style Type: {logo_style.get('style_type', 'traditional')}
- Logo Visual Weight: {logo_style.get('visual_weight', 'medium')}
- Recommended Text Style: {logo_style.get('recommended_text_style', 'sans-serif')}

**TEXT CONTENT (ENGLISH):**
- Headline: "{headline_content}"
- Description: "{description_content}"
- Event Details: "{event_info_content}"
- Contact Info: "{footer_info_content}"

**TASK:**
From a visual analysis of the flyer background and logo characteristics:
1. Identify clear, uncluttered areas for each text block and the logo.
2. Suggest web-safe fonts matching the recommended style and Islamic theme.
3. Choose HEX text colors from extracted, readable, or Islamic palettes ensuring excellent contrast with the background at the placement position.
4. Define exact placement and sizing percentages relative to flyer dimensions.

**OUTPUT FORMAT (JSON only, no extra text):**

{
  "headline": {
    "fontFamily": "string",
    "color": "#RRGGBB",
    "fontSizePx": number,
    "fontWeight": "normal|bold|lighter|bolder|numeric",
    "textAlign": "center|left|right",
    "lineHeightEm": number,
    "initialTopPercentage": number,
    "initialWidthPercentage": number,
    "initialLeftPercentage": number
  },
  "body": { 
      "fontFamily": "string",
    "color": "#RRGGBB",
    "fontSizePx": number,
    "fontWeight": "normal|bold|lighter|bolder|numeric",
    "textAlign": "center|left|right",
    "lineHeightEm": number,
    "initialTopPercentage": number,
    "initialWidthPercentage": number,
    "initialLeftPercentage": number },
  "event_info": {"fontFamily": "string",
    "color": "#RRGGBB",
    "fontSizePx": number,
    "fontWeight": "normal|bold|lighter|bolder|numeric",
    "textAlign": "center|left|right",
    "lineHeightEm": number,
    "initialTopPercentage": number,
    "initialWidthPercentage": number,
    "initialLeftPercentage": number},
  "footer": {"fontFamily": "string",
    "color": "#RRGGBB",
    "fontSizePx": number,
    "fontWeight": "normal|bold|lighter|bolder|numeric",
    "textAlign": "center|left|right",
    "lineHeightEm": number,
    "initialTopPercentage": number,
    "initialWidthPercentage": number,
    "initialLeftPercentage": number},
  "logo": {
    "initialTopPercentage": number,
    "initialLeftPercentage": number,
    "initialWidthPercentage": number,
    "horizontalAlignment": "left|center|right",
    "shadowEffect": {
      "apply": true|false,
      "color": "#RRGGBBAA",
      "offsetPx": number,
      "blurPx": number
    }
  }
}

Return only the JSON object.
"""

            print("   🤖 Envoi à GPT-4o pour styles de texte islamiques et position du logo (analyse visuelle)...")
            output = self._replicate_run_with_retries(
                "openai/gpt-4o",
                input_data={
                    "prompt": full_prompt_text,
                    "image_input": [background_image_url], # C'est ici que l'image est envoyée pour analyse
                    "max_completion_tokens": 1500,
                    "temperature": 0.7
                },
                timeout=REPLICATE_TIMEOUT
            )

            suggestions_str = "".join(output)
            print(f"   ✅ Suggestions reçues: {len(suggestions_str)} caractères")

            try:
                # Tente de nettoyer la réponse si elle contient du markdown JSON
                if suggestions_str.strip().startswith("```json"):
                    suggestions_str = suggestions_str.strip("```json\n").strip("```")

                suggestions = json.loads(suggestions_str)

                # Validation basique
                if not isinstance(suggestions, dict):
                    raise ValueError("Les suggestions ne sont pas au format JSON dict.")

                print("   ✅ Suggestions de style et position du logo parsées avec succès.")
                return suggestions

            except json.JSONDecodeError as e:
                print(f"   ⚠️ Erreur de parsing JSON pour les suggestions de style: {e}")
                print(f"   Réponse GPT-4o brute qui a échoué: \n{suggestions_str[:500]}...")
                return self._get_default_islamic_styles(logo_analysis)

        except Exception as e:
            print(f"   ❌ Erreur dans get_ai_design_suggestions: {e}")
            print(f"   📋 Traceback: {traceback.format_exc()}")
            return self._get_default_islamic_styles(logo_analysis)

    def _get_default_islamic_styles(self, logo_analysis):
        """Styles par défaut basés sur l'analyse du logo si l'IA visuelle échoue."""
        print("   ⚠️ Utilisation des styles de texte par défaut.")
        colors = logo_analysis.get('extracted_colors', [])
        readable_colors = logo_analysis.get('readable_text_colors', ["#FFFFFF", "#000000"]) # Fallback
        logo_dominant_color = logo_analysis.get('logo_dominant_color', "#2D6A4F")

        # Utilisation de couleurs de texte lisibles basées sur l'analyse du logo, ou des valeurs sûres
        headline_color = readable_colors[0] if readable_colors else "#D4AF37"
        body_color = readable_colors[1] if len(readable_colors) > 1 else "#FFFFFF"
        event_info_color = logo_dominant_color if logo_dominant_color else "#40916C"
        footer_color = readable_colors[0] if readable_colors else "#D4AF37"

        # Polices par défaut, assurez-vous qu'elles correspondent aux TTF disponibles
        default_headline_font = "Playfair Display, serif"
        default_body_font = "Roboto, sans-serif"
        default_info_footer_font = "Open Sans, sans-serif"

        return {
            "headline": {
                "fontFamily": default_headline_font,
                "color": headline_color,
                "fontSizePx": 38,
                "fontWeight": "bold",
                "textAlign": "center",
                "lineHeightEm": 1.2,
                "initialTopPercentage": 10,
                "initialWidthPercentage": 90,
                "initialLeftPercentage": 5
            },
            "body": {
                "fontFamily": default_body_font,
                "color": body_color,
                "fontSizePx": 18,
                "fontWeight": "normal",
                "textAlign": "center",
                "lineHeightEm": 1.5,
                "initialTopPercentage": 35,
                "initialWidthPercentage": 85,
                "initialLeftPercentage": 7.5
            },
            "event_info": {
                "fontFamily": default_info_footer_font,
                "color": event_info_color,
                "fontSizePx": 22,
                "fontWeight": "600",
                "textAlign": "center",
                "lineHeightEm": 1.3,
                "initialTopPercentage": 65,
                "initialWidthPercentage": 88,
                "initialLeftPercentage": 6
            },
            "footer": {
                "fontFamily": default_info_footer_font,
                "color": footer_color,
                "fontSizePx": 14,
                "fontWeight": "normal",
                "textAlign": "center",
                "lineHeightEm": 1.4,
                "initialTopPercentage": 88,
                "initialWidthPercentage": 95,
                "initialLeftPercentage": 2.5
            },
            # --- AJOUT DES VALEURS PAR DÉFAUT POUR LE LOGO ---
            "logo": {
                "initialTopPercentage": 25, # Positionnement par défaut
                "initialLeftPercentage": 50, # Positionnement par défaut (50% pour le centre)
                "initialWidthPercentage": 30, # Largeur par défaut (30% de la largeur du flyer)
                "horizontalAlignment": "center", # Alignement par défaut
                "shadowEffect": {
                    "apply": True,
                    "color": "#000000A0", # Ombre noire légèrement transparente
                    "offsetPx": 3,
                    "blurPx": 4
                }
            }
        }

# Initialisation du générateur au démarrage de l'application Flask
try:
    islamic_flyer_gen = IslamicFlyerGenerator(api_key_unused=None)
    print("✅ Générateur islamique initialisé avec succès (Instance prête).")
except Exception as e:
    print(f"❌ ERREUR CRITIQUE lors de l'initialisation du générateur: {e}")
    raise


# --- Fonction utilitaire pour obtenir le chemin de la police ---
def _get_font_path(font_family):
    """
    Tente de trouver le chemin d'un fichier de police basé sur le nom de la famille.
    Recherche d'abord dans le dossier 'fonts' du projet.
    """
    base_dir = os.path.dirname(__file__)
    project_fonts_dir = os.path.join(base_dir, 'fonts')

    # Mappage des noms de polices CSS vers les noms de fichiers .ttf (assurez-vous que ces fichiers existent dans 'fonts/')
    font_files_map = {
        "Arial": "arial.ttf",
        "Verdana": "verdana.ttf",
        "Helvetica": "arial.ttf", # Helvetica est souvent mappée à Arial sur Windows/Linux par défaut
        "Georgia": "georgia.ttf",
        "Times New Roman": "times.ttf",
        "Courier New": "cour.ttf",
        "Impact": "impact.ttf",
        "Trebuchet MS": "trebuc.ttf",
        "Open Sans": "OpenSans-Regular.ttf", # Exemple de Google Font
        "Roboto": "Roboto-Regular.ttf",      # Exemple de Google Font
        "Playfair Display": "PlayfairDisplay-Regular.ttf", # Exemple de Google Font
        "Lato": "Lato-Regular.ttf",
        "Merriweather": "Merriweather-Regular.ttf",
        # Ajoutez d'autres polices si nécessaire, en respectant les noms de fichiers exacts.
        # Pour les variantes (bold, italic), vous devrez ajouter des entrées comme "Roboto Bold": "Roboto-Bold.ttf"
        # et gérer la sélection dans le code de rendu si vous voulez supporter plus que 'normal'/'bold'.
    }

    clean_font_name = font_family.split(',')[0].strip()

    # Tente de trouver la police exacte dans le mappage et le dossier du projet
    if clean_font_name in font_files_map:
        potential_path = os.path.join(project_fonts_dir, font_files_map[clean_font_name])
        if os.path.exists(potential_path):
            return potential_path
    
    # Fallback générique si la police exacte n'est pas trouvée dans le dossier projet.
    # On peut chercher d'autres polices communes qui pourraient être là.
    generic_fallbacks = [
        "arial.ttf", "OpenSans-Regular.ttf", "Roboto-Regular.ttf",
        "times.ttf", "georgia.ttf",
        "cour.ttf" # For monospace
    ]
    for filename in generic_fallbacks:
        potential_path = os.path.join(project_fonts_dir, filename)
        if os.path.exists(potential_path):
            print(f"   AVERTISSEMENT: Police '{font_family}' non trouvée. Utilisation de la police de fallback du projet: {potential_path}")
            return potential_path

    print(f"   AVERTISSEMENT: Aucune police compatible pour '{font_family}' trouvée dans le dossier 'fonts/'. Utilisation de la police par défaut (PIL).")
    return None # Cela fera que PIL utilise sa police bitmap par défaut

def _text_wrap(text, font, max_width):
    """
    Découpe le texte en lignes pour qu'il tienne dans une largeur maximale.
    """
    lines = []
    if not text:
        return lines

    words = text.split(' ')
    current_line = []
    for word in words:
        test_line = ' '.join(current_line + [word])

        try:
            # getbbox() renvoie (left, top, right, bottom)
            # La largeur est (right - left)
            bbox = font.getbbox(test_line)
            text_width = bbox[2] - bbox[0]
        except Exception as e:
            # Fallback si getbbox échoue (peut arriver avec certaines versions/polices)
            print(f"   AVERTISSEMENT: Échec de font.getbbox pour '{test_line[:30]}...': {e}. Estimant la largeur.")
            text_width = len(test_line) * font.size * 0.6 # Estimation simple

        if text_width <= max_width:
            current_line.append(word)
        else:
            if current_line: # Si la ligne actuelle n'est pas vide, l'ajouter
                lines.append(' '.join(current_line))
            
            # Gérer le cas où un seul mot est plus large que la ligne
            try:
                word_bbox = font.getbbox(word)
                word_width = word_bbox[2] - word_bbox[0]
            except Exception:
                word_width = len(word) * font.size * 0.6 # Estimation

            if word_width > max_width:
                # Si le mot seul est trop large, il sera coupé par le conteneur,
                # mais on l'ajoute comme sa propre ligne pour ne pas bloquer.
                lines.append(word)
                current_line = []
            else:
                current_line = [word] # Démarrer une nouvelle ligne avec ce mot

    if current_line:
        lines.append(' '.join(current_line))
    return lines


@app.route('/api/generate-islamic-flyer', methods=['POST'])
def generate_islamic_flyer_main_route():
    print("\n" + "="*80)
    print("🕌 NOUVELLE REQUÊTE DE GÉNÉRATION DE FLYER ISLAMIQUE (Principal)")
    print("="*80)

    try:
        print("🔍 Phase 1: Validation des données reçues.")

        if 'logo_image' not in request.files:
            error_msg = "Aucun fichier 'logo_image' dans la requête."
            print(f"   ❌ {error_msg}")
            return jsonify({'error': error_msg}), 400

        logo_image_file = request.files['logo_image']
        print(f"   📁 Logo reçu: {logo_image_file.filename}")

        if logo_image_file.filename == '':
            error_msg = "Nom de fichier vide pour le logo."
            print(f"   ❌ {error_msg}")
            return jsonify({'error': error_msg}), 400

        logo_image_bytes = logo_image_file.read()
        print(f"   📏 Taille du logo: {len(logo_image_bytes)} bytes.")

        if len(logo_image_bytes) == 0:
            error_msg = "Fichier logo vide."
            print(f"   ❌ {error_msg}")
            return jsonify({'error': error_msg}), 400

        try:
            # Tente d'ouvrir l'image pour validation (PIL la ferme automatiquement après usage)
            Image.open(BytesIO(logo_image_bytes))
            print(f"   ✅ Logo valide (test PIL).")
        except Exception as e:
            error_msg = f"Le logo fourni est invalide ou corrompu: {e}"
            print(f"   ❌ {error_msg}")
            return jsonify({'error': error_msg}), 400

        content_data = {
            'headline1': request.form.get('headline1', 'Annual Gala 2024'),
            'short_description': request.form.get('short_description', 'Join us for an unforgettable evening of celebration and networking — a unique opportunity to connect with industry leaders in an exceptional setting.'),
            'background_description': request.form.get('background_description', 'elegant islamic event, arabesque patterns, mosque silhouette'),
            'event_info': request.form.get('event_info', 'Date: May 15, 2024 - Time: 7:00 PM - Venue: The Grand Palace, Paris'),
            'footer_info': request.form.get('footer_info', 'Contact: info@mosque-event.com | www.mosque-event.com | +212-522-12-34-56')
        }
        print(f"   📝 Données reçues: {content_data}")

        print("   ✅ Phase 1 terminée: Données valides.")

        # --- ÉTAPE 1: ANALYSE DU LOGO (Couleurs, Style général, Suggestions de fond) ---
        print("\n🎨 Phase 2: Analyse complète du logo avec GPT-4o.")
        try:
            logo_analysis = islamic_flyer_gen.extract_logo_colors_and_styles_with_gpt4o(logo_image_bytes)
            print("   ✅ Phase 2 terminée: Analyse du logo complétée.")
        except Exception as e:
            error_msg = f'Erreur lors de l\'analyse des couleurs du logo: {str(e)}'
            print(f"   ❌ {error_msg}")
            return jsonify({'error': error_msg}), 500

        # --- ÉTAPE 2: GÉNÉRATION DE L'ARRIÈRE-PLAN ---
        print("\n🖼️ Phase 3: Génération de l'arrière-plan islamique avec Imagen.")
        try:
            flyer_background_image_url = islamic_flyer_gen.generate_islamic_background(
                content_data['background_description'],
                logo_analysis,
                content_data
            )
            print("   ✅ Phase 3 terminée: Arrière-plan généré avec succès.")
        except Exception as e:
            error_msg = f'Erreur lors de la génération de l\'arrière-plan islamique: {str(e)}'
            print(f"   ❌ {error_msg}")
            return jsonify({'error': error_msg}), 500

        # --- ÉTAPE 3: SUGGESTION DE STYLES ET POSITIONS DE TEXTE ET LOGO (Analyse visuelle de l'arrière-plan par GPT-4o) ---
        print("\n📝 Phase 4: Suggestion de styles de texte et position du logo (analyse visuelle par GPT-4o).")
        try:
            text_style_suggestions = islamic_flyer_gen.get_ai_design_suggestions(
                flyer_background_image_url, # C'est ici que l'image générée est passée à GPT-4o
                logo_analysis,
                content_data
            )
            print("   ✅ Phase 4 terminée: Styles et position du logo suggérés.")
        except Exception as e:
            error_msg = f'Erreur lors de la suggestion des styles de texte et du logo (analyse visuelle): {str(e)}'
            print(f"   ❌ {error_msg}")
            return jsonify({'error': error_msg}), 500

        print(f"\n✅ SUCCÈS COMPLET DE LA PREMIÈRE PHASE!")
        print(f"   🎉 URL de l'arrière-plan: {flyer_background_image_url}")
        print(f"   🎨 Couleurs extraites du logo: {logo_analysis.get('extracted_colors', 'N/A')}")
        print(f"   🎨 Couleurs arrière-plan suggérées: {logo_analysis.get('ai_suggested_background_colors', 'N/A')}")
        print(f"   ✨ Suggestions de style pour texte et logo: {text_style_suggestions}")
        print("="*80 + "\n")

        return jsonify({
            'success': True,
            'flyer_background_url': flyer_background_image_url,
            'text_style_suggestions': text_style_suggestions,
            'extracted_colors': logo_analysis.get('extracted_colors', []), # Envoyer les couleurs extraites pour info client
            'logo_analysis': logo_analysis, # Envoyer l'analyse complète du logo
            'message': 'Flyer islamique généré avec succès avec analyse complète du logo.'
        })

    except Exception as e:
        print(f"\n❌ ERREUR FATALE DANS LA ROUTE ISLAMIQUE PRINCIPALE:")
        print(f"   🔥 Erreur: {e}")
        print(f"   📋 Type: {type(e).__name__}")
        print(f"   🗂️ Traceback complet:")
        traceback.print_exc()
        print("="*80 + "\n")

        return jsonify({
            'error': f"Une erreur interne est survenue lors de la génération initiale: {str(e)}",
            'error_type': type(e).__name__
        }), 500

# --- ROUTE POUR LA GÉNÉRATION FINALE DU FLYER CÔTÉ SERVEUR ---
@app.route('/api/generate-final-flyer', methods=['POST'])
def generate_final_flyer():
    print("\n" + "="*80)
    print("✨ DÉBUT DE LA GÉNÉRATION FINALE DE FLYER ISLAMIQUE (Côté Serveur)")
    print("="*80)
    try:
        data = request.json
        background_url = data.get('background_url')
        text_components = data.get('text_components', [])
        flyer_dims = data.get('flyer_dimensions', {'width': 360, 'height': 640})

        if not background_url:
            print("   ❌ URL de l'image de fond manquante.")
            return jsonify({'error': 'URL de l\'image de fond manquante.'}), 400

        print(f"   📥 Téléchargement de l'image de fond depuis: {background_url}")
        try:
            response = requests.get(background_url, stream=True, timeout=30)
            response.raise_for_status() # Lève une erreur pour les codes d'état HTTP non 2xx
            background_image_bytes = BytesIO(response.content)
            # Charger l'image de fond et s'assurer qu'elle est en mode RGBA
            background = Image.open(background_image_bytes).convert("RGBA")
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Erreur de téléchargement de l'arrière-plan: {e}")
            return jsonify({'error': f"Échec du téléchargement de l'arrière-plan: {e}"}), 500
        except Exception as e:
            print(f"   ❌ Erreur de chargement de l'arrière-plan avec PIL: {e}")
            return jsonify({'error': f"Échec du chargement de l'image de fond: {e}"}), 500

        print(f"   📏 Dimensions de l'arrière-plan téléchargé: {background.size}")
        if background.width != flyer_dims['width'] or background.height != flyer_dims['height']:
            print(f"   🔄 Redimensionnement de {background.size} à {flyer_dims['width']}x{flyer_dims['height']}.")
            background = background.resize((flyer_dims['width'], flyer_dims['height']), Image.Resampling.LANCZOS)

        # Créez une image de sortie finale avec un fond transparent (pour les PNG) ou blanc
        # Coller l'arrière-plan sur une nouvelle image pour s'assurer d'avoir un canevas propre.
        final_output_image = Image.new("RGBA", (flyer_dims['width'], flyer_dims['height']), (0, 0, 0, 0)) # Fond transparent
        final_output_image.paste(background, (0, 0), background) # Paste background, respecting its alpha if any

        # Dessiner sur cette image finale
        draw = ImageDraw.Draw(final_output_image)

        print(f"   📝 Traitement de {len(text_components)} composants...")

        for comp_idx, comp in enumerate(text_components):
            comp_id = comp.get('id', f'comp_{comp_idx}')
            content = comp.get('content', '')
            style = comp.get('style', {})
            is_image = comp.get('isImage', False)
            image_url = comp.get('imageUrl', None)

            print(f"   🔍 Composant {comp_idx + 1}: {comp_id} ({'image' if is_image else 'texte'}). Contenu: '{content[:50]}...'")

            # Traitement spécial pour les logos (images)
            if is_image and comp_id == 'logo':
                print(f"   🖼️ Traitement du logo '{comp_id}'...")

                try:
                    # Télécharger le logo depuis l'URL data ou URL externe
                    if image_url.startswith('data:image/'):
                        header, encoded = image_url.split(',', 1)
                        logo_bytes = base64.b64decode(encoded)
                    else:
                        logo_response = requests.get(image_url, stream=True, timeout=15)
                        logo_response.raise_for_status()
                        logo_bytes = logo_response.content

                    logo_image = Image.open(BytesIO(logo_bytes)).convert("RGBA") # S'assure que le logo est RGBA

                    # Récupérer les styles de positionnement
                    logo_x_px = comp.get('x', 0)
                    logo_y_px = comp.get('y', 0)
                    width_percent = int(comp.get('width', '30%').replace('%', ''))
                    shadow_effect = style.get('shadowEffect', {"apply": False})

                    # Calculer les dimensions du logo en pixels
                    logo_width_px = int((width_percent / 100) * flyer_dims['width'])

                    # Redimensionner le logo en gardant les proportions
                    if logo_image.width > 0 and logo_image.height > 0: # Éviter division par zéro
                        logo_ratio = logo_image.width / logo_image.height
                        logo_height_px = int(logo_width_px / logo_ratio)
                    else:
                        logo_height_px = logo_width_px # Fallback si image est invalide
                        print(f"   ⚠️ Dimensions du logo invalides, utilisant hauteur = largeur pour le redimensionnement.")


                    # Redimensionner le logo
                    logo_image = logo_image.resize((logo_width_px, logo_height_px), Image.Resampling.LANCZOS)

                    # Appliquer l'ombre si suggéré
                    if shadow_effect.get('apply', False):
                        shadow_color_hex = shadow_effect.get('color', '#000000A0')
                        shadow_offset_px = shadow_effect.get('offsetPx', 3)
                        shadow_blur_px = shadow_effect.get('blurPx', 4)

                        def hex_to_rgba_tuple(hex_color):
                            hex_color = hex_color.lstrip('#')
                            if len(hex_color) == 6: # RRGGBB
                                return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4)) + (255,)
                            elif len(hex_color) == 8: # RRGGBBAA
                                return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4, 6))
                            return (0, 0, 0, 0) # Fallback transparent

                        shadow_color_rgba = hex_to_rgba_tuple(shadow_color_hex)

                        # Créer une image d'ombre de la même taille que le logo (ou légèrement plus grande pour le blur)
                        # Remplir avec la couleur d'ombre et l'alpha du logo
                        # L'approche avec ImageDraw.Draw().ellipse/rectangle() pour le masque d'ombre est plus flexible pour des formes complexes
                        # Pour un logo générique, on peut utiliser un masque basé sur l'alpha du logo lui-même.
                        logo_alpha_mask = logo_image.split()[3] # Obtenir le canal alpha du logo
                        shadow_base = Image.new('RGBA', logo_image.size, shadow_color_rgba)
                        shadow_base.putalpha(logo_alpha_mask) # Appliquer le masque alpha du logo à l'image d'ombre

                        # Appliquer le flou sur l'ombre
                        shadow_image_blurred = shadow_base.filter(ImageFilter.GaussianBlur(shadow_blur_px))

                        # Calculer la position de l'ombre
                        shadow_x = logo_x_px + shadow_offset_px
                        shadow_y = logo_y_px + shadow_offset_px

                        # Coller l'ombre sur l'image finale
                        if shadow_x < flyer_dims['width'] and shadow_y < flyer_dims['height']:
                            final_output_image.paste(shadow_image_blurred, (shadow_x, shadow_y), shadow_image_blurred)


                    # Coller le logo sur l'image finale (par-dessus l'ombre)
                    if logo_x_px < flyer_dims['width'] and logo_y_px < flyer_dims['height']:
                        final_output_image.paste(logo_image, (logo_x_px, logo_y_px), logo_image)

                    print(f"   ✅ Logo '{comp_id}' placé à ({logo_x_px}, {logo_y_px}) avec taille {logo_width_px}x{logo_height_px}. Ombre appliquée: {shadow_effect.get('apply', False)}")

                except Exception as e:
                    print(f"   ❌ Erreur lors du placement du logo '{comp_id}': {e}")
                    traceback.print_exc()
                    continue # Passe au composant suivant

                continue  # Passe au composant suivant après avoir traité le logo

            # Traitement des composants texte
            if not content.strip():
                print(f"   ⚠️ Contenu vide pour le composant texte '{comp_id}', passage au suivant.")
                continue

            # Récupérer les styles et positions
            x_px = comp.get('x', 0)
            y_px = comp.get('y', 0)

            width_percent = int(comp.get('width', '90%').replace('%', ''))
            max_text_width_px = (width_percent / 100) * flyer_dims['width']
            min_height_px = comp.get('minHeightPx', 0)

            font_family = style.get('fontFamily', 'Arial, sans-serif').split(',')[0].strip()
            font_size_px = int(style.get('fontSizePx', 24))
            color_hex = style.get('color', '#000000')
            text_align = style.get('textAlign', 'center')
            line_height_em = float(style.get('lineHeightEm', 1.4))

            # Convertir la couleur HEX en RGB/RGBA pour PIL
            try:
                if not color_hex.startswith('#'):
                    color_hex = '#000000' # Fallback si format invalide
                text_color_rgb = tuple(int(color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            except ValueError:
                text_color_rgb = (0, 0, 0) # Noir par défaut si erreur de conversion
            text_color_rgba = (*text_color_rgb, 255) # Ajoute l'alpha 255 (opaque)

            # Charger la police
            font_path = _get_font_path(font_family)
            try:
                if font_path and os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, font_size_px)
                else:
                    font = ImageFont.load_default() # Police bitmap par défaut de PIL
                    print(f"   ⚠️ Police de fallback (PIL par défaut) utilisée pour '{comp_id}'.")
            except (IOError, OSError) as e:
                print(f"   ⚠️ Erreur de chargement police '{font_family}': {e}. Utilisation de la police par défaut (PIL).")
                font = ImageFont.load_default()

            # Déterminer la couleur de l'ombre du texte (contraste inversé)
            text_luminance = (text_color_rgb[0] * 0.299 + text_color_rgb[1] * 0.587 + text_color_rgb[2] * 0.114)
            is_light_text = text_luminance > 128
            shadow_color_rgba = (0, 0, 0, 180) if is_light_text else (255, 255, 255, 180) # Légèrement transparent
            shadow_offset = max(1, int(font_size_px / 20)) # Ajuster l'offset de l'ombre

            lines = _text_wrap(content, font, max_text_width_px)

            current_y_for_line = y_px
            for line_idx, line in enumerate(lines):
                if not line.strip():
                    continue

                try:
                    # Obtenir la boîte englobante du texte pour la ligne
                    bbox = font.getbbox(line)
                    line_width = bbox[2] - bbox[0] # Largeur du texte réel
                    line_height = bbox[3] - bbox[1] # Hauteur du texte réel
                except Exception as e:
                    print(f"   AVERTISSEMENT: Échec de font.getbbox pour la ligne '{line[:20]}...': {e}. Estimant la largeur/hauteur.")
                    line_width = len(line) * font_size_px * 0.6 # Estimation
                    line_height = font_size_px # Estimation

                line_x_final = x_px
                # Ajuster la position X en fonction de l'alignement et de la largeur réelle de la ligne
                if text_align == 'center':
                    line_x_final += (max_text_width_px - line_width) / 2
                elif text_align == 'right':
                    line_x_final += (max_text_width_px - line_width)

                line_x_final = int(max(0, line_x_final)) # S'assurer que X ne soit pas négatif
                current_y_px_int = int(max(0, current_y_for_line)) # S'assurer que Y ne soit pas négatif

                # Dessiner l'ombre du texte
                draw.text(
                    (int(line_x_final + shadow_offset), int(current_y_px_int + shadow_offset)),
                    line,
                    font=font,
                    fill=shadow_color_rgba
                )

                # Dessiner le texte principal
                draw.text(
                    (line_x_final, current_y_px_int),
                    line,
                    font=font,
                    fill=text_color_rgba
                )

                next_line_height = font_size_px * line_height_em
                current_y_for_line += next_line_height

            print(f"   ✅ Texte '{comp_id}' traité: {len(lines)} lignes, couleur: {color_hex}, police: {font_family}.")

        # Amélioration finale de l'image (légère accentuation)
        final_output_image = final_output_image.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3))

        # Sauvegarde en PNG (gère la transparence via RGBA)
        img_io = BytesIO()
        final_output_image.save(img_io, 'PNG', quality=100, optimize=True)
        img_io.seek(0)

        print("   ✅ Flyer islamique final généré avec succès !")

        return send_file(
            img_io,
            mimetype='image/png',
            as_attachment=True,
            download_name=f'flyer_islamique_{int(time.time())}.png'
        )

    except Exception as e:
        print(f"\n❌ ERREUR LORS DE LA GÉNÉRATION FINALE:")
        print(f"   🔥 Erreur: {e}")
        print(f"   📋 Type: {type(e).__name__}")
        print(f"   🗂️ Traceback complet:")
        traceback.print_exc()
        print("="*80 + "\n")
        return jsonify({
            'error': f"Erreur lors de la génération finale du flyer: {str(e)}",
            'error_type': type(e).__name__
        }), 500

if __name__ == '__main__':
    # Lance le serveur Flask en mode développement
    # Pour un déploiement en production, utilisez un serveur WSGI comme Gunicorn ou Waitress.
    app.run(debug=True, port=5000)













# # FLYER-IA/flyer-ia/backend/app.py

# from flask import Flask, request, jsonify, send_file
# from flask_cors import CORS
# import openai
# import replicate
# from replicate.exceptions import ReplicateError
# from replicate.helpers import FileOutput
# from PIL import Image, ImageDraw, ImageFont
# import io # Garder pour io.BytesIO dans describe_image_style (si non from io import BytesIO)
# from io import BytesIO # <--- CORRECTION: Importation explicite de BytesIO
# import base64
# import os
# from dotenv import load_dotenv
# import traceback
# import json
# import time
# import requests

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
#                 if e.status == 429:
#                     print(f"   ⚠️ Replicate a renvoyé 429 (trop de requêtes). Réessai dans {current_delay:.1f}s...")
#                     time.sleep(current_delay)
#                     current_delay *= 2
#                     if current_delay > 60:
#                         current_delay = 60
#                 else:
#                     print(f"   ❌ Erreur Replicate inattendue (non 429): {e}")
#                     raise
#             except Exception as e:
#                 print(f"   ❌ Erreur générale lors de l'appel Replicate (tentative {attempt + 1}): {e}")
#                 time.sleep(current_delay)
#                 current_delay *= 2
#                 if current_delay > 60:
#                     current_delay = 60

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
#             headline_content = content_data.get('headline1', 'Headline')
#             description_content = content_data.get('short_description', 'A concise description of your event, summarizing its purpose or key features.')
#             event_info_content = content_data.get('event_info', 'Date, Time, and Location of the Event')
#             footer_info_content = content_data.get('footer_info', 'Contact Information, Website, and Phone Number')

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

#         headline_length_desc = "a short, prominent heading" if len(content_data.get('headline1', '')) < 25 else "a medium-length, multi-line prominent heading"
#         description_length_desc = "a concise, short paragraph" if len(content_data.get('short_description', '')) < 150 else "a detailed, longer multi-line paragraph"
#         event_info_length_desc = "a single line of important details"
#         footer_info_length_desc = "one to two lines of contact information"

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
#             output = self._replicate_run_with_retries(
#                 "google/imagen-4",
#                 input_data={
#                     "prompt": imagen_prompt,
#                     "aspect_ratio": "9:16",
#                     "output_format": "jpg",
#                     "safety_filter_level": "block_medium_and_above",
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

# # --- Fonction utilitaire pour obtenir le chemin de la police ---
# # IMPORTANT: Vous DEVEZ avoir les fichiers .ttf ou .otf des polices que vous utilisez
# # sur votre serveur, idéalement dans un dossier 'fonts' à côté de app.py.
# # Sinon, Pillow utilisera une police par défaut, ce qui affectera le rendu.
# def _get_font_path(font_family):
#     base_dir = os.path.dirname(__file__)
#     project_fonts_dir = os.path.join(base_dir, 'fonts') # Créez ce dossier et mettez vos .ttf ici

#     # Cartographie des noms de polices CSS aux noms de fichiers .ttf.
#     # Ajoutez ici les noms exacts des fichiers .ttf que vous avez téléchargés.
#     font_files_map = {
#         "Arial": "arial.ttf",
#         "Verdana": "verdana.ttf",
#         "Helvetica": "arial.ttf", # Souvent remplacée par Arial
#         "Georgia": "georgia.ttf",
#         "Times New Roman": "times.ttf",
#         "Courier New": "cour.ttf",
#         "Impact": "impact.ttf",
#         "Trebuchet MS": "trebuc.ttf",
#         "Open Sans": "OpenSans-Regular.ttf", # Assurez-vous d'avoir ce fichier
#         "Roboto": "Roboto-Regular.ttf",     # Assurez-vous d'avoir ce fichier
#         "Playfair Display": "PlayfairDisplay-Regular.ttf", # Assurez-vous d'avoir ce fichier
#         "Lato": "Lato-Regular.ttf",         # Assurez-vous d'avoir ce fichier
#         "Merriweather": "Merriweather-Regular.ttf", # Assurez-vous d'avoir ce fichier
#         # Pour les variantes (gras, italique), vous aurez besoin de fichiers spécifiques (ex: Roboto-Bold.ttf)
#         # Ceci est une simplification pour l'exemple.
#     }

#     # Nettoyage du nom de la police pour la recherche
#     clean_font_name = font_family.split(',')[0].strip()
    
#     # Prioriser les polices du dossier 'fonts' du projet
#     if clean_font_name in font_files_map:
#         potential_path = os.path.join(project_fonts_dir, font_files_map[clean_font_name])
#         if os.path.exists(potential_path):
#             return potential_path
    
#     # Fallback vers des polices système courantes (peut varier selon l'OS)
#     system_font_paths = {
#         "serif": ["times.ttf", "Georgia.ttf"],
#         "sans-serif": ["arial.ttf", "OpenSans-Regular.ttf", "Roboto-Regular.ttf"],
#         "monospace": ["cour.ttf"]
#     }

#     # Essayer de trouver une police générique si aucune correspondance directe
#     if "serif" in font_family.lower():
#         fallback_filenames = system_font_paths["serif"]
#     elif "monospace" in font_family.lower():
#         fallback_filenames = system_font_paths["monospace"]
#     else:
#         fallback_filenames = system_font_paths["sans-serif"]
    
#     for filename in fallback_filenames:
#         # Essayer dans le dossier de votre projet
#         potential_path = os.path.join(project_fonts_dir, filename)
#         if os.path.exists(potential_path):
#             print(f"   Utilisation de la police de fallback du projet: {potential_path}")
#             return potential_path
        
#         # Essayer des chemins système courants (pour Linux/Windows)
#         for sys_path_prefix in ["/usr/share/fonts/truetype/", "/Library/Fonts/", os.path.join(os.getenv("WINDIR") or "", "Fonts")]:
#             potential_path = os.path.join(sys_path_prefix, filename)
#             if os.path.exists(potential_path):
#                 print(f"   Utilisation de la police de fallback système: {potential_path}")
#                 return potential_path

#     print(f"   AVERTISSEMENT: Police '{font_family}' ou une alternative appropriée non trouvée. Utilisation de la police par défaut de Pillow.")
#     return None # Pillow utilisera sa police par défaut

# def _text_wrap(text, font, max_width):
#     lines = []
#     if not text:
#         return lines

#     # Utilisez textbbox pour obtenir des mesures précises du texte
#     # textbbox retourne (left, top, right, bottom)
#     # text_width = bbox[2] - bbox[0]
    
#     words = text.split(' ')
#     current_line = []
#     for word in words:
#         test_line = ' '.join(current_line + [word])
        
#         # Obtenir la largeur du texte de test
#         try:
#             # textbbox est plus fiable pour obtenir les dimensions exactes du texte
#             bbox = font.getbbox(test_line)
#             text_width = bbox[2] - bbox[0]
#         except Exception as e:
#             # Fallback si getbbox échoue (ex: caractères non supportés par la police)
#             print(f"   AVERTISSEMENT: Échec de font.getbbox pour '{test_line}': {e}. Estimations utilisées.")
#             # Estimation approximative si getbbox échoue
#             text_width = len(test_line) * font.size * 0.6 # 0.6 est un facteur heuristique
            
#         if text_width <= max_width:
#             current_line.append(word)
#         else:
#             if current_line: # Si la ligne actuelle n'est pas vide, l'ajouter
#                 lines.append(' '.join(current_line))
            
#             # Vérifier si le mot lui-même est plus large que la largeur max
#             try:
#                 word_bbox = font.getbbox(word)
#                 word_width = word_bbox[2] - word_bbox[0]
#             except Exception:
#                 word_width = len(word) * font.size * 0.6

#             if word_width > max_width:
#                 # Si un seul mot est trop long, il doit être coupé. Pillow ne coupe pas le texte.
#                 # Pour l'instant, on ajoute le mot tel quel, il dépassera.
#                 # Une implémentation plus avancée devrait couper le mot.
#                 lines.append(word)
#                 current_line = []
#             else:
#                 current_line = [word] # Commence une nouvelle ligne avec le mot
    
#     if current_line:
#         lines.append(' '.join(current_line))
#     return lines


# # --- ROUTES FLASK MODIFIÉES ---
# @app.route('/api/generate-flyer-from-prototype', methods=['POST'])
# def generate_flyer_from_prototype():
#     print("\n" + "="*80)
#     print("🚀 NOUVELLE REQUÊTE DE GÉNÉRATION API (Fond purement artistique + Styles Texte analysés)")
#     print("="*80)

#     try:
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
#             # Utilise io.BytesIO car BytesIO n'est pas importé directement pour cette partie
#             # ou vous pouvez changer cette ligne aussi pour utiliser 'BytesIO(style_image_bytes)'
#             Image.open(io.BytesIO(style_image_bytes))
#             print(f"   ✅ Image d'entrée valide (test PIL)")
#         except Exception as e:
#             error_msg = f"L'image fournie est invalide ou corrompue: {e}"
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 400
        
#         content_data = {
#             'headline1': request.form.get('headline1', 'Your Event Headline'),
#             'short_description': request.form.get('short_description', 'A brief description of your event, summarizing its purpose and key features.'),
#             'event_info': request.form.get('event_info', 'Date, Time, and Location'),
#             'footer_info': request.form.get('footer_info', 'Contact Info | Website | Phone')
#         }
#         print(f"   📝 Données textuelles reçues: {content_data}")


#         print("   ✅ Phase 1 terminée: Données valides")

#         print("\n🔍 Phase 2: Analyse de l'image d'entrée avec GPT-4o (via Replicate)")
#         try:
#             style_description = flyer_gen.describe_image_style(style_image_bytes)
#             print("   ✅ Phase 2 terminée: Image analysée")
#         except Exception as e:
#             error_msg = f'Erreur lors de l\'analyse du style de l\'image par GPT-4o (via Replicate): {str(e)}'
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 500

#         print("\n🖼️ Phase 3: Génération de l'image de fond purement artistique avec Imagen 4")
#         try:
#             flyer_background_image_url = flyer_gen.generate_textless_flyer_background(style_description, content_data)
#             print("   ✅ Phase 3 terminée: Image de fond générée")
#         except Exception as e:
#             error_msg = f'Erreur lors de la génération de l\'image de fond par Imagen (Replicate): {str(e)}'
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 500

#         print("\n🎨 Nouvelle Phase: Suggestion de styles de texte avec GPT-4o VISION (sur l'image générée)")
#         try:
#             text_style_suggestions = flyer_gen.suggest_text_styles_for_flyer(style_description, flyer_background_image_url, content_data)
#             print("   ✅ Styles de texte suggérés basés sur l'image générée et le contenu réel")
#         except Exception as e:
#             error_msg = f'Erreur lors de la suggestion des styles de texte par GPT-4o Vision (via Replicate): {str(e)}'
#             print(f"   ❌ {error_msg}")
#             return jsonify({'error': error_msg}), 500


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

# # --- NOUVELLE ROUTE POUR LA GÉNÉRATION FINALE DU FLYER CÔTÉ SERVEUR ---
# @app.route('/api/generate-final-flyer', methods=['POST'])
# def generate_final_flyer():
#     print("\n" + "="*80)
#     print("✨ NOUVELLE REQUÊTE DE GÉNÉRATION FINALE DE FLYER (Côté Serveur)")
#     print("="*80)
#     try:
#         data = request.json
#         background_url = data.get('background_url')
#         text_components = data.get('text_components', [])
#         flyer_dims = data.get('flyer_dimensions', {'width': 360, 'height': 640})

#         if not background_url:
#             return jsonify({'error': 'URL de l\'image de fond manquante.'}), 400

#         print(f"   Téléchargement de l'image de fond depuis: {background_url}")
#         response = requests.get(background_url, stream=True)
#         response.raise_for_status()
#         background_image_bytes = BytesIO(response.content) # <-- C'est ici que BytesIO était non défini
#         background = Image.open(background_image_bytes).convert("RGBA")

#         if background.width != flyer_dims['width'] or background.height != flyer_dims['height']:
#             print(f"   Redimensionnement de l'image de fond de {background.size} à {flyer_dims['width']}x{flyer_dims['height']}")
#             background = background.resize((flyer_dims['width'], flyer_dims['height']), Image.Resampling.LANCZOS)
        
#         draw = ImageDraw.Draw(background)

#         for comp in text_components:
#             content = comp.get('content', '')
#             x = comp.get('x', 0)
#             y = comp.get('y', 0)
#             style = comp.get('style', {})

#             # Convertir la largeur en pixels basée sur le pourcentage
#             width_percent = int(comp.get('width', '90%').replace('%', ''))
#             max_text_width_px = (width_percent / 100) * flyer_dims['width']

#             font_family = style.get('fontFamily', 'Arial, sans-serif').split(',')[0].strip()
#             font_size_px = style.get('fontSizePx', 24)
#             color_hex = style.get('color', '#000000')
#             text_align = style.get('textAlign', 'center')
#             line_height_em = style.get('lineHeightEm', 1.4)

#             text_color_rgb = tuple(int(color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
#             text_color_rgba = (*text_color_rgb, 255) # Couleur du texte (opaque)

#             font_path = _get_font_path(font_family)
#             try:
#                 font = ImageFont.truetype(font_path, font_size_px) if font_path else ImageFont.load_default()
#             except IOError:
#                 print(f"   AVERTISSEMENT: Impossible de charger la police '{font_family}'. Utilisation de la police par défaut.")
#                 font = ImageFont.load_default()

#             # Calculer la couleur de l'ombre en fonction de la luminosité du texte principal
#             # Utilise la formule de luminosité perçue (YIQ)
#             is_light_text_color = (text_color_rgb[0] * 0.299 + text_color_rgb[1] * 0.587 + text_color_rgb[2] * 0.114) > 186
#             shadow_color_rgba = (0, 0, 0, 180) if is_light_text_color else (255, 255, 255, 180) # Semi-transparent
#             shadow_offset = 1 # Décalage de l'ombre en pixels

#             lines = _text_wrap(content, font, max_text_width_px)
            
#             current_y = y
#             for line in lines:
#                 # Obtenir la bbox de la ligne pour calculer sa largeur réelle
#                 # textbbox((x,y), text, font) retourne (left, top, right, bottom)
#                 # Le premier (x,y) est juste un point de référence, les valeurs de la bbox sont relatives à ce point
#                 try:
#                     bbox = font.getbbox(line)
#                     line_width = bbox[2] - bbox[0] # Largeur réelle de la ligne de texte
#                 except Exception as e:
#                     print(f"   AVERTISSEMENT: Échec de font.getbbox pour ligne '{line}': {e}. Estimations utilisées.")
#                     line_width = len(line) * font.size * 0.6
                
#                 # Calculer la position X en fonction de l'alignement
#                 line_x = x # Point de départ du conteneur texte
#                 if text_align == 'center':
#                     line_x += (max_text_width_px - line_width) / 2
#                 elif text_align == 'right':
#                     line_x += (max_text_width_px - line_width)
#                 # else: (left) line_x reste x
                
#                 # Dessiner l'ombre
#                 draw.text((line_x + shadow_offset, current_y + shadow_offset), line, font=font, fill=shadow_color_rgba)
#                 # Dessiner le texte principal
#                 draw.text((line_x, current_y), line, font=font, fill=text_color_rgba)

#                 # Calculer la hauteur de la ligne suivante
#                 # La hauteur de la ligne est basée sur la taille de la police et le lineHeightEm
#                 # Une approximation est (hauteur_de_ligne_réelle_par_Pillow * lineHeightEm)
#                 # Ou simplement la taille de la police * lineHeightEm
#                 next_line_height = font_size_px * line_height_em
#                 current_y += next_line_height


#         img_io = BytesIO()
#         background.save(img_io, 'PNG', quality=95)
#         img_io.seek(0)

#         print("   ✅ Flyer final généré avec succès !")
#         return send_file(img_io, mimetype='image/png')

#     except Exception as e:
#         print(f"\n❌ ERREUR LORS DE LA GÉNÉRATION FINALE DU FLYER:")
#         print(f"   🔥 Erreur: {e}")
#         print(f"   📋 Type: {type(e).__name__}")
#         print(f"   🗂️ Traceback complet:")
#         traceback.print_exc()
#         print("="*80 + "\n")
#         return jsonify({'error': f"Une erreur interne est survenue lors de la génération du flyer final: {str(e)}"}), 500

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
        # Generate a highly detailed and artistic flyer background in a vertical 9:16 aspect ratio.
        # The visual style and atmosphere should be: {style_description}

        # ⚠️ CRITICAL INSTRUCTION:
        # DO NOT generate any text, letters, numbers, writing, words, symbols, glyphs, or anything that resembles text or typography.

        # The image must be:
        # - Fully graphical and artistic,
        # - WITHOUT ANY visible or hidden text or shapes that look like placeholders or banners,
        # - NO logos, no fake UI, no watermarks, no labels, no icons, no boxes for text.

        # 🧠 Imagine that this flyer will have 4 blocks of information added later:
        # - A title,
        # - A paragraph of description,
        # - Event details (time and location),
        # - Contact information.

        # DO NOT include or imply these elements in the image. Instead, arrange the artistic composition to leave soft, natural zones that *could be used* for text overlay — but that look organic and part of the scene.

        # 🎯 The image must feel complete and beautiful WITHOUT any indication that text should be placed somewhere. No banners, no scrolls, no outlines, no boxes.

        # ABSOLUTELY NO TEXT.
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



