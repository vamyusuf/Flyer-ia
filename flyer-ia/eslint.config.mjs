import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

// Étendre la configuration par défaut de Next.js
const eslintConfig = [...compat.extends("next/core-web-vitals")];

// Ajouter une nouvelle configuration pour surcharger les règles
// Placez-le APRÈS les configurations étendues pour qu'il puisse les surcharger
eslintConfig.push({
  files: ["**/*.{js,mjs,cjs,ts,jsx,tsx}"], // Appliquer à tous les fichiers JS/TS/JSX/TSX
  rules: {
    // Désactiver la règle pour les entités non échappées
    "react/no-unescaped-entities": "off",
    // Vous pouvez ajouter d'autres règles personnalisées ici si besoin
  }
});

export default eslintConfig;








// import { dirname } from "path";
// import { fileURLToPath } from "url";
// import { FlatCompat } from "@eslint/eslintrc";

// const __filename = fileURLToPath(import.meta.url);
// const __dirname = dirname(__filename);

// const compat = new FlatCompat({
//   baseDirectory: __dirname,
// });

// const eslintConfig = [...compat.extends("next/core-web-vitals")];

// export default eslintConfig;
