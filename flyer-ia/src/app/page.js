"use client";

import { useState, useRef, useEffect, useCallback } from 'react';
import Image from 'next/image';
import Draggable from 'react-draggable';
import './globals.css';

// Liste des polices disponibles pour la sélection manuelle.
// Assurez-vous d'avoir les fichiers .ttf correspondants dans backend/fonts/
const FONT_OPTIONS = [
  'Arial, sans-serif',
  'Verdana, sans-serif',
  'Helvetica, sans-serif',
  'Georgia, serif',
  'Times New Roman, serif',
  'Courier New, monospace',
  'Impact, sans-serif',
  'Trebuchet MS, sans-serif',
  'Open Sans, sans-serif',
  'Roboto, sans-serif',
  'Playfair Display, serif',
  'Lato, sans-serif',
  'Merriweather, serif',
];

// Types d'événements islamiques prédéfinis avec descriptions en Anglais
const EVENT_TYPES = {
  mosque_opening: "Mosque Opening - Solemn inauguration ceremony with traditional Islamic architecture",
  ramadan: "Ramadan - Spiritual atmosphere with crescent moon, traditional lanterns, and golden colors",
  eid_fitr: "Eid al-Fitr - Joyful celebration marking the end of Ramadan with festive decorations and vibrant colors",
  eid_adha: "Eid al-Adha - Pilgrimage and sacrifice, solemn ambiance with Mecca motifs",
  mawlid: "Mawlid - Celebration of the Prophet's birth with elegant Arabic calligraphy and floral patterns",
  hajj: "Hajj - Pilgrimage to Mecca with the Kaaba and sacred architecture",
  islamic_wedding: "Islamic Wedding - Elegant ceremony with geometric patterns and refined colors",
  quran_recitation: "Quran Recitation - Contemplative ambiance with calligraphy and spiritual motifs",
  iftar: "Iftar - Breaking of fast meal with traditional table and warm atmosphere",
  islamic_conference: "Islamic Conference - Educational event with modern architecture and traditional elements",
  custom: "Custom - Describe your own event"
};

export default function HomePage() {
  const [logoFile, setLogoFile] = useState(null);
  const [logoPreview, setLogoPreview] = useState(null);
  const [isDraggingOver, setIsDraggingOver] = useState(false);

  const [contentInput, setContentInput] = useState({
    headline1: 'Annual Gala 2024',
    short_description: 'Join us for an unforgettable evening of celebration and networking — a unique opportunity to connect with industry leaders in an exceptional setting.',
    event_date: '2024-12-05',
    event_time: '19:00',
    event_location: 'The Grand Palace, Paris',
    footer_email: 'info@mosque-event.com',
    footer_website: 'www.mosque-event.com',
    footer_phone: '+212 5 22 12 34 56',
    event_type: 'mosque_opening',
    custom_description: ''
  });

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [flyerBackgroundUrl, setFlyerBackgroundUrl] = useState(null);
  const [logoAnalysis, setLogoAnalysis] = useState(null); // Contient l'analyse complète du logo

  const [textComponents, setTextComponents] = useState([]); // Composants actuels (avec modifications utilisateur)
  const [aiTextStyleSuggestions, setAiTextStyleSuggestions] = useState(null); // Suggestions brutes de l'IA
  const [initialAiTextComponents, setInitialAiTextComponents] = useState(null); // État initial basé sur les suggestions IA

  const [selectedComponentId, setSelectedComponentId] = useState(null);

  const flyerContainerRef = useRef(null);

  // Refs for draggable components
  const headlineRef = useRef(null);
  const descriptionRef = useRef(null);
  const eventInfoRef = useRef(null);
  const footerRef = useRef(null);
  const logoRef = useRef(null);

  const componentRefsMap = {
      headline: headlineRef,
      description: descriptionRef,
      event_info: eventInfoRef,
      footer: footerRef,
      logo: logoRef
  };

  const initializeTextComponents = useCallback((aiSuggestions, currentContentInput, currentLogoPreview) => {
    const formatDate = (dateString) => {
      if (!dateString) return '';
      try {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
      } catch (e) {
        console.error("Error formatting date:", e);
        return dateString;
      }
    };

    const eventDetails = [
      currentContentInput.event_date ? formatDate(currentContentInput.event_date) : '',
      currentContentInput.event_time,
      currentContentInput.event_location
    ].filter(Boolean).join(' - ');

    const footerDetails = [
      currentContentInput.footer_email,
      currentContentInput.footer_website,
      currentContentInput.footer_phone
    ].filter(Boolean).join(' | ');

    const rawComponents = [
      { id: 'headline', type: 'headline', content: currentContentInput.headline1 },
      { id: 'description', type: 'body', content: currentContentInput.short_description },
      { id: 'event_info', type: 'event_info', content: eventDetails },
      { id: 'footer', type: 'footer', content: footerDetails },
    ];

    if (currentLogoPreview) { // S'assurer que le logo est ajouté si une preview existe
      rawComponents.push({
        id: 'logo',
        type: 'logo',
        content: '', // Le contenu est l'image elle-même
        isImage: true,
        imageUrl: currentLogoPreview
      });
    }

    // Dimensions du flyer en prévisualisation (pour convertir les pourcentages en pixels initiaux)
    const previewWidth = 360;
    const previewHeight = 640;

    const styledComponents = rawComponents.map(comp => {
      const style = aiSuggestions[comp.type] || {};

      // Déclarer avec `let` car elles seront réassignées (Math.max)
      let initialY = (style.initialTopPercentage / 100) * previewHeight;
      const initialWidthPx = (style.initialWidthPercentage / 100) * previewWidth;
      let initialX = (style.initialLeftPercentage / 100) * previewWidth;

      // Ajuster l'X pour l'alignement horizontal du logo si nécessaire
      if (comp.type === 'logo' && style.horizontalAlignment === 'center') {
        // Si l'IA a suggéré initialLeftPercentage = 50% pour un centre, alors le X doit être 50% - (largeur_logo/2)
        // La largeur est déjà en % via initialWidthPercentage, donc on ajuste initialX pour le coin supérieur gauche du logo.
        initialX = initialX - (initialWidthPx / 2);
      } else if (comp.type === 'logo' && style.horizontalAlignment === 'right') {
        // Si l'IA a suggéré initialLeftPercentage pour être le point de départ d'un conteneur qui aligne le logo à droite,
        // alors initialX doit être ajusté pour que le coin supérieur gauche du logo soit à initialLeftPercentage - largeur_logo
        initialX = initialX - initialWidthPx;
      }
      // Assurer que les positions initiales sont au moins 0
      initialX = Math.max(0, initialX);
      initialY = Math.max(0, initialY);

      // --- Gestion de l'effet d'ombre pour tous les composants ---
      let shadowEffect = null;
      if (comp.isImage) {
        // Pour les logos, utiliser directement le shadowEffect fourni par l'IA
        shadowEffect = style.shadowEffect || { apply: false, color: "#000000A0", offsetPx: 3, blurPx: 4 };
      } else {
        // Pour le texte, si l'IA a suggéré un textShadow (string CSS), le parser en objet shadowEffect
        if (style.textShadow) {
          const match = style.textShadow.match(/(-?\d+)px\s+(-?\d+)px\s+(\d+)px\s+(.+)/);
          if (match) {
            const offset = parseInt(match[1]); // On prend le premier offset pour simplifier
            const blur = parseInt(match[3]);
            const color = match[4];
            shadowEffect = {
              apply: true,
              color: color,
              offsetPx: offset,
              blurPx: blur
            };
          } else {
             // Fallback si le format n'est pas reconnu (ex: "2px 2px 4px rgba(0,0,0,0.8)")
             const defaultColor = style.color ? (parseInt(style.color.replace('#', ''), 16) > 0xFFFFFF / 2 ? 'rgba(0, 0, 0, 0.8)' : 'rgba(255, 255, 255, 0.8)') : 'rgba(0, 0, 0, 0.8)';
             shadowEffect = { apply: true, color: defaultColor, offsetPx: 2, blurPx: 4 };
          }
        } else {
          // Par défaut, pas d'ombre si non suggéré par l'IA
          const defaultColor = style.color ? (parseInt(style.color.replace('#', ''), 16) > 0xFFFFFF / 2 ? 'rgba(0, 0, 0, 0.8)' : 'rgba(255, 255, 255, 0.8)') : 'rgba(0, 0, 0, 0.8)';
          shadowEffect = { apply: false, color: defaultColor, offsetPx: 2, blurPx: 4 };
        }
      }

      // Générer la propriété CSS textShadow à partir de l'objet shadowEffect pour la prévisualisation
      const cssTextShadow = shadowEffect.apply
        ? `${shadowEffect.offsetPx}px ${shadowEffect.offsetPx}px ${shadowEffect.blurPx}px ${shadowEffect.color}`
        : 'none';


      return {
        ...comp,
        x: initialX, // Position initiale en pixels (draggable gère ça)
        y: initialY, // Position initiale en pixels
        width: `${style.initialWidthPercentage || (comp.type === 'logo' ? 30 : 90)}%`, // Largeur en pourcentage
        minHeightPx: style.minHeightPx || (comp.type === 'logo' ? 80 : 0), // Hauteur minimale en pixels
        style: {
          fontFamily: style.fontFamily || 'Arial, sans-serif',
          color: style.color || '#FFFFFF', // Couleur du texte principal
          fontSize: `${style.fontSizePx || 24}px`, // Taille de police en pixels
          fontWeight: style.fontWeight || 'normal',
          textAlign: style.textAlign || 'center',
          lineHeight: `${style.lineHeightEm || 1.4}em`, // Hauteur de ligne en em
          textShadow: comp.isImage ? 'none' : cssTextShadow, // Propriété CSS textShadow pour la prévisualisation
          shadowEffect: shadowEffect, // Objet de configuration d'ombre interne
        }
      };
    });
    return styledComponents;
  }, []); // Dépendances pour useCallback

  useEffect(() => {
    // Si l'arrière-plan et les suggestions de l'IA sont disponibles, initialiser les composants
    if (aiTextStyleSuggestions && flyerBackgroundUrl) {
      const newComponents = initializeTextComponents(aiTextStyleSuggestions, contentInput, logoPreview);
      setTextComponents(newComponents);
      setInitialAiTextComponents(newComponents); // Sauvegarder pour le reset
    }
  }, [aiTextStyleSuggestions, flyerBackgroundUrl, contentInput, logoPreview, initializeTextComponents]);


  const processFile = (file) => {
    if (file) {
      if (file.type.startsWith('image/')) {
        setLogoFile(file);
        const reader = new FileReader();
        reader.onloadend = () => {
          setLogoPreview(reader.result);
          // Réinitialiser le flyer et les suggestions à chaque nouveau logo
          setError(null);
          setFlyerBackgroundUrl(null);
          setTextComponents([]);
          setAiTextStyleSuggestions(null);
          setInitialAiTextComponents(null);
          setSelectedComponentId(null);
          setLogoAnalysis(null);
        };
        reader.readAsDataURL(file);
      } else {
        setError("Please upload a valid image file (JPG, PNG, GIF, etc.).");
        setLogoFile(null);
        setLogoPreview(null);
      }
    }
  };

  const handleImageChange = (e) => {
    processFile(e.target.files[0]);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDraggingOver(true);
  };

  const handleDragLeave = () => {
    setIsDraggingOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDraggingOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleContentInputChange = (e) => {
    const { name, value } = e.target;
    setContentInput(prev => ({ ...prev, [name]: value }));

    // Mettre à jour le contenu des composants textuels en direct
    setTextComponents(prevComponents =>
      prevComponents.map(comp => {
        let newContent = comp.content;
        const updatedContentInput = { ...contentInput, [name]: value }; // Utiliser l'état mis à jour

        const formatDate = (dateString) => {
          if (!dateString) return '';
          try {
            const date = new Date(dateString);
            return date.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
          } catch (e) {
            return dateString;
          }
        };

        if (comp.id === 'headline' && name === 'headline1') {
          newContent = value;
        } else if (comp.id === 'description' && name === 'short_description') {
          newContent = value;
        } else if (comp.id === 'event_info' && ['event_date', 'event_time', 'event_location'].includes(name)) {
          newContent = [
            updatedContentInput.event_date ? formatDate(updatedContentInput.event_date) : '',
            updatedContentInput.event_time,
            updatedContentInput.event_location
          ].filter(Boolean).join(' - ');
        } else if (comp.id === 'footer' && ['footer_email', 'footer_website', 'footer_phone'].includes(name)) {
          newContent = [
            updatedContentInput.footer_email,
            updatedContentInput.footer_website,
            updatedContentInput.footer_phone
          ].filter(Boolean).join(' | ');
        }
        return { ...comp, content: newContent };
      })
    );
  };

  const handleComponentClick = (id) => {
    setSelectedComponentId(id);
  };

  const handleStyleChange = (styleProp, value) => {
    setTextComponents(prevComponents =>
      prevComponents.map(comp => {
        if (comp.id === selectedComponentId) {
          const newStyle = { ...comp.style };
          let newWidth = comp.width;
          let newMinHeightPx = comp.minHeightPx;

          // --- Gérer les propriétés de base ---
          if (styleProp === 'fontSize') {
            newStyle.fontSize = `${value}px`;
          } else if (styleProp === 'color') {
            newStyle.color = value;
            // Si l'ombre est appliquée, ajuster sa couleur par défaut pour le contraste
            if (newStyle.shadowEffect && newStyle.shadowEffect.apply) {
                const isLightColor = parseInt(value.replace('#', ''), 16) > 0xFFFFFF / 2;
                newStyle.shadowEffect.color = isLightColor ? 'rgba(0, 0, 0, 0.8)' : 'rgba(255, 255, 255, 0.8)';
            }
          } else if (styleProp === 'width') {
            newWidth = `${value}%`;
          } else if (styleProp === 'minHeightPx') {
            newMinHeightPx = value;
          } else if (styleProp === 'fontFamily') {
            newStyle.fontFamily = value;
          } else if (styleProp === 'textAlign') {
            newStyle.textAlign = value;
          }

          // --- Gérer les propriétés de shadowEffect ---
          if (newStyle.shadowEffect) { // S'assurer que l'objet existe
              if (styleProp === 'shadowApply') {
                  newStyle.shadowEffect.apply = value;
                  // Si on active l'ombre et qu'elle n'a pas de couleur, lui donner une par défaut basée sur la couleur du texte
                  if (value && !newStyle.shadowEffect.color) {
                      const isLightColor = parseInt(newStyle.color.replace('#', ''), 16) > 0xFFFFFF / 2;
                      newStyle.shadowEffect.color = isLightColor ? 'rgba(0, 0, 0, 0.8)' : 'rgba(255, 255, 255, 0.8)';
                  }
              } else if (styleProp === 'shadowColor') {
                  newStyle.shadowEffect.color = value;
              } else if (styleProp === 'shadowOffsetPx') {
                  newStyle.shadowEffect.offsetPx = parseInt(value);
              } else if (styleProp === 'shadowBlurPx') {
                  newStyle.shadowEffect.blurPx = parseInt(value);
              }
          }


          // Re-générer la propriété CSS textShadow à partir de l'objet shadowEffect mis à jour
          if (!comp.isImage && newStyle.shadowEffect) { // Seulement pour le texte
            newStyle.textShadow = newStyle.shadowEffect.apply
              ? `${newStyle.shadowEffect.offsetPx}px ${newStyle.shadowEffect.offsetPx}px ${newStyle.shadowEffect.blurPx}px ${newStyle.shadowEffect.color}`
              : 'none';
          }

          return { ...comp, style: newStyle, width: newWidth, minHeightPx: newMinHeightPx };
        }
        return comp;
      })
    );
  };

  const handleComponentTextChange = (id, newText) => {
    setTextComponents(prevComponents =>
      prevComponents.map(comp => (comp.id === id ? { ...comp, content: newText } : comp))
    );
  };

  const handleStopDrag = (e, data, id) => {
    setTextComponents(prevComponents =>
      prevComponents.map(comp =>
        comp.id === id ? { ...comp, x: data.x, y: data.y } : comp
      )
    );
  };

  const getBackgroundDescription = () => {
    if (contentInput.event_type === 'custom') {
      return contentInput.custom_description || 'Custom event with traditional Islamic elements';
    }
    return EVENT_TYPES[contentInput.event_type] || EVENT_TYPES.mosque_opening;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!logoFile) {
        setError("Please choose an organization logo.");
        return;
    }

    setIsLoading(true);
    setError(null);
    setFlyerBackgroundUrl(null);
    setTextComponents([]); // Réinitialiser avant nouvelle génération
    setAiTextStyleSuggestions(null);
    setInitialAiTextComponents(null);
    setSelectedComponentId(null);
    setLogoAnalysis(null);

    const formData = new FormData();
    formData.append('logo_image', logoFile);
    formData.append('headline1', contentInput.headline1);
    formData.append('short_description', contentInput.short_description);
    formData.append('background_description', getBackgroundDescription());

    const eventDetails = [
      contentInput.event_date ? new Date(contentInput.event_date).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }) : '',
      contentInput.event_time,
      contentInput.event_location
    ].filter(Boolean).join(' - ');
    formData.append('event_info', eventDetails);

    const footerDetails = [
      contentInput.footer_email,
      contentInput.footer_website,
      contentInput.footer_phone
    ].filter(Boolean).join(' | ');
    formData.append('footer_info', footerDetails);

    try {
      const baseUrl = process.env.NODE_ENV === 'development'
        ? 'http://localhost:5000'
        : window.location.origin;

      const response = await fetch(`${baseUrl}/api/generate-islamic-flyer`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Error during flyer generation (step 1).');
      }

      const data = await response.json();
      setFlyerBackgroundUrl(data.flyer_background_url);
      setAiTextStyleSuggestions(data.text_style_suggestions); // Suggestions de style basées sur l'analyse visuelle IA
      setLogoAnalysis(data.logo_analysis);
      console.log("AI Suggestions received:", data.text_style_suggestions);
      console.log("Logo Analysis received:", data.logo_analysis);

    } catch (err) {
      console.error("Error during flyer generation:", err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  // La fonction handleDownloadFlyer appelle maintenant directement la fonction de téléchargement côté serveur
  const handleDownloadFlyer = async () => {
    if (!flyerBackgroundUrl || textComponents.length === 0) {
      setError("No flyer generated yet or components are missing. Please generate one first.");
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      await handleDownloadFlyerServerSide();
      alert("Your Islamic flyer has been downloaded successfully (server-side)!");
    } catch (serverError) {
      console.error("Error during server-side generation:", serverError);
      setError(`Failed to download flyer: ${serverError.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownloadFlyerServerSide = async () => {
    const baseUrl = process.env.NODE_ENV === 'development'
        ? 'http://localhost:5000'
        : window.location.origin;

    // Préparer les données des composants pour le backend
    const textData = textComponents.map(comp => {
      // Nettoyer les props de style pour ne garder que celles nécessaires pour le backend
      const cleanedStyle = {
        fontFamily: comp.style.fontFamily,
        color: comp.style.color,
        fontSizePx: parseInt(comp.style.fontSize) || 24,
        fontWeight: comp.style.fontWeight,
        textAlign: comp.style.textAlign,
        lineHeightEm: parseFloat(comp.style.lineHeight) || 1.4,
      };
      // Ajouter l'effet d'ombre (pour texte ET logo) si applicable
      if (comp.style.shadowEffect && comp.style.shadowEffect.apply) {
        cleanedStyle.shadowEffect = comp.style.shadowEffect;
      }

      return {
          id: comp.id,
          content: comp.content,
          x: Math.round(comp.x), // Envoyer les positions en pixels
          y: Math.round(comp.y), // Envoyer les positions en pixels
          width: comp.width, // Largeur en pourcentage
          isImage: comp.isImage || false,
          imageUrl: comp.imageUrl || null,
          style: cleanedStyle,
          minHeightPx: comp.minHeightPx || 0
      };
    });

    console.log("Sending data to server for final generation:", textData);

    const response = await fetch(`${baseUrl}/api/generate-final-flyer`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            background_url: flyerBackgroundUrl,
            text_components: textData,
            flyer_dimensions: {
                width: 360,
                height: 640
            }
        })
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(`Server Error: ${errorData.error || 'Failed to generate final flyer'}`);
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `islamic_flyer_server_side_${contentInput.headline1.replace(/\s+/g, '_')}_${new Date().getTime()}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);

  };

  const handleResetStyles = () => {
    if (initialAiTextComponents) {
        // Créer une copie profonde pour éviter les références directes
        const resetComponents = initialAiTextComponents.map(comp => ({
            ...comp,
            style: { ...comp.style }
        }));
        setTextComponents(resetComponents);
        setSelectedComponentId(null);
        alert("Styles have been reset to AI suggestions.");
    } else {
        alert("No initial AI suggestions to reset. Generate a flyer first.");
    }
  };

  const selectedComponent = textComponents.find(comp => comp.id === selectedComponentId);

  return (
    <div className="App">
      <header className="App-header">
        <h1>🕌 AI Islamic Flyer Generator</h1>
        <p>Upload your organization's logo, describe your Islamic event, and let AI create a personalized flyer with colors inspired by your logo.</p>
      </header>

      {/* Main content area: 3 columns on large screens, stacked on small */}
      <main className="flex flex-col lg:flex-row w-full max-w-7xl gap-8 mx-auto">

        {/* --- Column 1: Input Form --- */}
        <div className="form-input-section w-full lg:w-1/3">
          <h2 className="text-2xl font-bold mb-4 text-center text-teal-700">Create Your Flyer</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* --- SECTION 1 : ORGANIZATION LOGO --- */}
            <fieldset>
              <legend>1. Your Organization's Logo</legend>
              <p className="field-description">Upload your mosque/organization's logo. The AI will draw inspiration from its colors to create the background.</p>

              <div
                className={`drop-zone ${isDraggingOver ? 'drag-over' : ''}`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
              >
                <p>Drag & drop your logo here, or</p>
                <label htmlFor="logo-upload-input" className="custom-file-upload">
                  {logoFile ? "Change Logo" : "Choose a Logo"}
                </label>
                <input
                  id="logo-upload-input"
                  type="file"
                  accept="image/*"
                  onChange={handleImageChange}
                />
              </div>

              {logoPreview && <div className="image-preview-container"><img src={logoPreview} alt="Logo Preview" className="image-preview" /></div>}
              {error && !logoFile && <p className="error-message">{error}</p>}
            </fieldset>

            {/* --- SECTION 2 : EVENT TYPE --- */}
            <fieldset>
              <legend>2. Islamic Event Type</legend>

              <label htmlFor="event_type">Event Type:</label>
              <select
                id="event_type"
                name="event_type"
                value={contentInput.event_type}
                onChange={handleContentInputChange}
                className="mt-1"
              >
                {Object.entries(EVENT_TYPES).map(([key, value]) => (
                  <option key={key} value={key}>
                    {value.split(' - ')[0]}
                  </option>
                ))}
              </select>

              {contentInput.event_type === 'custom' && (
                <div>
                  <label htmlFor="custom_description">Custom Event Description:</label>
                  <p className="field-description">Describe your event so the AI can create an appropriate background.</p>
                  <textarea
                    id="custom_description"
                    name="custom_description"
                    value={contentInput.custom_description}
                    onChange={handleContentInputChange}
                    rows={3}
                    placeholder="Ex: Conference on Islamic education with modern decor and traditional elements..."
                  />
                </div>
              )}

              <div className={`event-type-description event-type-${contentInput.event_type}`}>
                <p><strong>Background Style Description:</strong> {getBackgroundDescription()}</p>
              </div>
            </fieldset>

            {/* --- SECTION 3 : FLYER CONTENT --- */}
            <fieldset>
              <legend>3. Flyer Content</legend>

              <label htmlFor="headline1">Main Headline</label>
              <input
                type="text"
                id="headline1"
                name="headline1"
                value={contentInput.headline1}
                onChange={handleContentInputChange}
                placeholder="Ex: Grand Mosque Opening"
              />

              <label htmlFor="short_description">Description</label>
              <p className="field-description">A brief description of your event.</p>
              <textarea
                id="short_description"
                name="short_description"
                value={contentInput.short_description}
                onChange={handleContentInputChange}
                rows={4}
                placeholder="Describe your event..."
              />

              <div className="event-grid">
                <div>
                  <label htmlFor="event_date">Date</label>
                  <input type="date" id="event_date" name="event_date" value={contentInput.event_date} onChange={handleContentInputChange}/>
                </div>
                <div>
                  <label htmlFor="event_time">Time</label>
                  <input type="time" id="event_time" name="event_time" value={contentInput.event_time} onChange={handleContentInputChange}/>
                </div>
                <div className="full-width">
                  <label htmlFor="event_location">Location</label>
                  <input
                    type="text"
                    id="event_location"
                    name="event_location"
                    value={contentInput.event_location}
                    onChange={handleContentInputChange}
                    placeholder="Ex: Grand Mosque, Casablanca"
                  />
                </div>
              </div>
            </fieldset>

            {/* --- SECTION 4 : CONTACT --- */}
            <fieldset>
              <legend>4. Contact Information</legend>
              <div className="contact-grid">
                <div>
                  <label htmlFor="footer_email">Email</label>
                  <input type="email" id="footer_email" name="footer_email" value={contentInput.footer_email} onChange={handleContentInputChange}/>
                </div>
                <div>
                  <label htmlFor="footer_website">Website</label>
                  <input type="text" id="footer_website" name="footer_website" value={contentInput.footer_website} onChange={handleContentInputChange}/>
                </div>
                <div>
                  <label htmlFor="footer_phone">Phone</label>
                  <input type="text" id="footer_phone" name="footer_phone" value={contentInput.footer_phone} onChange={handleContentInputChange}/>
                </div>
              </div>
            </fieldset>

            <button type="submit" disabled={isLoading || !logoFile} className="generate-btn">
               {isLoading ? `Generating Islamic Flyer...` : `🎨 Generate Islamic Flyer`}
            </button>
          </form>
        </div>

        {/* --- Column 2: Generated Flyer Preview --- */}
        <div className="flyer-display-section w-full lg:w-1/3 flex flex-col items-center">
            {isLoading && <div className="loading-container"><div className="loader"></div><p>Generating your personalized Islamic flyer...</p></div>}
            {error && <p className="error-message">{error}</p>}

            {flyerBackgroundUrl && (
                <div className="flyer-viewer-and-button"> {/* Wrapper for image and download button */}
                    <h2>Your Islamic Flyer is Ready! 🕌✨</h2>
                    <p>Click on an element (text or logo) to select it, then drag to reposition or use the controls to adjust styles.</p>

                    <div className="generated-flyer-preview-wrapper" onClick={() => setSelectedComponentId(null)}>
                        <div
                            className="generated-flyer-preview"
                            ref={flyerContainerRef}
                            style={{
                                position: 'relative',
                                width: '360px',
                                height: '640px',
                                margin: '0 auto',
                                overflow: 'hidden',
                                transform: 'translateZ(0)',
                                backfaceVisibility: 'hidden',
                                perspective: '1000px',
                            }}
                        >
                            {flyerBackgroundUrl && (
                                <img
                                    src={flyerBackgroundUrl}
                                    alt="Islamic Flyer Background"
                                    className="generated-background-image"
                                    style={{
                                        position: 'absolute',
                                        top: '0',
                                        left: '0',
                                        width: '100%',
                                        height: '100%',
                                        objectFit: 'cover',
                                        zIndex: '1',
                                        imageRendering: 'high-quality'
                                    }}
                                />
                            )}

                            {textComponents.map(comp => {
                                const nodeRef = componentRefsMap[comp.id] || useRef(null);

                                if (comp.isImage && comp.imageUrl) {
                                    return (
                                        <Draggable
                                            key={comp.id}
                                            nodeRef={nodeRef}
                                            bounds="parent"
                                            position={{ x: comp.x, y: comp.y }}
                                            onStop={(e, data) => handleStopDrag(e, data, comp.id)}
                                        >
                                            <div
                                                ref={nodeRef}
                                                className={`image-draggable-component ${selectedComponentId === comp.id ? 'selected' : ''}`}
                                                style={{
                                                    width: comp.width,
                                                    minHeight: comp.minHeightPx ? `${comp.minHeightPx}px` : 'auto',
                                                    position: 'absolute',
                                                    zIndex: '3',
                                                    cursor: 'grab',
                                                    border: selectedComponentId === comp.id ? '2px dashed var(--islamic-green)' : 'none',
                                                    borderRadius: '4px',
                                                    display: 'flex',
                                                    justifyContent: 'center',
                                                    alignItems: 'center',
                                                }}
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleComponentClick(comp.id);
                                                }}
                                            >
                                                <img
                                                    src={comp.imageUrl}
                                                    alt="Organization Logo"
                                                    style={{
                                                        width: '100%',
                                                        height: 'auto',
                                                        maxHeight: '100px',
                                                        objectFit: 'contain',
                                                        borderRadius: '4px',
                                                        filter: comp.style.shadowEffect && comp.style.shadowEffect.apply
                                                            ? `drop-shadow(${comp.style.shadowEffect.offsetPx}px ${comp.style.shadowEffect.offsetPx}px ${comp.style.shadowEffect.blurPx}px ${comp.style.shadowEffect.color})`
                                                            : 'none'
                                                    }}
                                                />
                                            </div>
                                        </Draggable>
                                    );
                                }

                                const containerWidthInPixels = (parseFloat(comp.width) / 100) * 360;
                                const estimatedCharsPerLine = containerWidthInPixels / ((parseInt(comp.style.fontSize) || 24) * 0.55);
                                const estimatedRows = Math.max(1, Math.ceil(comp.content.length / estimatedCharsPerLine));

                                return (
                                    <Draggable
                                        key={comp.id}
                                        nodeRef={nodeRef}
                                        bounds="parent"
                                        position={{ x: comp.x, y: comp.y }}
                                        onStop={(e, data) => handleStopDrag(e, data, comp.id)}
                                    >
                                        <div
                                            ref={nodeRef}
                                            className={`text-draggable-component text-type-${comp.type} ${selectedComponentId === comp.id ? 'selected' : ''}`}
                                            style={{
                                                ...comp.style, // Appliquer les styles (font, color, etc.)
                                                width: comp.width, // Appliquer la largeur en %
                                                minHeight: comp.minHeightPx ? `${comp.minHeightPx}px` : 'auto', // Appliquer la hauteur min
                                                position: 'absolute',
                                                zIndex: '2',
                                                cursor: 'grab',
                                            }}
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleComponentClick(comp.id);
                                            }}
                                        >
                                            <textarea
                                                value={comp.content}
                                                onChange={(e) => handleComponentTextChange(comp.id, e.target.value)}
                                                style={{
                                                    fontFamily: comp.style.fontFamily,
                                                    fontSize: comp.style.fontSize,
                                                    fontWeight: comp.style.fontWeight,
                                                    textAlign: comp.style.textAlign,
                                                    color: comp.style.color,
                                                    lineHeight: comp.style.lineHeight,
                                                    textShadow: comp.style.textShadow, // Appliquer l'ombre du texte

                                                    width: '100%',
                                                    height: 'auto',
                                                    resize: 'none',
                                                    border: 'none',
                                                    background: 'transparent',
                                                    padding: 0,
                                                    margin: 0,
                                                    outline: 'none',
                                                    whiteSpace: 'pre-wrap',
                                                }}
                                                rows={estimatedRows}
                                            />
                                        </div>
                                    </Draggable>
                                );
                            })}
                        </div>
                    </div>
                    <button onClick={handleDownloadFlyer} disabled={isLoading} className="download-btn">
                      {isLoading ? "Preparing for Download..." : "📥 Download Full Islamic Flyer"}
                    </button>
                </div>
            )}
        </div>

        {/* --- Column 3: Style Control Toolbar --- */}
        <div className="style-control-section w-full lg:w-1/3 p-4"> {/* Added padding */}
            {/* Toolbar for style modification - only visible if a flyer is generated */}
            {flyerBackgroundUrl && (
                <>
                    {selectedComponent && (
                        <div className="style-toolbar">
                            <h3>Edit {selectedComponent.id.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</h3>

                            {!selectedComponent.isImage && ( // Controls for Text Components
                                <>
                                    <div className="control-group">
                                        <label htmlFor="font-family-select">Font Family:</label>
                                        <select
                                            id="font-family-select"
                                            value={selectedComponent.style.fontFamily || 'Arial, sans-serif'}
                                            onChange={(e) => handleStyleChange('fontFamily', e.target.value)}
                                            style={{ fontFamily: selectedComponent.style.fontFamily }}
                                        >
                                            {FONT_OPTIONS.map(font => (
                                                <option key={font} value={font} style={{ fontFamily: font }}>
                                                    {font.split(',')[0]}
                                                </option>
                                            ))}
                                        </select>
                                    </div>

                                    <div className="control-group">
                                        <label htmlFor="font-size-slider">Font Size (px):</label>
                                        <input
                                            type="range"
                                            id="font-size-slider"
                                            min="10"
                                            max="100"
                                            value={parseInt(selectedComponent.style.fontSize) || 24}
                                            onChange={(e) => handleStyleChange('fontSize', e.target.value)}
                                        />
                                        <span>{parseInt(selectedComponent.style.fontSize) || 24}px</span>
                                    </div>

                                    <div className="control-group">
                                        <label htmlFor="text-color-picker">Text Color:</label>
                                        <input
                                            type="color"
                                            id="text-color-picker"
                                            value={selectedComponent.style.color || '#FFFFFF'}
                                            onChange={(e) => handleStyleChange('color', e.target.value)}
                                        />
                                    </div>

                                    <div className="control-group">
                                        <label htmlFor="text-align-select">Text Alignment:</label>
                                        <select
                                            id="text-align-select"
                                            value={selectedComponent.style.textAlign || 'center'}
                                            onChange={(e) => handleStyleChange('textAlign', e.target.value)}
                                        >
                                            <option value="left">Left</option>
                                            <option value="center">Center</option>
                                            <option value="right">Right</option>
                                        </select>
                                    </div>

                                    {/* --- Shadow Controls for Text --- */}
                                    {selectedComponent.style.shadowEffect && (
                                        <div className="control-group shadow-controls">
                                            <label>
                                                <input
                                                    type="checkbox"
                                                    checked={selectedComponent.style.shadowEffect.apply}
                                                    onChange={(e) => handleStyleChange('shadowApply', e.target.checked)}
                                                />
                                                Apply Shadow
                                            </label>

                                            {selectedComponent.style.shadowEffect.apply && (
                                                <>
                                                    <div className="control-group">
                                                        <label htmlFor="shadow-color-picker">Shadow Color:</label>
                                                        <input
                                                            type="color"
                                                            id="shadow-color-picker"
                                                            value={selectedComponent.style.shadowEffect.color.startsWith('rgba') ? selectedComponent.style.shadowEffect.color.substring(0,7) : selectedComponent.style.shadowEffect.color || '#000000'}
                                                            onChange={(e) => handleStyleChange('shadowColor', e.target.value)}
                                                        />
                                                    </div>

                                                    <div className="control-group">
                                                        <label htmlFor="shadow-offset-slider">Shadow Offset (px):</label>
                                                        <input
                                                            type="range"
                                                            id="shadow-offset-slider"
                                                            min="0"
                                                            max="10"
                                                            value={selectedComponent.style.shadowEffect.offsetPx || 0}
                                                            onChange={(e) => handleStyleChange('shadowOffsetPx', e.target.value)}
                                                        />
                                                        <span>{selectedComponent.style.shadowEffect.offsetPx || 0}px</span>
                                                    </div>

                                                    <div className="control-group">
                                                        <label htmlFor="shadow-blur-slider">Shadow Blur (px):</label>
                                                        <input
                                                            type="range"
                                                            id="shadow-blur-slider"
                                                            min="0"
                                                            max="20"
                                                            value={selectedComponent.style.shadowEffect.blurPx || 0}
                                                            onChange={(e) => handleStyleChange('shadowBlurPx', e.target.value)}
                                                        />
                                                        <span>{selectedComponent.style.shadowEffect.blurPx || 0}px</span>
                                                    </div>
                                                </>
                                            )}
                                        </div>
                                    )}
                                </>
                            )} {/* End Text Controls */}

                            {/* --- General Width & Min-Height Controls (applies to both text and logo) --- */}
                            <div className="control-group">
                                <label htmlFor="width-slider">
                                    {selectedComponent.isImage ? 'Logo Width (%)' : 'Container Width (%)'}:
                                </label>
                                <input
                                    type="range"
                                    id="width-slider"
                                    min={selectedComponent.isImage ? "20" : "50"}
                                    max={selectedComponent.isImage ? "60" : "100"}
                                    value={parseInt(selectedComponent.width) || 90}
                                    onChange={(e) => handleStyleChange('width', e.target.value)}
                                />
                                <span>{parseInt(selectedComponent.width) || 90}%</span>
                            </div>

                            <div className="control-group">
                                <label htmlFor="min-height-slider">Min. Container Height (px):</label>
                                <input
                                    type="range"
                                    id="min-height-slider"
                                    min="0"
                                    max={selectedComponent.isImage ? "150" : "200"}
                                    step="5"
                                    value={selectedComponent.minHeightPx || 0}
                                    onChange={(e) => handleStyleChange('minHeightPx', parseInt(e.target.value))}
                                />
                                <span>{selectedComponent.minHeightPx || 0}px</span>
                            </div>


                            {selectedComponent.isImage && selectedComponent.style.shadowEffect && ( // Controls for Logo
                                <div className="control-group shadow-controls">
                                    <label>
                                        <input
                                            type="checkbox"
                                            checked={selectedComponent.style.shadowEffect.apply}
                                            onChange={(e) => handleStyleChange('shadowApply', e.target.checked)}
                                        />
                                        Apply Logo Shadow
                                    </label>
                                    {selectedComponent.style.shadowEffect.apply && (
                                        <>
                                            <div className="control-group">
                                                <label htmlFor="logo-shadow-color-picker">Shadow Color:</label>
                                                <input
                                                    type="color"
                                                    id="logo-shadow-color-picker"
                                                    value={selectedComponent.style.shadowEffect.color.startsWith('#') ? selectedComponent.style.shadowEffect.color.substring(0,7) : '#000000'} // Ensure HEX for picker
                                                    onChange={(e) => handleStyleChange('shadowColor', e.target.value + 'A0')} // Add alpha back
                                                />
                                            </div>
                                            <div className="control-group">
                                                <label htmlFor="logo-shadow-offset-slider">Shadow Offset (px):</label>
                                                <input
                                                    type="range"
                                                    id="logo-shadow-offset-slider"
                                                    min="0"
                                                    max="10"
                                                    value={selectedComponent.style.shadowEffect.offsetPx || 0}
                                                    onChange={(e) => handleStyleChange('shadowOffsetPx', e.target.value)}
                                                />
                                                <span>{selectedComponent.style.shadowEffect.offsetPx || 0}px</span>
                                            </div>
                                            <div className="control-group">
                                                <label htmlFor="logo-shadow-blur-slider">Shadow Blur (px):</label>
                                                <input
                                                    type="range"
                                                    id="logo-shadow-blur-slider"
                                                    min="0"
                                                    max="20"
                                                    value={selectedComponent.style.shadowEffect.blurPx || 0}
                                                    onChange={(e) => handleStyleChange('shadowBlurPx', e.target.value)}
                                                />
                                                <span>{selectedComponent.style.shadowEffect.blurPx || 0}px</span>
                                            </div>
                                        </>
                                    )}
                                </div>
                            )} {/* End Logo Controls */}

                            <button type="button" onClick={handleResetStyles} disabled={!initialAiTextComponents} className="reset-btn">
                                Reset Styles (AI Suggestions)
                            </button>
                        </div>
                    )}
                    {/* Reset AI Styles button outside of selectedComponent conditional to always be visible after generation */}
                    {initialAiTextComponents && !selectedComponent && (
                        <div className="style-toolbar text-center">
                            <button type="button" onClick={handleResetStyles} className="reset-btn">
                                Reset Styles (AI Suggestions)
                            </button>
                            <p className="text-gray-600 text-sm mt-2">Click on a flyer element to modify it.</p>
                        </div>
                    )}
                </>
            )}
        </div>
      </main>
    </div>
  );
}
















// // FLYER-IA/flyer-ia/frontend/app/page.js
// "use client";

// import { useState, useRef, useEffect, useCallback } from 'react';
// import Image from 'next/image';
// import html2canvas from 'html2canvas';
// import Draggable from 'react-draggable';
// import './globals.css';

// // Liste des polices disponibles pour la sélection manuelle (assurez-vous qu'elles sont importées dans globals.css)
// const FONT_OPTIONS = [
//   'Arial, sans-serif',
//   'Verdana, sans-serif',
//   'Helvetica, sans-serif',
//   'Georgia, serif',
//   'Times New Roman, serif',
//   'Courier New, monospace',
//   'Impact, sans-serif',
//   'Trebuchet MS, sans-serif',
//   'Open Sans, sans-serif',
//   'Roboto, sans-serif',
//   'Playfair Display, serif',
//   'Lato, sans-serif', // Ajouté
//   'Merriweather, serif', // Ajouté
// ];

// export default function HomePage() {
//   const [imageFile, setImageFile] = useState(null);
//   const [imagePreview, setImagePreview] = useState(null);
//   const [isDraggingOver, setIsDraggingOver] = useState(false);

//   const [contentInput, setContentInput] = useState({
//     headline1: 'Gala Annuel 2024',
//     short_description: 'Join us for an unforgettable evening of celebration and networking — a unique opportunity to connect with industry leaders in an exceptional setting.',
//     event_date: '2024-12-05',
//     event_time: '19:00',
//     event_location: 'Le Grand Palais, Paris',
//     footer_email: 'rsvp@votre-gala.com',
//     footer_website: 'www.votre-gala.com',
//     footer_phone: '+33 1 98 76 54 32'
//   });

//   const [isLoading, setIsLoading] = useState(false);
//   const [error, setError] = useState(null);
//   const [flyerBackgroundUrl, setFlyerBackgroundUrl] = useState(null);

//   const [textComponents, setTextComponents] = useState([]);
//   const [aiTextStyleSuggestions, setAiTextStyleSuggestions] = useState(null);
//   const [initialAiTextComponents, setInitialAiTextComponents] = useState(null);

//   const [selectedComponentId, setSelectedComponentId] = useState(null);

//   const flyerContainerRef = useRef(null);

//   const headlineRef = useRef(null);
//   const descriptionRef = useRef(null);
//   const eventInfoRef = useRef(null);
//   const footerRef = useRef(null);

//   const componentRefsMap = {
//       headline: headlineRef,
//       description: descriptionRef,
//       event_info: eventInfoRef,
//       footer: footerRef
//   };

//   const initializeTextComponents = useCallback((aiSuggestions, currentContentInput) => {
//     const eventDetails = [
//       currentContentInput.event_date ? new Date(currentContentInput.event_date).toLocaleDateString('fr-FR') : '',
//       currentContentInput.event_time,
//       currentContentInput.event_location
//     ].filter(Boolean).join(' - ');

//     const footerDetails = [
//       currentContentInput.footer_email,
//       currentContentInput.footer_website,
//       currentContentInput.footer_phone
//     ].filter(Boolean).join(' | ');

//     const rawComponents = [
//       { id: 'headline', type: 'headline', content: currentContentInput.headline1 },
//       { id: 'description', type: 'body', content: currentContentInput.short_description },
//       { id: 'event_info', type: 'event_info', content: eventDetails },
//       { id: 'footer', type: 'footer', content: footerDetails },
//     ];

//     const previewWidth = 360;
//     const previewHeight = 640;

//     const styledComponents = rawComponents.map(comp => {
//       const style = aiSuggestions[comp.type] || {};

//       const initialTopPercentage = style.initialTopPercentage !== undefined ? style.initialTopPercentage : (
//         comp.type === 'headline' ? 10 :
//         comp.type === 'description' ? 30 :
//         comp.type === 'event_info' ? 65 :
//         88
//       );
//       const initialWidthPercentage = style.initialWidthPercentage !== undefined ? style.initialWidthPercentage : (
//         comp.type === 'description' ? 80 : 90
//       );

//       const initialY = (initialTopPercentage / 100) * previewHeight;

//       const actualWidthInPixels = (initialWidthPercentage / 100) * previewWidth;
//       let initialX = 0;
//       const horizontalMargin = 15;
//       if (style.textAlign === 'center') {
//         initialX = (previewWidth - actualWidthInPixels) / 2;
//       } else if (style.textAlign === 'right') {
//         initialX = previewWidth - actualWidthInPixels - horizontalMargin;
//       } else {
//         initialX = horizontalMargin;
//       }

//       const textColor = style.color || '#FFFFFF';
//       const isLightColor = parseInt(textColor.replace('#', ''), 16) > 0xFFFFFF / 2;
//       const shadowColor = isLightColor ? 'rgba(0, 0, 0, 0.8)' : 'rgba(255, 255, 255, 0.8)';
//       const textShadowStyle = `1px 1px 2px ${shadowColor}, -1px -1px 2px ${shadowColor}`;

//       return {
//         ...comp,
//         x: initialX,
//         y: initialY,
//         width: `${initialWidthPercentage}%`,
//         minHeightPx: 0,
//         style: {
//           fontFamily: style.fontFamily || 'Arial, sans-serif',
//           color: textColor,
//           fontSize: `${style.fontSizePx || 24}px`,
//           fontWeight: style.fontWeight || 'normal',
//           textAlign: style.textAlign || 'center',
//           lineHeight: `${style.lineHeightEm || 1.4}em`,
//           textShadow: textShadowStyle,
//         }
//       };
//     });
//     return styledComponents;
//   }, []);

//   useEffect(() => {
//     if (aiTextStyleSuggestions && flyerBackgroundUrl) {
//       const newComponents = initializeTextComponents(aiTextStyleSuggestions, contentInput);
//       setTextComponents(newComponents);
//       setInitialAiTextComponents(newComponents);
//     }
//   }, [aiTextStyleSuggestions, flyerBackgroundUrl, contentInput, initializeTextComponents]);

//   const processFile = (file) => {
//     if (file) {
//       if (file.type.startsWith('image/')) {
//         setImageFile(file);
//         setImagePreview(URL.createObjectURL(file));
//         setError(null);
//         setFlyerBackgroundUrl(null);
//         setTextComponents([]);
//         setAiTextStyleSuggestions(null);
//         setInitialAiTextComponents(null);
//         setSelectedComponentId(null);
//       } else {
//         setError("Veuillez importer un fichier image valide (JPG, PNG, GIF, etc.).");
//         setImageFile(null);
//         setImagePreview(null);
//       }
//     }
//   };

//   const handleImageChange = (e) => {
//     processFile(e.target.files[0]);
//   };

//   const handleDragOver = (e) => {
//     e.preventDefault();
//     setIsDraggingOver(true);
//   };

//   const handleDragLeave = () => {
//     setIsDraggingOver(false);
//   };

//   const handleDrop = (e) => {
//     e.preventDefault();
//     setIsDraggingOver(false);
//     if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
//       processFile(e.dataTransfer.files[0]);
//     }
//   };

//   const handleContentInputChange = (e) => {
//     const { name, value } = e.target;
//     setContentInput(prev => ({ ...prev, [name]: value }));

//     setTextComponents(prevComponents =>
//       prevComponents.map(comp => {
//         let newContent = comp.content;
//         const updatedContentInput = { ...contentInput, [name]: value }; 

//         if (comp.id === 'headline' && name === 'headline1') {
//           newContent = value;
//         } else if (comp.id === 'description' && name === 'short_description') {
//           newContent = value;
//         } else if (comp.id === 'event_info' && ['event_date', 'event_time', 'event_location'].includes(name)) {
//           newContent = [
//             updatedContentInput.event_date ? new Date(updatedContentInput.event_date).toLocaleDateString('fr-FR') : '',
//             updatedContentInput.event_time,
//             updatedContentInput.event_location
//           ].filter(Boolean).join(' - ');
//         } else if (comp.id === 'footer' && ['footer_email', 'footer_website', 'footer_phone'].includes(name)) {
//           newContent = [
//             updatedContentInput.footer_email,
//             updatedContentInput.footer_website,
//             updatedContentInput.footer_phone
//           ].filter(Boolean).join(' | ');
//         }
//         return { ...comp, content: newContent };
//       })
//     );
//   };

//   const handleComponentClick = (id) => {
//     setSelectedComponentId(id);
//   };

//   const handleStyleChange = (styleProp, value) => {
//     setTextComponents(prevComponents =>
//       prevComponents.map(comp => {
//         if (comp.id === selectedComponentId) {
//           const newStyle = { ...comp.style };
//           let newWidth = comp.width;
//           let newMinHeightPx = comp.minHeightPx;

//           if (styleProp === 'fontSize') {
//             newStyle.fontSize = `${value}px`;
//           } else if (styleProp === 'color') {
//             newStyle.color = value;
//             const isLightColor = parseInt(value.replace('#', ''), 16) > 0xFFFFFF / 2;
//             const shadowColor = isLightColor ? 'rgba(0, 0, 0, 0.8)' : 'rgba(255, 255, 255, 0.8)';
//             newStyle.textShadow = `1px 1px 2px ${shadowColor}, -1px -1px 2px ${shadowColor}`;
//           } else if (styleProp === 'width') {
//             newWidth = `${value}%`;
//           } else if (styleProp === 'minHeightPx') {
//             newMinHeightPx = value;
//           } else if (styleProp === 'fontFamily') {
//             newStyle.fontFamily = value;
//           } else if (styleProp === 'textAlign') {
//             newStyle.textAlign = value;
//             const previewWidth = 360;
//             const initialWidthPercentage = parseInt(newWidth);
//             const actualWidthInPixels = (initialWidthPercentage / 100) * previewWidth;
//             let newX = comp.x;
//             const horizontalMargin = 15;
//             if (value === 'center') {
//               newX = (previewWidth - actualWidthInPixels) / 2;
//             } else if (value === 'right') {
//               newX = previewWidth - actualWidthInPixels - horizontalMargin;
//             } else { // left
//               newX = horizontalMargin;
//             }
//             return { ...comp, x: newX, style: newStyle, width: newWidth, minHeightPx: newMinHeightPx };
//           }
//           return { ...comp, style: newStyle, width: newWidth, minHeightPx: newMinHeightPx };
//         }
//         return comp;
//       })
//     );
//   };

//   const handleComponentTextChange = (id, newText) => {
//     setTextComponents(prevComponents =>
//       prevComponents.map(comp => (comp.id === id ? { ...comp, content: newText } : comp))
//     );
//   };

//   const handleStopDrag = (e, data, id) => {
//     setTextComponents(prevComponents =>
//       prevComponents.map(comp =>
//         comp.id === id ? { ...comp, x: data.x, y: data.y } : comp
//       )
//     );
//   };

//   const handleSubmit = async (e) => {
//     e.preventDefault();

//     if (!imageFile) {
//         setError("Veuillez choisir une image de style pour commencer.");
//         return;
//     }

//     setIsLoading(true);
//     setError(null);
//     setFlyerBackgroundUrl(null);
//     setTextComponents([]);
//     setAiTextStyleSuggestions(null);
//     setInitialAiTextComponents(null);
//     setSelectedComponentId(null);

//     const formData = new FormData();
//     formData.append('image', imageFile);
//     formData.append('headline1', contentInput.headline1);
//     formData.append('short_description', contentInput.short_description);
//     const eventDetails = [
//         contentInput.event_date ? new Date(contentInput.event_date).toLocaleDateString('fr-FR') : '',
//         contentInput.event_time,
//         contentInput.event_location
//     ].filter(Boolean).join(' - ');
//     formData.append('event_info', eventDetails);

//     const footerDetails = [
//         contentInput.footer_email,
//         contentInput.footer_website,
//         contentInput.footer_phone
//     ].filter(Boolean).join(' | ');
//     formData.append('footer_info', footerDetails);

//     try {
//       const baseUrl = process.env.NODE_ENV === 'development'
//         ? 'http://localhost:5000'
//         : window.location.origin;

//       const response = await fetch(`${baseUrl}/api/generate-flyer-from-prototype`, {
//         method: 'POST',
//         body: formData
//       });
//       const data = await response.json();
//       if (!response.ok) throw new Error(data.error || 'Une erreur est survenue.');

//       setFlyerBackgroundUrl(data.flyer_background_url);
//       setAiTextStyleSuggestions(data.text_style_suggestions);

//     } catch (err) {
//       setError(err.message);
//     } finally {
//       setIsLoading(false);
//     }
//   };

//   // FONCTION CORRIGÉE POUR LE TÉLÉCHARGEMENT
//   const handleDownloadFlyer = async () => {
//     if (!flyerContainerRef.current || !flyerBackgroundUrl) {
//         setError("Impossible de trouver l'élément à capturer ou l'image de fond.");
//         return;
//     }

//     setIsLoading(true);
//     setError(null);

//     try {
//         // Méthode 1: Essayer html2canvas avec configuration optimisée
//         console.log("Tentative de téléchargement avec html2canvas...");
//         const canvas = await html2canvas(flyerContainerRef.current, {
//             useCORS: true,
//             allowTaint: true,
//             scale: 3,
//             backgroundColor: null,
//             logging: false,
//             imageTimeout: 30000,
//             removeContainer: true,
//             foreignObjectRendering: true,
//             scrollX: 0,
//             scrollY: 0,
//             width: flyerContainerRef.current.scrollWidth,
//             height: flyerContainerRef.current.scrollHeight,
//             onclone: (clonedDoc) => {
//                 return new Promise((resolve) => {
//                     if (document.fonts && document.fonts.ready) {
//                         document.fonts.ready.then(() => {
//                             console.log("Polices prêtes pour html2canvas.");
//                             setTimeout(resolve, 500);
//                         }).catch(() => {
//                             console.warn("Échec de l'attente des polices, continuation...");
//                             setTimeout(resolve, 1000);
//                         });
//                     } else {
//                         setTimeout(resolve, 1500);
//                     }
//                 });
//             }
//         });

//         if (canvas.width === 0 || canvas.height === 0 || canvas.getContext('2d').getImageData(0, 0, 1, 1).data[3] === 0) {
//             throw new Error("html2canvas a généré un canvas vide ou transparent. Tentative de fallback.");
//         }

//         const image = canvas.toDataURL('image/png', 1.0);
//         const link = document.createElement('a');
//         link.href = image;
//         link.download = `flyer_client_side_${contentInput.headline1.replace(/\s+/g, '_')}_${new Date().getTime()}.png`;
//         document.body.appendChild(link);
//         link.click();
//         document.body.removeChild(link);
        
//         alert("Votre flyer a été téléchargé avec succès (client-side) !");
        
//     } catch (error) {
//         console.error("Erreur html2canvas:", error);
//         setError(`Erreur lors de la capture côté client: ${error.message}. Tentative de génération côté serveur...`);
        
//         // Méthode de fallback: Générer côté serveur
//         try {
//             await handleDownloadFlyerServerSide();
//             alert("Votre flyer a été téléchargé avec succès (server-side) !");
//         } catch (serverError) {
//             console.error("Erreur serveur:", serverError);
//             setError(`Échec de la génération côté serveur: ${serverError.message}. Tentative de télécharger l'image de fond seule...`);
            
//             // Dernier recours: télécharger l'image de fond
//             try {
//                 const response = await fetch(flyerBackgroundUrl);
//                 const blob = await response.blob();
//                 const url = window.URL.createObjectURL(blob);
//                 const link = document.createElement('a');
//                 link.href = url;
//                 link.download = `flyer_background_${new Date().getTime()}.png`;
//                 document.body.appendChild(link);
//                 link.click();
//                 document.body.removeChild(link);
//                 window.URL.revokeObjectURL(url);
                
//                 alert("Impossible de générer le flyer complet. L'image de fond a été téléchargée. Vous devrez ajouter le texte manuellement.");
//             } catch (fallbackError) {
//                 console.error("Erreur de téléchargement du fond:", fallbackError);
//                 setError("Impossible de télécharger le flyer du tout. Veuillez vérifier votre connexion ou réessayer plus tard.");
//             }
//         }
//     } finally {
//         setIsLoading(false);
//     }
//   };

//   // NOUVELLE FONCTION: Téléchargement côté serveur
//   const handleDownloadFlyerServerSide = async () => {
//     const baseUrl = process.env.NODE_ENV === 'development'
//         ? 'http://localhost:5000'
//         : window.location.origin;

//     const textData = textComponents.map(comp => {
//       const currentRef = componentRefsMap[comp.id]?.current;
//       let currentX = comp.x;
//       let currentY = comp.y;

//       if (currentRef) {
//         const transform = window.getComputedStyle(currentRef).transform;
//         if (transform && transform !== 'none') {
//           const matrix = transform.match(/matrix.*\((.+)\)/);
//           if (matrix && matrix[1]) { // Assurez-vous que la regex a bien capturé
//              const matrixValues = matrix[1].split(', ').map(Number);
//              currentX = matrixValues[4]; // dx
//              currentY = matrixValues[5]; // dy
//           }
//         }
//       }

//       return {
//           id: comp.id,
//           content: comp.content,
//           x: Math.round(currentX),
//           y: Math.round(currentY),
//           width: comp.width,
//           style: {
//               fontFamily: comp.style.fontFamily,
//               color: comp.style.color,
//               fontSizePx: parseInt(comp.style.fontSize) || 24,
//               fontWeight: comp.style.fontWeight,
//               textAlign: comp.style.textAlign,
//               lineHeightEm: parseFloat(comp.style.lineHeight) || 1.4,
//               textShadow: comp.style.textShadow, // Passons l'info de l'ombre au backend, il décidera comment l'appliquer
//           },
//           minHeightPx: comp.minHeightPx || 0
//       };
//     });

//     console.log("Envoi des données au serveur pour génération:", textData);

//     const response = await fetch(`${baseUrl}/api/generate-final-flyer`, {
//         method: 'POST',
//         headers: {
//             'Content-Type': 'application/json',
//         },
//         body: JSON.stringify({
//             background_url: flyerBackgroundUrl,
//             text_components: textData,
//             flyer_dimensions: {
//                 width: 360,
//                 height: 640
//             }
//         })
//     });

//     if (!response.ok) {
//         const errorData = await response.json();
//         throw new Error(`Erreur serveur: ${errorData.error || 'Impossible de générer le flyer final'}`);
//     }

//     const blob = await response.blob();
//     const url = window.URL.createObjectURL(blob);
//     const link = document.createElement('a');
//     link.href = url;
//     link.download = `flyer_server_side_${contentInput.headline1.replace(/\s+/g, '_')}_${new Date().getTime()}.png`;
//     document.body.appendChild(link);
//     link.click();
//     document.body.removeChild(link);
//     window.URL.revokeObjectURL(url);
    
//   };

//   const handleResetStyles = () => {
//     if (initialAiTextComponents) {
//         const resetComponents = initialAiTextComponents.map(comp => ({
//             ...comp,
//             style: { ...comp.style }
//         }));
//         setTextComponents(resetComponents);
//         setSelectedComponentId(null);
//         alert("Les styles ont été réinitialisés aux suggestions de l'IA.");
//     } else {
//         alert("Aucune suggestion initiale de l'IA à réinitialiser.");
//     }
//   };

//   const selectedComponent = textComponents.find(comp => comp.id === selectedComponentId);

//   return (
//     <div className="App">
//       <header className="App-header">
//         <h1>Générateur de Flyer par IA</h1>
//         <p>Importez votre design de base, ajoutez votre texte, laissez l'IA créer une image de fond personnalisée et suggérer les styles, puis placez et modifiez votre texte librement.</p>
//       </header>

//       <main>
//         <form onSubmit={handleSubmit} className="form-container">
//           {/* --- SECTION 1 : IMAGE DE BASE --- */}
//           <fieldset>
//             <legend>1. Image de Base pour le Style</legend>
//             <p className="field-description">Fournissez l'image de fond pour que l'IA en extraie le style. Elle générera une nouvelle image similaire SANS texte et suggérera des styles pour votre texte.</p>

//             <div
//               className={`drop-zone ${isDraggingOver ? 'drag-over' : ''}`}
//               onDragOver={handleDragOver}
//               onDragLeave={handleDragLeave}
//               onDrop={handleDrop}
//             >
//               <p>Glissez-déposez votre image ici, ou</p>
//               <label htmlFor="image-upload-input" className="custom-file-upload">
//                 {imageFile ? "Changer l'image" : "Choisir une image de style"}
//               </label>
//               <input
//                 id="image-upload-input"
//                 type="file"
//                 accept="image/*"
//                 onChange={handleImageChange}
//               />
//             </div>

//             {imagePreview && <div className="image-preview-container"><img src={imagePreview} alt="Aperçu de l'image de style" className="image-preview" /></div>}
//             {error && !imageFile && <p className="error-message">{error}</p>}
//           </fieldset>

//           {/* --- SECTION 2 : CONTENU DU FLYER (Texte) --- */}
//           <fieldset>
//             <legend>2. Contenu Texte du Flyer</legend>

//             <label htmlFor="headline1">Titre Principal</label>
//             <input type="text" id="headline1" name="headline1" value={contentInput.headline1} onChange={handleContentInputChange} placeholder="Ex: Soirée de Lancement"/>

//             <label htmlFor="short_description">Description Principale</label>
//             <p className="field-description">Le texte principal qui décrit votre événement ou message.</p>
//             <textarea
//               id="short_description"
//               name="short_description"
//               value={contentInput.short_description}
//               onChange={handleContentInputChange}
//               rows={4}
//               placeholder="Décrivez votre événement ici..."
//             />

//             <div className="event-grid">
//               <div>
//                 <label htmlFor="event_date">Date</label>
//                 <input type="date" id="event_date" name="event_date" value={contentInput.event_date} onChange={handleContentInputChange}/>
//               </div>
//               <div>
//                 <label htmlFor="event_time">Heure</label>
//                 <input type="time" id="event_time" name="event_time" value={contentInput.event_time} onChange={handleContentInputChange}/>
//               </div>
//               <div className="full-width">
//                 <label htmlFor="event_location">Lieu</label>
//                 <input type="text" id="event_location" name="event_location" value={contentInput.event_location} onChange={handleContentInputChange} placeholder="Ex: Le Grand Palais, Paris"/>
//               </div>
//             </div>
//           </fieldset>

//           {/* --- SECTION 3 : CONTACT --- */}
//           <fieldset>
//             <legend>3. Informations de Contact (Pied de page)</legend>
//             <div className="contact-grid">
//               <div>
//                 <label htmlFor="footer_email">Email</label>
//                 <input type="email" id="footer_email" name="footer_email" value={contentInput.footer_email} onChange={handleContentInputChange}/>
//               </div>
//               <div>
//                 <label htmlFor="footer_website">Site Web</label>
//                 <input type="text" id="footer_website" name="footer_website" value={contentInput.footer_website} onChange={handleContentInputChange}/>
//               </div>
//               <div>
//                 <label htmlFor="footer_phone">Téléphone</label>
//                 <input type="text" id="footer_phone" name="footer_phone" value={contentInput.footer_phone} onChange={handleContentInputChange}/>
//               </div>
//             </div>
//           </fieldset>

//           <button type="submit" disabled={isLoading || !imageFile} className="generate-btn">
//              {isLoading ? `Génération du fond et des styles...` : `Générer l'image de fond et les styles de texte`}
//           </button>
//         </form>

//         {/* --- SECTION RÉSULTATS --- */}
//         <div className="result-container">
//           {isLoading && <div className="loading-container"><div className="loader"></div><p>Génération de l'image de fond et analyse des styles...</p></div>}
//           {error && <p className="error-message">{error}</p>}

//           {flyerBackgroundUrl && (
//             <div className="flyer-editor-section">
//               <h2>Votre Design est Prêt ! 🚀</h2>
//               <p>Cliquez sur un bloc de texte pour le modifier et le positionner. Utilisez les contrôles ci-dessous pour ajuster les styles.</p>

//               {/* Toolbar de modification de style */}
//               {selectedComponent && (
//                 <div className="style-toolbar">
//                   <h3>Modifier {selectedComponent.id.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</h3>
//                   <div className="control-group">
//                     <label htmlFor="font-family-select">Police de Caractères:</label>
//                     <select
//                       id="font-family-select"
//                       value={selectedComponent.style.fontFamily || 'Arial, sans-serif'}
//                       onChange={(e) => handleStyleChange('fontFamily', e.target.value)}
//                       style={{ fontFamily: selectedComponent.style.fontFamily }}
//                     >
//                       {FONT_OPTIONS.map(font => (
//                         <option key={font} value={font} style={{ fontFamily: font }}>
//                           {font.split(',')[0]}
//                         </option>
//                       ))}
//                     </select>
//                   </div>

//                   <div className="control-group">
//                     <label htmlFor="font-size-slider">Taille du Texte (px):</label>
//                     <input
//                       type="range"
//                       id="font-size-slider"
//                       min="10"
//                       max="100"
//                       value={parseInt(selectedComponent.style.fontSize) || 24}
//                       onChange={(e) => handleStyleChange('fontSize', e.target.value)}
//                     />
//                     <span>{parseInt(selectedComponent.style.fontSize) || 24}px</span>
//                   </div>

//                   <div className="control-group">
//                     <label htmlFor="text-color-picker">Couleur du Texte:</label>
//                     <input
//                       type="color"
//                       id="text-color-picker"
//                       value={selectedComponent.style.color || '#FFFFFF'}
//                       onChange={(e) => handleStyleChange('color', e.target.value)}
//                     />
//                   </div>

//                   <div className="control-group">
//                     <label htmlFor="text-align-select">Alignement:</label>
//                     <select
//                       id="text-align-select"
//                       value={selectedComponent.style.textAlign || 'center'}
//                       onChange={(e) => handleStyleChange('textAlign', e.target.value)}
//                     >
//                       <option value="left">Gauche</option>
//                       <option value="center">Centre</option>
//                       <option value="right">Droite</option>
//                     </select>
//                   </div>

//                   <div className="control-group">
//                     <label htmlFor="width-slider">Largeur du Conteneur (%):</label>
//                     <input
//                       type="range"
//                       id="width-slider"
//                       min="50"
//                       max="100"
//                       value={parseInt(selectedComponent.width) || 90}
//                       onChange={(e) => handleStyleChange('width', e.target.value)}
//                     />
//                     <span>{parseInt(selectedComponent.width) || 90}%</span>
//                   </div>

//                   <div className="control-group">
//                     <label htmlFor="min-height-slider">Hauteur Min. Conteneur (px):</label>
//                     <input
//                       type="range"
//                       id="min-height-slider"
//                       min="0"
//                       max="200"
//                       step="5"
//                       value={selectedComponent.minHeightPx || 0}
//                       onChange={(e) => handleStyleChange('minHeightPx', parseInt(e.target.value))}
//                     />
//                     <span>{selectedComponent.minHeightPx || 0}px</span>
//                   </div>
                  
//                   <button type="button" onClick={handleResetStyles} disabled={!initialAiTextComponents} className="reset-btn">
//                       Réinitialiser les styles (Suggestions IA)
//                   </button>
//                 </div>
//               )}

//               <div className="generated-flyer-preview-wrapper" onClick={() => setSelectedComponentId(null)}>
//                 <div 
//                   className="generated-flyer-preview" 
//                   ref={flyerContainerRef}
//                   style={{
//                     position: 'relative',
//                     width: '360px',
//                     height: '640px',
//                     margin: '0 auto',
//                     overflow: 'hidden',
//                     transform: 'translateZ(0)',
//                     backfaceVisibility: 'hidden',
//                     perspective: '1000px'
//                   }}
//                 >
//                   <img 
//                     src={flyerBackgroundUrl} 
//                     alt="Flyer Background" 
//                     className="generated-background-image"
//                     style={{
//                       position: 'absolute',
//                       top: '0',
//                       left: '0',
//                       width: '100%',
//                       height: '100%',
//                       objectFit: 'cover',
//                       zIndex: '1',
//                       imageRendering: 'high-quality'
//                     }}
//                   />

//                   {textComponents.map(comp => {
//                     const nodeRef = componentRefsMap[comp.id];

//                     const estimatedCharsPerLine = ((parseInt(comp.width) / 100) * 360) / ((parseInt(comp.style.fontSize) || 24) * 0.55);
//                     const estimatedRows = Math.max(1, Math.ceil(comp.content.length / estimatedCharsPerLine));
                    
//                     return (
//                       <Draggable
//                         key={comp.id}
//                         nodeRef={nodeRef}
//                         bounds="parent"
//                         position={{ x: comp.x, y: comp.y }}
//                         onStop={(e, data) => handleStopDrag(e, data, comp.id)}
//                       >
//                         <div
//                           ref={nodeRef}
//                           className={`text-draggable-component text-type-${comp.type} ${selectedComponentId === comp.id ? 'selected' : ''}`}
//                           style={{
//                             ...comp.style,
//                             width: comp.width,
//                             minHeight: comp.minHeightPx ? `${comp.minHeightPx}px` : 'auto',
//                             position: 'absolute',
//                             zIndex: '2',
//                             cursor: 'move'
//                           }}
//                           onClick={(e) => {
//                               e.stopPropagation();
//                               handleComponentClick(comp.id);
//                           }}
//                         >
//                           <textarea
//                             value={comp.content}
//                             onChange={(e) => handleComponentTextChange(comp.id, e.target.value)}
//                             style={{
//                               fontFamily: comp.style.fontFamily,
//                               fontSize: comp.style.fontSize,
//                               fontWeight: comp.style.fontWeight,
//                               textAlign: comp.style.textAlign,
//                               color: comp.style.color,
//                               lineHeight: comp.style.lineHeight,
//                               textShadow: comp.style.textShadow,

//                               width: '100%',
//                               height: 'auto',
//                               resize: 'none',
//                               border: 'none',
//                               background: 'transparent',
//                               padding: 0,
//                               margin: 0,
//                               overflowY: 'hidden',
//                               outline: 'none',
//                             }}
//                             rows={estimatedRows}
//                           />
//                         </div>
//                       </Draggable>
//                     );
//                   })}
//                 </div>
//               </div>
//               <button onClick={handleDownloadFlyer} disabled={isLoading} className="download-btn">
//                 {isLoading ? "Préparation au téléchargement..." : "📥 Télécharger le Flyer Complet (Image + Texte)"}
//               </button>
//             </div>
//           )}
//         </div>
//       </main>
//     </div>
//   );
// }




















// "use client";

// import { useState, useRef, useEffect, useCallback } from 'react';
// import Image from 'next/image';
// import html2canvas from 'html2canvas';
// import Draggable from 'react-draggable';
// import './globals.css';

// // Liste des polices disponibles pour la sélection manuelle
// const FONT_OPTIONS = [
//   'Arial, sans-serif',
//   'Verdana, sans-serif',
//   'Helvetica, sans-serif',
//   'Georgia, serif',
//   'Times New Roman, serif',
//   'Courier New, monospace',
//   'Impact, sans-serif',
//   'Trebuchet MS, sans-serif',
//   'Open Sans, sans-serif',
//   'Roboto, sans-serif',
//   'Playfair Display, serif',
// ];

// export default function HomePage() {
//   const [imageFile, setImageFile] = useState(null);
//   const [imagePreview, setImagePreview] = useState(null);
//   const [isDraggingOver, setIsDraggingOver] = useState(false);

//   const [contentInput, setContentInput] = useState({
//     headline1: 'Gala Annuel 2024',
//     short_description: 'Join us for an unforgettable evening of celebration and networking — a unique opportunity to connect with industry leaders in an exceptional setting.',
//     event_date: '2024-12-05',
//     event_time: '19:00',
//     event_location: 'Le Grand Palais, Paris',
//     footer_email: 'rsvp@votre-gala.com',
//     footer_website: 'www.votre-gala.com',
//     footer_phone: '+33 1 98 76 54 32'
//   });

//   const [isLoading, setIsLoading] = useState(false);
//   const [error, setError] = useState(null);
//   const [flyerBackgroundUrl, setFlyerBackgroundUrl] = useState(null);

//   const [textComponents, setTextComponents] = useState([]);
//   const [aiTextStyleSuggestions, setAiTextStyleSuggestions] = useState(null);

//   const [initialAiTextComponents, setInitialAiTextComponents] = useState(null);

//   const [selectedComponentId, setSelectedComponentId] = useState(null);

//   const flyerContainerRef = useRef(null);

//   const headlineRef = useRef(null);
//   const descriptionRef = useRef(null);
//   const eventInfoRef = useRef(null);
//   const footerRef = useRef(null);

//   const componentRefsMap = {
//       headline: headlineRef,
//       description: descriptionRef,
//       event_info: eventInfoRef,
//       footer: footerRef
//   };

//   const initializeTextComponents = useCallback((aiSuggestions, currentContentInput) => {
//     const eventDetails = [
//       currentContentInput.event_date ? new Date(currentContentInput.event_date).toLocaleDateString('fr-FR') : '',
//       currentContentInput.event_time,
//       currentContentInput.event_location
//     ].filter(Boolean).join(' - ');

//     const footerDetails = [
//       currentContentInput.footer_email,
//       currentContentInput.footer_website,
//       currentContentInput.footer_phone
//     ].filter(Boolean).join(' | ');

//     const rawComponents = [
//       { id: 'headline', type: 'headline', content: currentContentInput.headline1 },
//       { id: 'description', type: 'body', content: currentContentInput.short_description },
//       { id: 'event_info', type: 'event_info', content: eventDetails },
//       { id: 'footer', type: 'footer', content: footerDetails },
//     ];

//     const previewWidth = 360;
//     const previewHeight = 640;

//     const styledComponents = rawComponents.map(comp => {
//       const style = aiSuggestions[comp.type] || {};

//       const initialTopPercentage = style.initialTopPercentage !== undefined ? style.initialTopPercentage : (
//         comp.type === 'headline' ? 10 :
//         comp.type === 'description' ? 30 :
//         comp.type === 'event_info' ? 65 :
//         88
//       );
//       const initialWidthPercentage = style.initialWidthPercentage !== undefined ? style.initialWidthPercentage : (
//         comp.type === 'description' ? 80 : 90
//       );

//       const initialY = (initialTopPercentage / 100) * previewHeight;

//       const actualWidthInPixels = (initialWidthPercentage / 100) * previewWidth;
//       let initialX = 0;
//       const horizontalMargin = 15;
//       if (style.textAlign === 'center') {
//         initialX = (previewWidth - actualWidthInPixels) / 2;
//       } else if (style.textAlign === 'right') {
//         initialX = previewWidth - actualWidthInPixels - horizontalMargin;
//       } else {
//         initialX = horizontalMargin;
//       }

//       const textColor = style.color || '#FFFFFF';
//       const isLightColor = parseInt(textColor.replace('#', ''), 16) > 0xFFFFFF / 2;
//       const shadowColor = isLightColor ? 'rgba(0, 0, 0, 0.8)' : 'rgba(255, 255, 255, 0.8)';
//       const textShadowStyle = `1px 1px 2px ${shadowColor}, -1px -1px 2px ${shadowColor}`;

//       return {
//         ...comp,
//         x: initialX,
//         y: initialY,
//         width: `${initialWidthPercentage}%`,
//         minHeightPx: 0,
//         style: {
//           fontFamily: style.fontFamily || 'Arial, sans-serif',
//           color: textColor,
//           fontSize: `${style.fontSizePx || 24}px`,
//           fontWeight: style.fontWeight || 'normal',
//           textAlign: style.textAlign || 'center',
//           lineHeight: `${style.lineHeightEm || 1.4}em`,
//           textShadow: textShadowStyle,
//         }
//       };
//     });
//     return styledComponents;
//   }, []);

//   useEffect(() => {
//     if (aiTextStyleSuggestions && flyerBackgroundUrl) {
//       const newComponents = initializeTextComponents(aiTextStyleSuggestions, contentInput);
//       setTextComponents(newComponents);
//       setInitialAiTextComponents(newComponents);
//     }
//   }, [aiTextStyleSuggestions, flyerBackgroundUrl, contentInput, initializeTextComponents]);

//   const processFile = (file) => {
//     if (file) {
//       if (file.type.startsWith('image/')) {
//         setImageFile(file);
//         setImagePreview(URL.createObjectURL(file));
//         setError(null);
//         setFlyerBackgroundUrl(null);
//         setTextComponents([]);
//         setAiTextStyleSuggestions(null);
//         setInitialAiTextComponents(null);
//         setSelectedComponentId(null);
//       } else {
//         setError("Veuillez importer un fichier image valide (JPG, PNG, GIF, etc.).");
//         setImageFile(null);
//         setImagePreview(null);
//       }
//     }
//   };

//   const handleImageChange = (e) => {
//     processFile(e.target.files[0]);
//   };

//   const handleDragOver = (e) => {
//     e.preventDefault();
//     setIsDraggingOver(true);
//   };

//   const handleDragLeave = () => {
//     setIsDraggingOver(false);
//   };

//   const handleDrop = (e) => {
//     e.preventDefault();
//     setIsDraggingOver(false);
//     if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
//       processFile(e.dataTransfer.files[0]);
//     }
//   };

//   const handleContentInputChange = (e) => {
//     const { name, value } = e.target;
//     setContentInput(prev => ({ ...prev, [name]: value }));

//     setTextComponents(prevComponents =>
//       prevComponents.map(comp => {
//         let newContent = comp.content;
//         const updatedContentInput = { ...contentInput, [name]: value }; 

//         if (comp.id === 'headline' && name === 'headline1') {
//           newContent = value;
//         } else if (comp.id === 'description' && name === 'short_description') {
//           newContent = value;
//         } else if (comp.id === 'event_info' && ['event_date', 'event_time', 'event_location'].includes(name)) {
//           newContent = [
//             updatedContentInput.event_date ? new Date(updatedContentInput.event_date).toLocaleDateString('fr-FR') : '',
//             updatedContentInput.event_time,
//             updatedContentInput.event_location
//           ].filter(Boolean).join(' - ');
//         } else if (comp.id === 'footer' && ['footer_email', 'footer_website', 'footer_phone'].includes(name)) {
//           newContent = [
//             updatedContentInput.footer_email,
//             updatedContentInput.footer_website,
//             updatedContentInput.footer_phone
//           ].filter(Boolean).join(' | ');
//         }
//         return { ...comp, content: newContent };
//       })
//     );
//   };

//   const handleComponentClick = (id) => {
//     setSelectedComponentId(id);
//   };

//   const handleStyleChange = (styleProp, value) => {
//     setTextComponents(prevComponents =>
//       prevComponents.map(comp => {
//         if (comp.id === selectedComponentId) {
//           const newStyle = { ...comp.style };
//           let newWidth = comp.width;
//           let newMinHeightPx = comp.minHeightPx;

//           if (styleProp === 'fontSize') {
//             newStyle.fontSize = `${value}px`;
//           } else if (styleProp === 'color') {
//             newStyle.color = value;
//             const isLightColor = parseInt(value.replace('#', ''), 16) > 0xFFFFFF / 2;
//             const shadowColor = isLightColor ? 'rgba(0, 0, 0, 0.8)' : 'rgba(255, 255, 255, 0.8)';
//             newStyle.textShadow = `1px 1px 2px ${shadowColor}, -1px -1px 2px ${shadowColor}`;
//           } else if (styleProp === 'width') {
//             newWidth = `${value}%`;
//           } else if (styleProp === 'minHeightPx') {
//             newMinHeightPx = value;
//           } else if (styleProp === 'fontFamily') {
//             newStyle.fontFamily = value;
//           }
//           return { ...comp, style: newStyle, width: newWidth, minHeightPx: newMinHeightPx };
//         }
//         return comp;
//       })
//     );
//   };

//   const handleComponentTextChange = (id, newText) => {
//     setTextComponents(prevComponents =>
//       prevComponents.map(comp => (comp.id === id ? { ...comp, content: newText } : comp))
//     );
//   };

//   const handleStopDrag = (e, data, id) => {
//     setTextComponents(prevComponents =>
//       prevComponents.map(comp =>
//         comp.id === id ? { ...comp, x: data.x, y: data.y } : comp
//       )
//     );
//   };

//   const handleSubmit = async (e) => {
//     e.preventDefault();

//     if (!imageFile) {
//         setError("Veuillez choisir une image de style pour commencer.");
//         return;
//     }

//     setIsLoading(true);
//     setError(null);
//     setFlyerBackgroundUrl(null);
//     setTextComponents([]);
//     setAiTextStyleSuggestions(null);
//     setInitialAiTextComponents(null);
//     setSelectedComponentId(null);

//     const formData = new FormData();
//     formData.append('image', imageFile);
//     formData.append('headline1', contentInput.headline1);
//     formData.append('short_description', contentInput.short_description);
//     const eventDetails = [
//         contentInput.event_date ? new Date(contentInput.event_date).toLocaleDateString('fr-FR') : '',
//         contentInput.event_time,
//         contentInput.event_location
//     ].filter(Boolean).join(' - ');
//     formData.append('event_info', eventDetails);

//     const footerDetails = [
//         contentInput.footer_email,
//         contentInput.footer_website,
//         contentInput.footer_phone
//     ].filter(Boolean).join(' | ');
//     formData.append('footer_info', footerDetails);

//     try {
//       const baseUrl = process.env.NODE_ENV === 'development'
//         ? 'http://localhost:5000'
//         : window.location.origin;

//       const response = await fetch(`${baseUrl}/api/generate-flyer-from-prototype`, {
//         method: 'POST',
//         body: formData
//       });
//       const data = await response.json();
//       if (!response.ok) throw new Error(data.error || 'Une erreur est survenue.');

//       setFlyerBackgroundUrl(data.flyer_background_url);
//       setAiTextStyleSuggestions(data.text_style_suggestions);

//     } catch (err) {
//       setError(err.message);
//     } finally {
//       setIsLoading(false);
//     }
//   };

//   // FONCTION CORRIGÉE POUR LE TÉLÉCHARGEMENT
//   const handleDownloadFlyer = async () => {
//     if (!flyerContainerRef.current || !flyerBackgroundUrl) {
//         setError("Impossible de trouver l'élément à capturer.");
//         return;
//     }

//     setIsLoading(true);
//     setError(null);

//     try {
//         // Méthode 1: Essayer html2canvas avec configuration optimisée
//         const canvas = await html2canvas(flyerContainerRef.current, {
//             useCORS: true,
//             allowTaint: true,
//             scale: 3, // Haute résolution
//             backgroundColor: null,
//             logging: false,
//             imageTimeout: 30000,
//             removeContainer: true,
//             foreignObjectRendering: true,
//             scrollX: 0,
//             scrollY: 0,
//             width: flyerContainerRef.current.scrollWidth,
//             height: flyerContainerRef.current.scrollHeight,
//             onclone: (clonedDoc) => {
//                 // Attendre le chargement des polices
//                 return new Promise((resolve) => {
//                     if (document.fonts && document.fonts.ready) {
//                         document.fonts.ready.then(() => {
//                             setTimeout(resolve, 1000);
//                         });
//                     } else {
//                         setTimeout(resolve, 1500);
//                     }
//                 });
//             }
//         });

//         // Vérifier la qualité du canvas
//         if (canvas.width === 0 || canvas.height === 0) {
//             throw new Error("Canvas vide généré");
//         }

//         const image = canvas.toDataURL('image/png', 1.0);
//         const link = document.createElement('a');
//         link.href = image;
//         link.download = `flyer_${contentInput.headline1.replace(/\s+/g, '_')}_${new Date().getTime()}.png`;
//         document.body.appendChild(link);
//         link.click();
//         document.body.removeChild(link);
        
//         alert("Votre flyer a été téléchargé avec succès !");
        
//     } catch (error) {
//         console.error("Erreur html2canvas:", error);
        
//         // Méthode de fallback: Générer côté serveur
//         try {
//             await handleDownloadFlyerServerSide();
//         } catch (serverError) {
//             console.error("Erreur serveur:", serverError);
            
//             // Dernier recours: télécharger l'image de fond
//             try {
//                 const response = await fetch(flyerBackgroundUrl);
//                 const blob = await response.blob();
//                 const url = window.URL.createObjectURL(blob);
//                 const link = document.createElement('a');
//                 link.href = url;
//                 link.download = `flyer_background_${new Date().getTime()}.png`;
//                 document.body.appendChild(link);
//                 link.click();
//                 document.body.removeChild(link);
//                 window.URL.revokeObjectURL(url);
                
//                 alert("Problème avec la capture complète. L'image de fond a été téléchargée. Vous pouvez ajouter le texte manuellement avec un logiciel d'édition.");
//             } catch (fallbackError) {
//                 setError("Impossible de télécharger le flyer. Vérifiez votre connexion et réessayez.");
//             }
//         }
//     } finally {
//         setIsLoading(false);
//     }
//   };

//   // NOUVELLE FONCTION: Téléchargement côté serveur
//   const handleDownloadFlyerServerSide = async () => {
//     const baseUrl = process.env.NODE_ENV === 'development'
//         ? 'http://localhost:5000'
//         : window.location.origin;

//     // Préparer les données des composants texte avec positions en pixels
//     const containerRect = flyerContainerRef.current.getBoundingClientRect();
//     const textData = textComponents.map(comp => ({
//         id: comp.id,
//         content: comp.content,
//         x: Math.round(comp.x),
//         y: Math.round(comp.y),
//         width: comp.width,
//         style: {
//             ...comp.style,
//             fontSize: parseInt(comp.style.fontSize) || 24,
//         },
//         minHeightPx: comp.minHeightPx || 0
//     }));

//     const response = await fetch(`${baseUrl}/api/generate-final-flyer`, {
//         method: 'POST',
//         headers: {
//             'Content-Type': 'application/json',
//         },
//         body: JSON.stringify({
//             background_url: flyerBackgroundUrl,
//             text_components: textData,
//             flyer_dimensions: {
//                 width: 360,
//                 height: 640
//             }
//         })
//     });

//     if (!response.ok) {
//         throw new Error('Erreur serveur lors de la génération du flyer final');
//     }

//     const blob = await response.blob();
//     const url = window.URL.createObjectURL(blob);
//     const link = document.createElement('a');
//     link.href = url;
//     link.download = `flyer_final_${contentInput.headline1.replace(/\s+/g, '_')}_${new Date().getTime()}.png`;
//     document.body.appendChild(link);
//     link.click();
//     document.body.removeChild(link);
//     window.URL.revokeObjectURL(url);
    
//     alert("Votre flyer a été téléchargé avec succès !");
//   };

//   const handleResetStyles = () => {
//     if (initialAiTextComponents) {
//         const resetComponents = initialAiTextComponents.map(comp => ({
//             ...comp,
//             style: { ...comp.style }
//         }));
//         setTextComponents(resetComponents);
//         setSelectedComponentId(null);
//         alert("Les styles ont été réinitialisés aux suggestions de l'IA.");
//     } else {
//         alert("Aucune suggestion initiale de l'IA à réinitialiser.");
//     }
//   };

//   const selectedComponent = textComponents.find(comp => comp.id === selectedComponentId);

//   return (
//     <div className="App">
//       <header className="App-header">
//         <h1>Générateur de Flyer par IA</h1>
//         <p>Importez votre design de base, ajoutez votre texte, laissez l'IA créer une image de fond personnalisée et suggérer les styles, puis placez et modifiez votre texte librement.</p>
//       </header>

//       <main>
//         <form onSubmit={handleSubmit} className="form-container">
//           {/* --- SECTION 1 : IMAGE DE BASE --- */}
//           <fieldset>
//             <legend>1. Image de Base pour le Style</legend>
//             <p className="field-description">Fournissez l'image de fond pour que l'IA en extraie le style. Elle générera une nouvelle image similaire SANS texte et suggérera des styles pour votre texte.</p>

//             <div
//               className={`drop-zone ${isDraggingOver ? 'drag-over' : ''}`}
//               onDragOver={handleDragOver}
//               onDragLeave={handleDragLeave}
//               onDrop={handleDrop}
//             >
//               <p>Glissez-déposez votre image ici, ou</p>
//               <label htmlFor="image-upload-input" className="custom-file-upload">
//                 {imageFile ? "Changer l'image" : "Choisir une image de style"}
//               </label>
//               <input
//                 id="image-upload-input"
//                 type="file"
//                 accept="image/*"
//                 onChange={handleImageChange}
//               />
//             </div>

//             {imagePreview && <div className="image-preview-container"><img src={imagePreview} alt="Aperçu de l'image de style" className="image-preview" /></div>}
//             {error && !imageFile && <p className="error-message">{error}</p>}
//           </fieldset>

//           {/* --- SECTION 2 : CONTENU DU FLYER (Texte) --- */}
//           <fieldset>
//             <legend>2. Contenu Texte du Flyer</legend>

//             <label htmlFor="headline1">Titre Principal</label>
//             <input type="text" id="headline1" name="headline1" value={contentInput.headline1} onChange={handleContentInputChange} placeholder="Ex: Soirée de Lancement"/>

//             <label htmlFor="short_description">Description Principale</label>
//             <p className="field-description">Le texte principal qui décrit votre événement ou message.</p>
//             <textarea
//               id="short_description"
//               name="short_description"
//               value={contentInput.short_description}
//               onChange={handleContentInputChange}
//               rows={4}
//               placeholder="Décrivez votre événement ici..."
//             />

//             <div className="event-grid">
//               <div>
//                 <label htmlFor="event_date">Date</label>
//                 <input type="date" id="event_date" name="event_date" value={contentInput.event_date} onChange={handleContentInputChange}/>
//               </div>
//               <div>
//                 <label htmlFor="event_time">Heure</label>
//                 <input type="time" id="event_time" name="event_time" value={contentInput.event_time} onChange={handleContentInputChange}/>
//               </div>
//               <div className="full-width">
//                 <label htmlFor="event_location">Lieu</label>
//                 <input type="text" id="event_location" name="event_location" value={contentInput.event_location} onChange={handleContentInputChange} placeholder="Ex: Le Grand Palais, Paris"/>
//               </div>
//             </div>
//           </fieldset>

//           {/* --- SECTION 3 : CONTACT --- */}
//           <fieldset>
//             <legend>3. Informations de Contact (Pied de page)</legend>
//             <div className="contact-grid">
//               <div>
//                 <label htmlFor="footer_email">Email</label>
//                 <input type="email" id="footer_email" name="footer_email" value={contentInput.footer_email} onChange={handleContentInputChange}/>
//               </div>
//               <div>
//                 <label htmlFor="footer_website">Site Web</label>
//                 <input type="text" id="footer_website" name="footer_website" value={contentInput.footer_website} onChange={handleContentInputChange}/>
//               </div>
//               <div>
//                 <label htmlFor="footer_phone">Téléphone</label>
//                 <input type="text" id="footer_phone" name="footer_phone" value={contentInput.footer_phone} onChange={handleContentInputChange}/>
//               </div>
//             </div>
//           </fieldset>

//           <button type="submit" disabled={isLoading || !imageFile} className="generate-btn">
//              {isLoading ? `Génération du fond et des styles...` : `Générer l'image de fond et les styles de texte`}
//           </button>
//         </form>

//         {/* --- SECTION RÉSULTATS --- */}
//         <div className="result-container">
//           {isLoading && <div className="loading-container"><div className="loader"></div><p>Génération de l'image de fond et analyse des styles...</p></div>}
//           {error && <p className="error-message">{error}</p>}

//           {flyerBackgroundUrl && (
//             <div className="flyer-editor-section">
//               <h2>Votre Design est Prêt ! 🚀</h2>
//               <p>Cliquez sur un bloc de texte pour le modifier et le positionner. Utilisez les contrôles ci-dessous pour ajuster les styles.</p>

//               {/* Toolbar de modification de style */}
//               {selectedComponent && (
//                 <div className="style-toolbar">
//                   <h3>Modifier {selectedComponent.id.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</h3>
//                   <div className="control-group">
//                     <label htmlFor="font-family-select">Police de Caractères:</label>
//                     <select
//                       id="font-family-select"
//                       value={selectedComponent.style.fontFamily || 'Arial, sans-serif'}
//                       onChange={(e) => handleStyleChange('fontFamily', e.target.value)}
//                       style={{ fontFamily: selectedComponent.style.fontFamily }}
//                     >
//                       {FONT_OPTIONS.map(font => (
//                         <option key={font} value={font} style={{ fontFamily: font }}>
//                           {font.split(',')[0]}
//                         </option>
//                       ))}
//                     </select>
//                   </div>

//                   <div className="control-group">
//                     <label htmlFor="font-size-slider">Taille du Texte (px):</label>
//                     <input
//                       type="range"
//                       id="font-size-slider"
//                       min="10"
//                       max="100"
//                       value={parseInt(selectedComponent.style.fontSize) || 24}
//                       onChange={(e) => handleStyleChange('fontSize', e.target.value)}
//                     />
//                     <span>{parseInt(selectedComponent.style.fontSize) || 24}px</span>
//                   </div>

//                   <div className="control-group">
//                     <label htmlFor="text-color-picker">Couleur du Texte:</label>
//                     <input
//                       type="color"
//                       id="text-color-picker"
//                       value={selectedComponent.style.color || '#FFFFFF'}
//                       onChange={(e) => handleStyleChange('color', e.target.value)}
//                     />
//                   </div>

//                   <div className="control-group">
//                     <label htmlFor="width-slider">Largeur du Conteneur (%):</label>
//                     <input
//                       type="range"
//                       id="width-slider"
//                       min="50"
//                       max="100"
//                       value={parseInt(selectedComponent.width) || 90}
//                       onChange={(e) => handleStyleChange('width', e.target.value)}
//                     />
//                     <span>{parseInt(selectedComponent.width) || 90}%</span>
//                   </div>

//                   <div className="control-group">
//                     <label htmlFor="min-height-slider">Hauteur Min. Conteneur (px):</label>
//                     <input
//                       type="range"
//                       id="min-height-slider"
//                       min="0"
//                       max="200"
//                       step="5"
//                       value={selectedComponent.minHeightPx || 0}
//                       onChange={(e) => handleStyleChange('minHeightPx', parseInt(e.target.value))}
//                     />
//                     <span>{selectedComponent.minHeightPx || 0}px</span>
//                   </div>
                  
//                   <button type="button" onClick={handleResetStyles} disabled={!initialAiTextComponents} className="reset-btn">
//                       Réinitialiser les styles (Suggestions IA)
//                   </button>
//                 </div>
//               )}

//               <div className="generated-flyer-preview-wrapper" onClick={() => setSelectedComponentId(null)}>
//                 <div 
//                   className="generated-flyer-preview" 
//                   ref={flyerContainerRef}
//                   style={{
//                     position: 'relative',
//                     width: '360px',
//                     height: '640px',
//                     margin: '0 auto',
//                     overflow: 'hidden',
//                     transform: 'translateZ(0)',
//                     backfaceVisibility: 'hidden',
//                     perspective: '1000px'
//                   }}
//                 >
//                   {/* Image de fond générée par l'IA */}
//                   <img 
//                     src={flyerBackgroundUrl} 
//                     alt="Flyer Background" 
//                     className="generated-background-image"
//                     style={{
//                       position: 'absolute',
//                       top: '0',
//                       left: '0',
//                       width: '100%',
//                       height: '100%',
//                       objectFit: 'cover',
//                       zIndex: '1',
//                       imageRendering: 'high-quality'
//                     }}
//                   />

//                   {/* Composants de texte déplaçables */}
//                   {textComponents.map(comp => {
//                     const nodeRef = componentRefsMap[comp.id];

//                     return (
//                       <Draggable
//                         key={comp.id}
//                         nodeRef={nodeRef}
//                         bounds="parent"
//                         defaultPosition={{ x: comp.x, y: comp.y }}
//                         onStop={(e, data) => handleStopDrag(e, data, comp.id)}
//                       >
//                         <div
//                           ref={nodeRef}
//                           className={`text-draggable-component text-type-${comp.type} ${selectedComponentId === comp.id ? 'selected' : ''}`}
//                           style={{
//                             ...comp.style,
//                             width: comp.width,
//                             minHeight: comp.minHeightPx ? `${comp.minHeightPx}px` : 'auto',
//                             position: 'absolute',
//                             zIndex: '2',
//                             cursor: 'move'
//                           }}
//                           onClick={(e) => {
//                               e.stopPropagation();
//                               handleComponentClick(comp.id);
//                           }}
//                         >
//                           <textarea
//                             value={comp.content}
//                             onChange={(e) => handleComponentTextChange(comp.id, e.target.value)}
//                             style={{
//                               fontFamily: comp.style.fontFamily,
//                               fontSize: comp.style.fontSize,
//                               fontWeight: comp.style.fontWeight,
//                               textAlign: comp.style.textAlign,
//                               color: comp.style.color,
//                               lineHeight: comp.style.lineHeight,
//                               textShadow: comp.style.textShadow,

//                               width: '100%',
//                               height: 'auto',
//                               resize: 'none',
//                               border: 'none',
//                               background: 'transparent',
//                               padding: 0,
//                               margin: 0,
//                               overflowY: 'hidden',
//                               outline: 'none',
//                             }}
//                             rows={Math.max(1, Math.ceil(
//                                 (comp.content.length * ( (parseInt(comp.style.fontSize) || 24) * 0.55 )) /
//                                 ( (parseInt(comp.width) / 100 * 360) - 20 )
//                             ))}
//                           />
//                         </div>
//                       </Draggable>
//                     );
//                   })}
//                 </div>
//               </div>
//               <button onClick={handleDownloadFlyer} disabled={isLoading} className="download-btn">
//                 {isLoading ? "Préparation au téléchargement..." : "📥 Télécharger le Flyer Complet (Image + Texte)"}
//               </button>
//             </div>
//           )}
//         </div>
//       </main>
//     </div>
//   );
// }


























// "use client";  

// import { useState } from 'react';
// import Image from 'next/image'; // Gardons-le, même s'il n'est pas utilisé directement pour le preview
// import './globals.css';

// export default function HomePage() {
//   const [imageFile, setImageFile] = useState(null);
//   const [imagePreview, setImagePreview] = useState(null);
  
//   // Nouveau state pour le drag-and-drop
//   const [isDraggingOver, setIsDraggingOver] = useState(false);

//   // L'instruction n'est plus aussi critique car on utilise l'image, mais gardons-la.
//   const [instruction, setInstruction] = useState('Style luxueux et élégant, or et bleu nuit, ambiance de gala prestigieux.');
  
//   // Note : la génération de plusieurs images n'est pas gérée par le backend actuel qui se base sur une seule image d'entrée.
//   // On va le forcer à 1 pour éviter toute confusion.
//   const [numImages, setNumImages] = useState(1);

//   const [content, setContent] = useState({
//     headline1: 'Gala Annuel 2024',
//     short_description: 'Join us for an unforgettable evening of celebration and networking — a unique opportunity to connect with industry leaders in an exceptional setting.',
//     event_date: '2024-12-05',
//     event_time: '19:00',
//     event_location: 'Le Grand Palais, Paris',
//     footer_email: 'rsvp@votre-gala.com',
//     footer_website: 'www.votre-gala.com',
//     footer_phone: '+33 1 98 76 54 32'
//   });

//   const [isLoading, setIsLoading] = useState(false);
//   const [error, setError] = useState(null);
//   const [generatedFlyerUrls, setGeneratedFlyerUrls] = useState([]);

//   // Nouvelle fonction pour traiter le fichier, appelée par le input ou le drag-drop
//   const processFile = (file) => {
//     if (file) {
//       // Validation simple pour s'assurer que c'est une image
//       if (file.type.startsWith('image/')) {
//         setImageFile(file);
//         setImagePreview(URL.createObjectURL(file));
//         setError(null); // Nettoyer les erreurs précédentes
//       } else {
//         setError("Veuillez importer un fichier image valide (JPG, PNG, GIF, etc.).");
//         setImageFile(null);
//         setImagePreview(null);
//       }
//     }
//   };

//   const handleImageChange = (e) => {
//     processFile(e.target.files[0]);
//   };

//   // Gestionnaires pour le Drag & Drop
//   const handleDragOver = (e) => {
//     e.preventDefault(); // Nécessaire pour permettre le drop
//     setIsDraggingOver(true);
//   };

//   const handleDragLeave = () => {
//     setIsDraggingOver(false);
//   };

//   const handleDrop = (e) => {
//     e.preventDefault(); // Empêche le navigateur d'ouvrir le fichier directement
//     setIsDraggingOver(false);
//     if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
//       processFile(e.dataTransfer.files[0]);
//     }
//   };

//   const handleContentChange = (e) => {
//     const { name, value } = e.target;
//     setContent(prev => ({ ...prev, [name]: value }));
//   };

//   const handleSubmit = async (e) => {
//     e.preventDefault();
    
//     // Vérification cruciale : on ne peut pas générer sans image de base.
//     if (!imageFile) {
//         setError("Veuillez choisir une image de style pour commencer.");
//         return;
//     }

//     setIsLoading(true);
//     setError(null);
//     setGeneratedFlyerUrls([]);

//     const formData = new FormData();
//     formData.append('image', imageFile);
    
//     // --- CORRECTION ET SIMPLIFICATION ICI ---
//     // On construit les champs 'event_info' et 'footer_info' comme attendu par le backend.
    
//     // 1. Ajouter le titre et la description
//     formData.append('headline1', content.headline1);
//     formData.append('short_description', content.short_description);

//     // 2. Regrouper les informations de l'événement
//     // On ne combine que les champs qui ont une valeur.
//     const eventDetails = [
//         content.event_date ? new Date(content.event_date).toLocaleDateString('fr-FR') : '', // Format localisé
//         content.event_time,
//         content.event_location
//     ].filter(Boolean).join(' - '); // Le .filter(Boolean) enlève les chaînes vides
//     formData.append('event_info', eventDetails);

//     // 3. Regrouper les informations de contact
//     const footerDetails = [
//         content.footer_email,
//         content.footer_website,
//         content.footer_phone
//     ].filter(Boolean).join(' | ');
//     formData.append('footer_info', footerDetails);
    
//     // ------------------------------------------

//     try {
//       //const response = await fetch('http://localhost:5000/api/generate-flyer-from-prototype', { 
//       const baseUrl = process.env.NODE_ENV === 'development' 
//         ? 'http://localhost:5000' 
//         : window.location.origin;
//       const response = await fetch(`${baseUrl}/api/generate-flyer-from-prototype`, { 
//         method: 'POST', 
//         body: formData 
//       });
//       const data = await response.json();
//       if (!response.ok) throw new Error(data.error || 'Une erreur est survenue.');
//       setGeneratedFlyerUrls(data.flyer_urls);
//     } catch (err) {
//       setError(err.message);
//     } finally {
//       setIsLoading(false);
//     }
//   };

//   return (
//     <div className="App">
//       <header className="App-header">
//         <h1>Générateur de Flyer par IA</h1>
//         <p>Importez votre design de base, ajoutez votre texte, et laissez l'IA l'intégrer parfaitement.</p>
//       </header>

//       <main>
//         <form onSubmit={handleSubmit} className="form-container">
//           {/* --- SECTION 1 : IMAGE DE BASE --- */}
//           <fieldset>
//             <legend>1. Image de Base</legend>
//             <p className="field-description">Fournissez l'image de fond sur laquelle le texte sera ajouté.</p>
            
//             {/* Zone de Drag & Drop */}
//             <div 
//               className={`drop-zone ${isDraggingOver ? 'drag-over' : ''}`}
//               onDragOver={handleDragOver}
//               onDragLeave={handleDragLeave}
//               onDrop={handleDrop}
//             >
//               <p>Glissez-déposez votre image ici, ou</p>
//               <label htmlFor="image-upload-input" className="custom-file-upload">
//                 {imageFile ? "Changer l'image" : "Choisir une image de fond"}
//               </label>
//               <input 
//                 id="image-upload-input" 
//                 type="file" 
//                 accept="image/*" 
//                 onChange={handleImageChange} 
//                 // Removed 'required' here as the form validation handles missing imageFile
//               />
//             </div>
            
//             {imagePreview && <div className="image-preview-container"><img src={imagePreview} alt="Aperçu" className="image-preview" /></div>}
//             {error && !imageFile && <p className="error-message">{error}</p>} {/* Affiche l'erreur si pas d'image */}
//           </fieldset>
          
//           {/* --- SECTION 2 : CONTENU DU FLYER --- */}
//           <fieldset>
//             <legend>2. Contenu du Flyer</legend>
            
//             <label htmlFor="headline1">Titre Principal</label>
//             <input type="text" id="headline1" name="headline1" value={content.headline1} onChange={handleContentChange} placeholder="Ex: Soirée de Lancement"/>
            
//             <label htmlFor="short_description">Description Principale</label>
//             <p className="field-description">Le texte principal qui décrit votre événement ou message.</p>
//             <textarea 
//               id="short_description" 
//               name="short_description" 
//               value={content.short_description} 
//               onChange={handleContentChange} 
//               rows={4}
//               placeholder="Décrivez votre événement ici..."
//             />

//             <div className="event-grid">
//               <div>
//                 <label htmlFor="event_date">Date</label>
//                 <input type="date" id="event_date" name="event_date" value={content.event_date} onChange={handleContentChange}/>
//               </div>
//               <div>
//                 <label htmlFor="event_time">Heure</label>
//                 <input type="time" id="event_time" name="event_time" value={content.event_time} onChange={handleContentChange}/>
//               </div>
//               <div className="full-width">
//                 <label htmlFor="event_location">Lieu</label>
//                 <input type="text" id="event_location" name="event_location" value={content.event_location} onChange={handleContentChange} placeholder="Ex: 123 Rue de l'Innovation, Paris"/>
//               </div>
//             </div>
//           </fieldset>
          
//           {/* --- SECTION 3 : CONTACT --- */}
//           <fieldset>
//             <legend>3. Informations de Contact (Pied de page)</legend>
//             <div className="contact-grid">
//               <div>
//                 <label htmlFor="footer_email">Email</label>
//                 <input type="email" id="footer_email" name="footer_email" value={content.footer_email} onChange={handleContentChange}/>
//               </div>
//               <div>
//                 <label htmlFor="footer_website">Site Web</label>
//                 <input type="text" id="footer_website" name="footer_website" value={content.footer_website} onChange={handleContentChange}/>
//               </div>
//               <div>
//                 <label htmlFor="footer_phone">Téléphone</label>
//                 <input type="text" id="footer_phone" name="footer_phone" value={content.footer_phone} onChange={handleContentChange}/>
//               </div>
//             </div>
//           </fieldset>
          
//           <button type="submit" disabled={isLoading || !imageFile} className="generate-btn">
//              {isLoading ? `Génération en cours...` : `Intégrer le Texte sur l'Image`}
//           </button>
//         </form>

//         {/* --- SECTION RÉSULTATS --- */}
//         <div className="result-container">
//           {isLoading && <div className="loading-container"><div className="loader"></div><p>Analyse de l'image et intégration du texte...</p></div>}
//           {error && imageFile && <p className="error-message">Erreur : {error}</p>} {/* Affiche l'erreur si l'image est là, mais il y a une autre erreur */}
//           {generatedFlyerUrls.length > 0 && (
//             <div>
//               <h2>Votre Design est prêt ! 🚀</h2>
//               <div className="gallery-container">
//                 {generatedFlyerUrls.map((url, index) => (
//                   <div key={index} className="gallery-item">
//                     {/* Utiliser un <img> standard peut être plus simple ici si les dimensions varient */}
//                     <img src={url} alt={`Flyer généré ${index + 1}`} className="generated-flyer" style={{ width: '100%', height: 'auto' }} />
//                     <a href={url} target="_blank" rel="noopener noreferrer" className="download-link">📥 Télécharger le Design</a>
//                   </div>
//                 ))}
//               </div>
//             </div>
//           )}
//         </div>
//       </main>
//     </div>
//   );
// }