import type { IconName } from '#lib/components/Icon.svelte';

// FR-014: the six internet advertising categories. Presentation metadata only.
export const categories: {
  id: string;
  name: string;
  short: string;
  icon: IconName;
  description: string;
}[] = [
  {
    id: 'website-banners',
    name: 'Website banners',
    short: 'Website banners',
    icon: 'globe',
    description: 'A place on the pages your customers visit.',
  },
  {
    id: 'sponsored-articles',
    name: 'Sponsored articles',
    short: 'Sponsored articles',
    icon: 'article',
    description: 'Give your story room to be read.',
  },
  {
    id: 'social-media-posts',
    name: 'Social media posts',
    short: 'Social media',
    icon: 'social',
    description: 'Join the conversations that matter.',
  },
  {
    id: 'video-integrations',
    name: 'Video integrations',
    short: 'Video integrations',
    icon: 'video',
    description: 'Put your brand in the next great watch.',
  },
  {
    id: 'stream-ads',
    name: 'Stream ads',
    short: 'Stream ads',
    icon: 'stream',
    description: 'Be part of the live moment.',
  },
  {
    id: 'in-app-mobile-ads',
    name: 'In-app mobile ads',
    short: 'In-app mobile ads',
    icon: 'mobile',
    description: 'Meet people in their everyday apps.',
  },
];

export const categoryName = (id: string) => categories.find((item) => item.id === id)?.name ?? id;

export const formatUah = (amount: number) =>
  `${new Intl.NumberFormat('en-US', { minimumFractionDigits: Number.isInteger(amount) ? 0 : 2 }).format(amount)} UAH`;
