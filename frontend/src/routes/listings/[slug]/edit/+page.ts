import { error } from '@sveltejs/kit';
import { isListingId } from '#lib/listings/api.ts';
import type { PageLoad } from './$types';

// Only live listings (UUIDs) can be edited; the sample listings are read-only fixtures.
export const load: PageLoad = ({ params }) => {
  if (!isListingId(params.slug)) error(404, 'This listing could not be found.');
  return { listingId: params.slug };
};
