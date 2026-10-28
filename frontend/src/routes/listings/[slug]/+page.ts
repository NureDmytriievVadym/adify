import { error } from '@sveltejs/kit';
import { demoListings } from '#lib/demo/marketplace.ts';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ params }) => {
  const listing = demoListings.find((item) => item.slug === params.slug);
  if (!listing) error(404, 'This listing could not be found.');
  return { listing };
};
