export const templatesRegistry = [
  {
    id: 'baskets',
    name: 'Baskets',
    description: 'Тёплая палитра для хендмейда и домашних товаров.',
    cssVars: {
      bg: 'linear-gradient(180deg, #f9f4ec 0%, #f2e5d7 100%)',
      text: '#3b342b',
      muted: '#7a6f64',
      'card-bg': 'rgba(255, 255, 255, 0.9)',
      accent: '#d4a373',
      radius: '18px',
      shadow: '0 18px 50px rgba(93, 76, 50, 0.18)',
      font: '"Inter", system-ui, sans-serif',
    },
    stylePreset: {
      buttonStyle: 'pills',
      cardBorder: false,
    },
  },
  {
    id: 'electronics',
    name: 'Electronics',
    description: 'Сдержанный графитовый стиль для техники и гаджетов.',
    cssVars: {
      bg: 'linear-gradient(145deg, #0f172a 0%, #0b1323 60%, #0a0f1c 100%)',
      text: '#e5e7eb',
      muted: '#94a3b8',
      'card-bg': 'rgba(30, 41, 59, 0.9)',
      accent: '#60a5fa',
      radius: '12px',
      shadow: '0 18px 48px rgba(0, 0, 0, 0.38)',
      font: '"Inter", system-ui, sans-serif',
    },
    stylePreset: {
      buttonStyle: 'solid',
      cardBorder: true,
    },
  },
  {
    id: 'services',
    name: 'Services',
    description: 'Нейтральный светлый пресет для услуг и консультаций.',
    cssVars: {
      bg: '#f5f6fb',
      text: '#1f2937',
      muted: '#6b7280',
      'card-bg': '#ffffff',
      accent: '#2563eb',
      radius: '16px',
      shadow: '0 16px 40px rgba(15, 23, 42, 0.12)',
      font: '"Inter", system-ui, sans-serif',
    },
    stylePreset: {
      buttonStyle: 'solid',
      cardBorder: false,
    },
  },
];

export function getTemplateById(id) {
  return templatesRegistry.find((tpl) => tpl.id === id);
}
