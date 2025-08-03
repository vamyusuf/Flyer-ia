"use client";

import React, { useState, useRef, useEffect, useCallback } from 'react';
import dynamic from 'next/dynamic';
import 'react-resizable/css/styles.css';

const Draggable = dynamic(() => import('react-draggable'), { 
  ssr: false,
  loading: () => <p>Chargement du glisser-déposer...</p>
});
const ResizableBox = dynamic(() => import('react-resizable').then(mod => mod.ResizableBox), { 
  ssr: false,
  loading: () => <p>Chargement du redimensionnement...</p>
});

const TEXT_STYLES_MAP = {
  'bold': 'gras',
  'italic': 'italique',
  'underline': 'souligné',
  'gold': 'doré',
  'white': 'blanc',
  'black': 'noir',
  'blue': 'bleu',
  'red': 'rouge',
  'very large': 'très grand',
  'large': 'grand',
  'medium': 'moyen',
  'small': 'petit'
};

function cssStyleToDescription(cssProps = {}) {
  const description = [];
  
  if (cssProps.fontWeight && (cssProps.fontWeight === 'bold' || parseInt(cssProps.fontWeight) >= 700)) {
    description.push(TEXT_STYLES_MAP['bold']);
  }
  if (cssProps.fontStyle === 'italic') {
    description.push(TEXT_STYLES_MAP['italic']);
  }
  if (cssProps.textDecoration?.includes('underline')) {
    description.push(TEXT_STYLES_MAP['underline']);
  }

  if (cssProps.color) {
    const color = cssProps.color.toLowerCase();
    const mappedColor = Object.keys(TEXT_STYLES_MAP).find(key => color.includes(key));
    description.push(mappedColor ? TEXT_STYLES_MAP[mappedColor] : `couleur ${cssProps.color}`);
  }

  if (cssProps.fontSize) {
    const sizeValue = parseFloat(cssProps.fontSize);
    if (!isNaN(sizeValue)) {
      if (sizeValue > 80) description.push(TEXT_STYLES_MAP['very large']);
      else if (sizeValue > 40) description.push(TEXT_STYLES_MAP['large']);
      else if (sizeValue > 20) description.push(TEXT_STYLES_MAP['medium']);
      else description.push(TEXT_STYLES_MAP['small']);
    }
  }

  if (cssProps.fontFamily) {
    description.push(`police ${cssProps.fontFamily.split(',')[0].replace(/"/g, '')}`);
  }

  return description.join(', ') || 'texte standard';
}

export default function EditableFlyer({ imageUrl, ocrResults = [], onSaveEdits, onCancelEdits }) {
  const [editableTextBlocks, setEditableTextBlocks] = useState([]);
  const imageRef = useRef(null);
  const containerRef = useRef(null);
  const [imageDimensions, setImageDimensions] = useState({ width: 800, height: 600 });

  const ocrStyleToCss = useCallback((ocrStyle = '') => {
    const defaultStyle = {
      fontSize: '24px',
      fontWeight: 'normal',
      fontStyle: 'normal',
      textDecoration: 'none',
      color: 'inherit',
      fontFamily: 'Verdana, sans-serif'
    };

    const lowerOcrStyle = ocrStyle.toLowerCase();
    const style = { ...defaultStyle };

    if (lowerOcrStyle.includes('very large') || lowerOcrStyle.includes('très grand')) {
      style.fontSize = '80px';
    } else if (lowerOcrStyle.includes('large') || lowerOcrStyle.includes('grand')) {
      style.fontSize = '48px';
    } else if (lowerOcrStyle.includes('medium') || lowerOcrStyle.includes('moyenne')) {
      style.fontSize = '24px';
    } else if (lowerOcrStyle.includes('small') || lowerOcrStyle.includes('petit')) {
      style.fontSize = '16px';
    }

    if (lowerOcrStyle.includes('bold') || lowerOcrStyle.includes('gras')) {
      style.fontWeight = 'bold';
    }

    if (lowerOcrStyle.includes('italic') || lowerOcrStyle.includes('italique')) {
      style.fontStyle = 'italic';
    }

    if (lowerOcrStyle.includes('underline') || lowerOcrStyle.includes('souligné')) {
      style.textDecoration = 'underline';
    }

    if (lowerOcrStyle.includes('gold') || lowerOcrStyle.includes('doré')) {
      style.color = '#FFD700';
    } else if (lowerOcrStyle.includes('white') || lowerOcrStyle.includes('blanc')) {
      style.color = 'white';
    } else if (lowerOcrStyle.includes('black') || lowerOcrStyle.includes('noir')) {
      style.color = 'black';
    } else if (lowerOcrStyle.includes('blue') || lowerOcrStyle.includes('bleu')) {
      style.color = 'blue';
    } else if (lowerOcrStyle.includes('red') || lowerOcrStyle.includes('rouge')) {
      style.color = 'red';
    }

    if (lowerOcrStyle.includes('serif')) {
      style.fontFamily = 'Georgia, serif';
    } else if (lowerOcrStyle.includes('sans-serif')) {
      style.fontFamily = 'Arial, sans-serif';
    }

    return style;
  }, []);

  useEffect(() => {
    const updateDimensions = () => {
      if (!imageRef.current || !containerRef.current) return;

      const img = imageRef.current;
      const container = containerRef.current;
      
      container.style.width = `${img.offsetWidth || 800}px`;
      container.style.height = `${img.offsetHeight || 600}px`;

      setImageDimensions({
        width: img.naturalWidth || 800,
        height: img.naturalHeight || 600
      });
    };

    const observer = new ResizeObserver(updateDimensions);
    if (imageRef.current) observer.observe(imageRef.current);
    updateDimensions();

    return () => {
      if (imageRef.current) observer.unobserve(imageRef.current);
    };
  }, [imageUrl]);

  useEffect(() => {
    if (!containerRef.current || !imageRef.current || !ocrResults?.length || !Draggable || !ResizableBox) {
      setEditableTextBlocks([]);
      return;
    }

    const containerWidth = containerRef.current.offsetWidth || 800;
    const containerHeight = containerRef.current.offsetHeight || 600;

    const initialBlocks = ocrResults.map((result, index) => {
      const visualStyle = result?.visual_style || '';
      const approxPosition = result?.approx_position || '';
      const textContent = result?.text_content || '';
      
      const cssStyle = ocrStyleToCss(visualStyle);
      
      let x = containerWidth * 0.1;
      let y = containerHeight * (0.1 + index * 0.15);

      const lowerApproxPosition = approxPosition.toLowerCase();
      
      if (lowerApproxPosition.includes('center') && lowerApproxPosition.includes('horizontal')) {
        x = containerWidth * 0.25;
      } else if (lowerApproxPosition.includes('right')) {
        x = containerWidth * 0.6;
      }
      
      if (lowerApproxPosition.includes('center') && lowerApproxPosition.includes('vertical')) {
        y = containerHeight * 0.4;
      } else if (lowerApproxPosition.includes('bottom')) {
        y = containerHeight * 0.8;
      }

      const fontSizeValue = parseFloat(cssStyle.fontSize) || 24;
      const initialFontSize = isNaN(fontSizeValue) ? 24 : fontSizeValue;
      
      const estimatedWidth = Math.min(
        containerWidth * 0.8,
        initialFontSize * (textContent.length || 10) * 0.6
      );
      const estimatedHeight = Math.max(initialFontSize * 1.5, 40);

      return {
        id: `text-block-${index}-${Date.now()}`,
        content: textContent,
        position: { x, y },
        size: { width: estimatedWidth, height: estimatedHeight },
        style: cssStyle,
        descriptionForAI: visualStyle,
        positionForAI: approxPosition,
        nodeRef: React.createRef() // Ajout de la référence pour Draggable
      };
    });

    setEditableTextBlocks(initialBlocks);
  }, [ocrResults, ocrStyleToCss]);

  const handleDrag = (e, ui, id) => {
    if (!id) return;
    
    setEditableTextBlocks(prevBlocks =>
      prevBlocks.map(block =>
        block.id === id
          ? { ...block, position: { x: ui.x, y: ui.y } }
          : block
      )
    );
  };

  const handleResize = (e, direction, ref, data, id) => {
    if (!id || !data) return;
    
    setEditableTextBlocks(prevBlocks =>
      prevBlocks.map(block =>
        block.id === id
          ? { ...block, size: { width: data.size.width, height: data.size.height } }
          : block
      )
    );
  };

  const handleContentChange = (e, id) => {
    if (!id) return;
    
    setEditableTextBlocks(prevBlocks =>
      prevBlocks.map(block =>
        block.id === id
          ? { ...block, content: e.target.innerHTML }
          : block
      )
    );
  };

  const saveEdits = () => {
    if (!onSaveEdits || !editableTextBlocks.length) return;
    onSaveEdits(editableTextBlocks);
  };

  if (!Draggable || !ResizableBox) {
    return (
      <div className="loading-container">
        <div className="loader small-loader"></div>
        <p>Chargement de l'éditeur visuel...</p>
      </div>
    );
  }

  return (
    <div className="editable-flyer-container" ref={containerRef}>
      <img
        src={imageUrl}
        alt="Flyer généré"
        className="editable-flyer-background"
        ref={imageRef}
        onError={(e) => {
          e.target.onerror = null;
          e.target.src = '/placeholder-flyer.jpg';
        }}
      />

      {editableTextBlocks.map(block => (
        <Draggable
          key={block.id}
          nodeRef={block.nodeRef}
          handle=".draggable-handle"
          defaultPosition={{ x: block.position.x, y: block.position.y }}
          position={block.position}
          onStop={(e, ui) => handleDrag(e, ui, block.id)}
          bounds="parent"
        >
          <div ref={block.nodeRef}>
            <ResizableBox
              width={block.size.width}
              height={block.size.height}
              minConstraints={[50, 20]}
              maxConstraints={[
                containerRef.current?.offsetWidth * 0.95 || Infinity,
                containerRef.current?.offsetHeight * 0.95 || Infinity
              ]}
              onResizeStop={(e, direction, ref, data) => handleResize(e, direction, ref, data, block.id)}
              resizeHandles={['se']}
              className="resizable-text-block-wrapper"
            >
              <div
                className="editable-text-block"
                contentEditable
                suppressContentEditableWarning={true}
                onBlur={(e) => handleContentChange(e, block.id)}
                style={{ 
                  ...block.style,
                  width: '100%',
                  height: '100%',
                  outline: 'none',
                  overflow: 'hidden',
                  textAlign: block.positionForAI?.includes('left') 
                    ? 'left' 
                    : block.positionForAI?.includes('right') 
                      ? 'right' 
                      : 'center'
                }}
                dangerouslySetInnerHTML={{ __html: block.content }}
              />
              <div className="draggable-handle"></div>
            </ResizableBox>
          </div>
        </Draggable>
      ))}

      <div className="editable-flyer-controls">
        <button 
          onClick={saveEdits} 
          className="save-edits-btn" 
          disabled={!editableTextBlocks.length}
        >
          Sauvegarder les modifications et régénérer
        </button>
        <button onClick={onCancelEdits} className="cancel-edits-btn">
          Annuler l'édition
        </button>
      </div>
    </div>
  );
}