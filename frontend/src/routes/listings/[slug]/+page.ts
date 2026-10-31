import { error } from '@sveltejs/kit';
import { demoListings } from '#lib/demo/marketplace.ts';
import { isListingId } from '#lib/listings/api.ts';
import type { PageLoad } from './$types';

// Example listings are fixtures; real ones (UUIDs) are loaded by the page from the API in the browser.
export const load: PageLoad = ({ params }) => {
  const demo = demoListings.find((item) => item.slug === params.slug) ?? null;
  if (!demo && !isListingId(params.slug)) error(404, 'This listing could not be found.');
  return { demo, listingId: demo ? null : params.slug };
};
