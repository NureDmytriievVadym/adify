import type { IconName } from '#lib/components/Icon.svelte';

// Presentation fixtures, not an API contract. Replace in the listing stories.
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

export type DemoListing = {
  slug: string;
  categoryId: string;
  type: 'offer' | 'request';
  title: string;
  owner: string;
  initials: string;
  price: number;
  delivery: string;
  description: string;
  placement: { label: string; value: string }[];
};

export const demoListings: DemoListing[] = [
  {
    slug: 'everyday-social',
    categoryId: 'social-media-posts',
    type: 'offer',
    title: 'An Instagram post for brands with a little more soul',
    owner: 'Sofiia K.',
    initials: 'SK',
    price: 2400,
    delivery: '3 days',
    description:
      'A thoughtfully styled Instagram post for a lifestyle, home, or independent brand. We agree on the concept and publication date before work begins. This example shows how an advertising offer will be presented on Adify.',
    placement: [
      { label: 'Image formats', value: 'JPG or PNG, up to 8 MB' },
      { label: 'Aspect ratios', value: '1:1, 4:5, or 9:16' },
      { label: 'Video alternative', value: 'MP4 (H.264), up to 60 seconds and 100 MB' },
      { label: 'Caption', value: 'Up to 2,200 characters; emoji allowed' },
      { label: 'Hashtags', value: 'Up to 30' },
    ],
  },
  {
    slug: 'digital-daily',
    categoryId: 'website-banners',
    type: 'offer',
    title: 'Your brand, front and center on a design journal',
    owner: 'Digital Daily',
    initials: 'DD',
    price: 3500,
    delivery: '5 days',
    description:
      'A display banner placement on an independent design journal. Use the placement to introduce your brand alongside articles about design and creative work. Publication timing and the scope of the placement are agreed in chat.',
    placement: [
      { label: 'File formats', value: 'JPG, PNG, or GIF' },
      { label: 'Dimensions', value: '300 × 250 px or 728 × 90 px' },
      { label: 'Maximum file size', value: '150 KB' },
      { label: 'Animation', value: 'Up to 15 seconds' },
      { label: 'Alt text', value: 'Up to 100 characters; no emoji' },
    ],
  },
  {
    slug: 'creator-stories',
    categoryId: 'video-integrations',
    type: 'offer',
    title: 'A natural YouTube integration, made for your brand',
    owner: 'Maksym R.',
    initials: 'MR',
    price: 6000,
    delivery: '7 days',
    description:
      'A scripted brand integration within a YouTube video. The concept, script, and schedule are agreed before the project begins. The example is presentation content and is not an available service.',
    placement: [
      { label: 'Script', value: 'Up to 3,000 characters' },
      { label: 'Integration length', value: '30–120 seconds' },
      { label: 'Reference video', value: 'Optional MP4 (H.264), up to 500 MB' },
    ],
  },
  {
    slug: 'a-story-worth-sharing',
    categoryId: 'sponsored-articles',
    type: 'request',
    title: 'Looking for a home for our sustainable living story',
    owner: 'Olena M.',
    initials: 'OM',
    price: 4500,
    delivery: 'To be agreed',
    description:
      'We are looking for a website to publish a sponsored article about a small sustainable homeware brand. We would like to discuss the editorial approach and publication schedule. No strict technical requirements have been specified for this example request.',
    placement: [],
  },
  {
    slug: 'live-with-your-brand',
    categoryId: 'stream-ads',
    type: 'offer',
    title: 'Bring your brand into the live conversation',
    owner: 'Danylo P.',
    initials: 'DP',
    price: 1800,
    delivery: '4 days',
    description:
      'A stream overlay and spoken brand mention during a live broadcast. The placement and timing are agreed before the campaign. This is a sample listing for the website preview.',
    placement: [
      { label: 'Overlay', value: 'PNG, 1920 × 1080 or 728 × 90 px' },
      { label: 'Maximum file size', value: '1 MB' },
      { label: 'Spoken mention', value: 'Up to 500 characters' },
      { label: 'Duration', value: '15, 30, or 60 seconds' },
    ],
  },
  {
    slug: 'small-screen-big-ideas',
    categoryId: 'in-app-mobile-ads',
    type: 'offer',
    title: 'A little screen space for your next big idea',
    owner: 'Pocket Studio',
    initials: 'PS',
    price: 2800,
    delivery: '5 days',
    description:
      'An in-app advertising placement with banner, interstitial, or short video options. Agree on the placement type and campaign schedule with the provider before starting work. Sample content only.',
    placement: [
      { label: 'Banner', value: '320 × 50 or 300 × 250 px; up to 150 KB' },
      { label: 'Interstitial', value: '1080 × 1920 px; up to 1 MB' },
      { label: 'Video', value: 'MP4 (H.264), up to 30 seconds and 10 MB' },
    ],
  },
];

export const getCategory = (id: string) => categories.find((category) => category.id === id)!;
export const formatUah = (amount: number) =>
  `${new Intl.NumberFormat('en-US', { minimumFractionDigits: Number.isInteger(amount) ? 0 : 2 }).format(amount)} UAH`;
