// FLYER-IA/flyer-ia/frontend/app/page.js

"use client";

import { useState, useRef, useEffect, useCallback } from 'react';
import Image from 'next/image';
import html2canvas from 'html2canvas';
import Draggable from 'react-draggable';
import './globals.css';

// Liste des polices disponibles pour la sélection manuelle
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
];


export default function HomePage() {
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [isDraggingOver, setIsDraggingOver] = useState(false);

  const [contentInput, setContentInput] = useState({
    headline1: 'Gala Annuel 2024',
    short_description: 'Join us for an unforgettable evening of celebration and networking — a unique opportunity to connect with industry leaders in an exceptional setting.',
    event_date: '2024-12-05',
    event_time: '19:00',
    event_location: 'Le Grand Palais, Paris',
    footer_email: 'rsvp@votre-gala.com',
    footer_website: 'www.votre-gala.com',
    footer_phone: '+33 1 98 76 54 32'
  });

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [flyerBackgroundUrl, setFlyerBackgroundUrl] = useState(null);

  const [textComponents, setTextComponents] = useState([]);
  const [aiTextStyleSuggestions, setAiTextStyleSuggestions] = useState(null);

  const [initialAiTextComponents, setInitialAiTextComponents] = useState(null);

  const [selectedComponentId, setSelectedComponentId] = useState(null);

  const flyerContainerRef = useRef(null);

  const headlineRef = useRef(null);
  const descriptionRef = useRef(null);
  const eventInfoRef = useRef(null);
  const footerRef = useRef(null);

  const componentRefsMap = {
      headline: headlineRef,
      description: descriptionRef,
      event_info: eventInfoRef,
      footer: footerRef
  };

  const initializeTextComponents = useCallback((aiSuggestions, currentContentInput) => {
    const eventDetails = [
      currentContentInput.event_date ? new Date(currentContentInput.event_date).toLocaleDateString('fr-FR') : '',
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

    const previewWidth = 360;
    const previewHeight = 640;

    const styledComponents = rawComponents.map(comp => {
      const style = aiSuggestions[comp.type] || {};

      const initialTopPercentage = style.initialTopPercentage !== undefined ? style.initialTopPercentage : (
        comp.type === 'headline' ? 10 :
        comp.type === 'description' ? 30 :
        comp.type === 'event_info' ? 65 :
        88
      );
      const initialWidthPercentage = style.initialWidthPercentage !== undefined ? style.initialWidthPercentage : (
        comp.type === 'description' ? 80 : 90
      );

      const initialY = (initialTopPercentage / 100) * previewHeight;

      const actualWidthInPixels = (initialWidthPercentage / 100) * previewWidth;
      let initialX = 0;
      const horizontalMargin = 15;
      if (style.textAlign === 'center') {
        initialX = (previewWidth - actualWidthInPixels) / 2;
      } else if (style.textAlign === 'right') {
        initialX = previewWidth - actualWidthInPixels - horizontalMargin;
      } else {
        initialX = horizontalMargin;
      }

      const textColor = style.color || '#FFFFFF';
      const isLightColor = parseInt(textColor.replace('#', ''), 16) > 0xFFFFFF / 2;
      const shadowColor = isLightColor ? 'rgba(0, 0, 0, 0.8)' : 'rgba(255, 255, 255, 0.8)';
      const textShadowStyle = `1px 1px 2px ${shadowColor}, -1px -1px 2px ${shadowColor}`;

      return {
        ...comp,
        x: initialX,
        y: initialY,
        width: `${initialWidthPercentage}%`,
        minHeightPx: 0,
        style: {
          fontFamily: style.fontFamily || 'Arial, sans-serif',
          color: textColor,
          fontSize: `${style.fontSizePx || 24}px`,
          fontWeight: style.fontWeight || 'normal',
          textAlign: style.textAlign || 'center',
          lineHeight: `${style.lineHeightEm || 1.4}em`,
          textShadow: textShadowStyle,
        }
      };
    });
    return styledComponents;
  }, []);

  useEffect(() => {
    if (aiTextStyleSuggestions && flyerBackgroundUrl) {
      const newComponents = initializeTextComponents(aiTextStyleSuggestions, contentInput);
      setTextComponents(newComponents);
      setInitialAiTextComponents(newComponents);
    }
  }, [aiTextStyleSuggestions, flyerBackgroundUrl, contentInput, initializeTextComponents]);

  const processFile = (file) => {
    if (file) {
      if (file.type.startsWith('image/')) {
        setImageFile(file);
        setImagePreview(URL.createObjectURL(file));
        setError(null);
        setFlyerBackgroundUrl(null);
        setTextComponents([]);
        setAiTextStyleSuggestions(null);
        setInitialAiTextComponents(null);
        setSelectedComponentId(null);
      } else {
        setError("Veuillez importer un fichier image valide (JPG, PNG, GIF, etc.).");
        setImageFile(null);
        setImagePreview(null);
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

    setTextComponents(prevComponents =>
      prevComponents.map(comp => {
        let newContent = comp.content;
        const updatedContentInput = { ...contentInput, [name]: value }; 

        if (comp.id === 'headline' && name === 'headline1') {
          newContent = value;
        } else if (comp.id === 'description' && name === 'short_description') {
          newContent = value;
        } else if (comp.id === 'event_info' && ['event_date', 'event_time', 'event_location'].includes(name)) {
          newContent = [
            updatedContentInput.event_date ? new Date(updatedContentInput.event_date).toLocaleDateString('fr-FR') : '',
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

          if (styleProp === 'fontSize') {
            newStyle.fontSize = `${value}px`;
          } else if (styleProp === 'color') {
            newStyle.color = value;
            const isLightColor = parseInt(value.replace('#', ''), 16) > 0xFFFFFF / 2;
            const shadowColor = isLightColor ? 'rgba(0, 0, 0, 0.8)' : 'rgba(255, 255, 255, 0.8)';
            newStyle.textShadow = `1px 1px 2px ${shadowColor}, -1px -1px 2px ${shadowColor}`;
          } else if (styleProp === 'width') {
            newWidth = `${value}%`;
          } else if (styleProp === 'minHeightPx') {
            newMinHeightPx = value;
          } else if (styleProp === 'fontFamily') {
            newStyle.fontFamily = value;
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

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!imageFile) {
        setError("Veuillez choisir une image de style pour commencer.");
        return;
    }

    setIsLoading(true);
    setError(null);
    setFlyerBackgroundUrl(null);
    setTextComponents([]);
    setAiTextStyleSuggestions(null);
    setInitialAiTextComponents(null);
    setSelectedComponentId(null);

    const formData = new FormData();
    formData.append('image', imageFile);
    // IMPORTANT: Ces champs sont ajoutés pour que la route Flask puisse les lire.
    // Mais ils ne seront PLUS utilisés dans le prompt d'Imagen lui-même.
    formData.append('headline1', contentInput.headline1);
    formData.append('short_description', contentInput.short_description);
    const eventDetails = [
        contentInput.event_date ? new Date(contentInput.event_date).toLocaleDateString('fr-FR') : '',
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

      const response = await fetch(`${baseUrl}/api/generate-flyer-from-prototype`, {
        method: 'POST',
        body: formData
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Une erreur est survenue.');

      setFlyerBackgroundUrl(data.flyer_background_url);
      setAiTextStyleSuggestions(data.text_style_suggestions);

    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownloadFlyer = async () => {
    if (!flyerContainerRef.current) {
        setError("Impossible de trouver l'élément à capturer.");
        return;
    }

    setIsLoading(true);
    setError(null);

    try {
        const canvas = await html2canvas(flyerContainerRef.current, {
            useCORS: true,
            allowTaint: true,
            scale: 2, // Pour une meilleure résolution
            backgroundColor: null,
        });

        const image = canvas.toDataURL('image/png');
        const link = document.createElement('a');
        link.href = image;
        link.download = 'flyer_final_avec_texte.png';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        alert("Votre flyer a été téléchargé !");
    } catch (error) {
        console.error("Erreur lors de la génération de l'image finale:", error);
        setError("Impossible de générer l'image finale du flyer. Vérifiez la console pour les détails.");
    } finally {
        setIsLoading(false);
    }
  };

  const handleResetStyles = () => {
    if (initialAiTextComponents) {
        const resetComponents = initialAiTextComponents.map(comp => ({
            ...comp,
            style: { ...comp.style }
        }));
        setTextComponents(resetComponents);
        setSelectedComponentId(null);
        alert("Les styles ont été réinitialisés aux suggestions de l'IA.");
    } else {
        alert("Aucune suggestion initiale de l'IA à réinitialiser.");
    }
  };

  const selectedComponent = textComponents.find(comp => comp.id === selectedComponentId);


  return (
    <div className="App">
      <header className="App-header">
        <h1>Générateur de Flyer par IA</h1>
        <p>Importez votre design de base, ajoutez votre texte, laissez l'IA créer une image de fond personnalisée et suggérer les styles, puis placez et modifiez votre texte librement.</p>
      </header>

      <main>
        <form onSubmit={handleSubmit} className="form-container">
          {/* --- SECTION 1 : IMAGE DE BASE --- */}
          <fieldset>
            <legend>1. Image de Base pour le Style</legend>
            <p className="field-description">Fournissez l'image de fond pour que l'IA en extraie le style. Elle générera une nouvelle image similaire SANS texte et suggérera des styles pour votre texte.</p>

            <div
              className={`drop-zone ${isDraggingOver ? 'drag-over' : ''}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <p>Glissez-déposez votre image ici, ou</p>
              <label htmlFor="image-upload-input" className="custom-file-upload">
                {imageFile ? "Changer l'image" : "Choisir une image de style"}
              </label>
              <input
                id="image-upload-input"
                type="file"
                accept="image/*"
                onChange={handleImageChange}
              />
            </div>

            {imagePreview && <div className="image-preview-container"><img src={imagePreview} alt="Aperçu de l'image de style" className="image-preview" /></div>}
            {error && !imageFile && <p className="error-message">{error}</p>}
          </fieldset>

          {/* --- SECTION 2 : CONTENU DU FLYER (Texte) --- */}
          <fieldset>
            <legend>2. Contenu Texte du Flyer</legend>

            <label htmlFor="headline1">Titre Principal</label>
            <input type="text" id="headline1" name="headline1" value={contentInput.headline1} onChange={handleContentInputChange} placeholder="Ex: Soirée de Lancement"/>

            <label htmlFor="short_description">Description Principale</label>
            <p className="field-description">Le texte principal qui décrit votre événement ou message.</p>
            <textarea
              id="short_description"
              name="short_description"
              value={contentInput.short_description}
              onChange={handleContentInputChange}
              rows={4}
              placeholder="Décrivez votre événement ici..."
            />

            <div className="event-grid">
              <div>
                <label htmlFor="event_date">Date</label>
                <input type="date" id="event_date" name="event_date" value={contentInput.event_date} onChange={handleContentInputChange}/>
              </div>
              <div>
                <label htmlFor="event_time">Heure</label>
                <input type="time" id="event_time" name="event_time" value={contentInput.event_time} onChange={handleContentInputChange}/>
              </div>
              <div className="full-width">
                <label htmlFor="event_location">Lieu</label>
                <input type="text" id="event_location" name="event_location" value={contentInput.event_location} onChange={handleContentInputChange} placeholder="Ex: Le Grand Palais, Paris"/>
              </div>
            </div>
          </fieldset>

          {/* --- SECTION 3 : CONTACT --- */}
          <fieldset>
            <legend>3. Informations de Contact (Pied de page)</legend>
            <div className="contact-grid">
              <div>
                <label htmlFor="footer_email">Email</label>
                <input type="email" id="footer_email" name="footer_email" value={contentInput.footer_email} onChange={handleContentInputChange}/>
              </div>
              <div>
                <label htmlFor="footer_website">Site Web</label>
                <input type="text" id="footer_website" name="footer_website" value={contentInput.footer_website} onChange={handleContentInputChange}/>
              </div>
              <div>
                <label htmlFor="footer_phone">Téléphone</label>
                <input type="text" id="footer_phone" name="footer_phone" value={contentInput.footer_phone} onChange={handleContentInputChange}/>
              </div>
            </div>
          </fieldset>

          <button type="submit" disabled={isLoading || !imageFile} className="generate-btn">
             {isLoading ? `Génération du fond et des styles...` : `Générer l'image de fond et les styles de texte`}
          </button>
        </form>

        {/* --- SECTION RÉSULTATS --- */}
        <div className="result-container">
          {isLoading && <div className="loading-container"><div className="loader"></div><p>Génération de l'image de fond et analyse des styles...</p></div>}
          {error && <p className="error-message">{error}</p>}

          {flyerBackgroundUrl && (
            <div className="flyer-editor-section">
              <h2>Votre Design est Prêt ! 🚀</h2>
              <p>Cliquez sur un bloc de texte pour le modifier et le positionner. Utilisez les contrôles ci-dessous pour ajuster les styles.</p>

              {/* NOUVEAU: Toolbar de modification de style */}
              {selectedComponent && (
                <div className="style-toolbar">
                  <h3>Modifier {selectedComponent.id.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</h3>
                  <div className="control-group">
                    <label htmlFor="font-family-select">Police de Caractères:</label>
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
                    <label htmlFor="font-size-slider">Taille du Texte (px):</label>
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
                    <label htmlFor="text-color-picker">Couleur du Texte:</label>
                    <input
                      type="color"
                      id="text-color-picker"
                      value={selectedComponent.style.color || '#FFFFFF'}
                      onChange={(e) => handleStyleChange('color', e.target.value)}
                    />
                  </div>

                  <div className="control-group">
                    <label htmlFor="width-slider">Largeur du Conteneur (%):</label>
                    <input
                      type="range"
                      id="width-slider"
                      min="50"
                      max="100"
                      value={parseInt(selectedComponent.width) || 90}
                      onChange={(e) => handleStyleChange('width', e.target.value)}
                    />
                    <span>{parseInt(selectedComponent.width) || 90}%</span>
                  </div>

                  <div className="control-group">
                    <label htmlFor="min-height-slider">Hauteur Min. Conteneur (px):</label>
                    <input
                      type="range"
                      id="min-height-slider"
                      min="0"
                      max="200"
                      step="5"
                      value={selectedComponent.minHeightPx || 0}
                      onChange={(e) => handleStyleChange('minHeightPx', parseInt(e.target.value))}
                    />
                    <span>{selectedComponent.minHeightPx || 0}px</span>
                  </div>
                  {/* Bouton de réinitialisation */}
                  <button type="button" onClick={handleResetStyles} disabled={!initialAiTextComponents} className="reset-btn">
                      Réinitialiser les styles (Suggestions IA)
                  </button>
                </div>
              )}

              <div className="generated-flyer-preview-wrapper" onClick={() => setSelectedComponentId(null)}>
                <div className="generated-flyer-preview" ref={flyerContainerRef}>
                  {/* Image de fond générée par l'IA */}
                  <img src={flyerBackgroundUrl} alt="Flyer Background" className="generated-background-image" />

                  {/* Composants de texte déplaçables */}
                  {textComponents.map(comp => {
                    const nodeRef = componentRefsMap[comp.id];

                    return (
                      <Draggable
                        key={comp.id}
                        nodeRef={nodeRef}
                        bounds="parent"
                        defaultPosition={{ x: comp.x, y: comp.y }}
                        onStop={(e, data) => handleStopDrag(e, data, comp.id)}
                      >
                        <div
                          ref={nodeRef}
                          className={`text-draggable-component text-type-${comp.type} ${selectedComponentId === comp.id ? 'selected' : ''}`}
                          style={{
                            ...comp.style,
                            width: comp.width,
                            minHeight: comp.minHeightPx ? `${comp.minHeightPx}px` : 'auto',
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
                              textShadow: comp.style.textShadow,

                              width: '100%',
                              height: 'auto',
                              resize: 'none',
                              border: 'none',
                              background: 'transparent',
                              padding: 0,
                              margin: 0,
                              overflowY: 'hidden',
                              outline: 'none',
                            }}
                            rows={Math.max(1, Math.ceil(
                                (comp.content.length * ( (parseInt(comp.style.fontSize) || 24) * 0.55 )) /
                                ( (parseInt(comp.width) / 100 * 360) - 20 )
                            ))}
                          />
                        </div>
                      </Draggable>
                    );
                  })}
                </div>
              </div>
              <button onClick={handleDownloadFlyer} disabled={isLoading} className="download-btn">
                {isLoading ? "Préparation au téléchargement..." : "📥 Télécharger le Flyer Complet (Image + Texte)"}
              </button>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}





















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