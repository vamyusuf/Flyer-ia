"use client";  

import { useState } from 'react';
import Image from 'next/image';
import './globals.css';

export default function HomePage() {
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  
  // L'instruction n'est plus aussi critique car on utilise l'image, mais gardons-la.
  const [instruction, setInstruction] = useState('Style luxueux et élégant, or et bleu nuit, ambiance de gala prestigieux.');
  
  // Note : la génération de plusieurs images n'est pas gérée par le backend actuel qui se base sur une seule image d'entrée.
  // On va le forcer à 1 pour éviter toute confusion.
  const [numImages, setNumImages] = useState(1);

  const [content, setContent] = useState({
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
  const [generatedFlyerUrls, setGeneratedFlyerUrls] = useState([]);

  
  const handleImageChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setImageFile(file);
      setImagePreview(URL.createObjectURL(file));
    }
  };

  const handleContentChange = (e) => {
    const { name, value } = e.target;
    setContent(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Vérification cruciale : on ne peut pas générer sans image de base.
    if (!imageFile) {
        setError("Veuillez choisir une image de style pour commencer.");
        return;
    }

    setIsLoading(true);
    setError(null);
    setGeneratedFlyerUrls([]);

    const formData = new FormData();
    formData.append('image', imageFile);
    
    // --- CORRECTION ET SIMPLIFICATION ICI ---
    // On construit les champs 'event_info' et 'footer_info' comme attendu par le backend.
    
    // 1. Ajouter le titre et la description
    formData.append('headline1', content.headline1);
    formData.append('short_description', content.short_description);

    // 2. Regrouper les informations de l'événement
    // On ne combine que les champs qui ont une valeur.
    const eventDetails = [
        content.event_date ? new Date(content.event_date).toLocaleDateString('fr-FR') : '', // Format localisé
        content.event_time,
        content.event_location
    ].filter(Boolean).join(' - '); // Le .filter(Boolean) enlève les chaînes vides
    formData.append('event_info', eventDetails);

    // 3. Regrouper les informations de contact
    const footerDetails = [
        content.footer_email,
        content.footer_website,
        content.footer_phone
    ].filter(Boolean).join(' | ');
    formData.append('footer_info', footerDetails);
    
    // ------------------------------------------

    try {
      const response = await fetch('http://localhost:5000/api/generate-flyer-from-prototype', { 
        method: 'POST', 
        body: formData 
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Une erreur est survenue.');
      setGeneratedFlyerUrls(data.flyer_urls);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Générateur de Flyer par IA</h1>
        <p>Importez votre design de base, ajoutez votre texte, et laissez l&apos;IA l&apos;intégrer parfaitement.</p>
      </header>

      <main>
        <form onSubmit={handleSubmit} className="form-container">
          {/* --- SECTION 1 : IMAGE DE BASE --- */}
          <fieldset>
            <legend>1. Image de Base</legend>
            <p className="field-description">Fournissez l&apos;image de fond sur laquelle le texte sera ajouté.</p>
            <label htmlFor="image-upload-input" className="custom-file-upload">{imageFile ? "Changer l'image" : "Choisir une image de fond"}</label>
            <input id="image-upload-input" type="file" accept="image/*" onChange={handleImageChange} required />
            {imagePreview && <div className="image-preview-container"><img src={imagePreview} alt="Aperçu" className="image-preview" /></div>}
          </fieldset>
          
          {/* --- SECTION 2 : CONTENU DU FLYER --- */}
          <fieldset>
            <legend>2. Contenu du Flyer</legend>
            
            <label htmlFor="headline1">Titre Principal</label>
            <input type="text" id="headline1" name="headline1" value={content.headline1} onChange={handleContentChange} placeholder="Ex: Soirée de Lancement"/>
            
            <label htmlFor="short_description">Description Principale</label>
            <p className="field-description">Le texte principal qui décrit votre événement ou message.</p>
            <textarea 
              id="short_description" 
              name="short_description" 
              value={content.short_description} 
              onChange={handleContentChange} 
              rows={4}
              placeholder="Décrivez votre événement ici..."
            />

            <div className="event-grid">
              <div>
                <label htmlFor="event_date">Date</label>
                <input type="date" id="event_date" name="event_date" value={content.event_date} onChange={handleContentChange}/>
              </div>
              <div>
                <label htmlFor="event_time">Heure</label>
                <input type="time" id="event_time" name="event_time" value={content.event_time} onChange={handleContentChange}/>
              </div>
              <div className="full-width">
                <label htmlFor="event_location">Lieu</label>
                <input type="text" id="event_location" name="event_location" value={content.event_location} onChange={handleContentChange} placeholder="Ex: 123 Rue de l'Innovation, Paris"/>
              </div>
            </div>
          </fieldset>
          
          {/* --- SECTION 3 : CONTACT --- */}
          <fieldset>
            <legend>3. Informations de Contact (Pied de page)</legend>
            <div className="contact-grid">
              <div>
                <label htmlFor="footer_email">Email</label>
                <input type="email" id="footer_email" name="footer_email" value={content.footer_email} onChange={handleContentChange}/>
              </div>
              <div>
                <label htmlFor="footer_website">Site Web</label>
                <input type="text" id="footer_website" name="footer_website" value={content.footer_website} onChange={handleContentChange}/>
              </div>
              <div>
                <label htmlFor="footer_phone">Téléphone</label>
                <input type="text" id="footer_phone" name="footer_phone" value={content.footer_phone} onChange={handleContentChange}/>
              </div>
            </div>
          </fieldset>
          
          <button type="submit" disabled={isLoading || !imageFile} className="generate-btn">
             {isLoading ? `Génération en cours...` : `Intégrer le Texte sur l'Image`}
          </button>
        </form>

        {/* --- SECTION RÉSULTATS --- */}
        <div className="result-container">
          {isLoading && <div className="loading-container"><div className="loader"></div><p>Analyse de l&apos;image et intégration du texte...</p></div>}
          {error && <p className="error-message">Erreur : {error}</p>}
          {generatedFlyerUrls.length > 0 && (
            <div>
              <h2>Votre Design est prêt ! 🚀</h2>
              <div className="gallery-container">
                {generatedFlyerUrls.map((url, index) => (
                  <div key={index} className="gallery-item">
                    {/* Utiliser un <img> standard peut être plus simple ici si les dimensions varient */}
                    <img src={url} alt={`Flyer généré ${index + 1}`} className="generated-flyer" style={{ width: '100%', height: 'auto' }} />
                    <a href={url} target="_blank" rel="noopener noreferrer" className="download-link">📥 Télécharger le Design</a>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
