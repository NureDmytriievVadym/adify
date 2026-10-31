<script lang="ts">
  import { getCategory, formatUah } from '#lib/demo/marketplace.ts';
  import type { ApiListing } from '#lib/listings/api.ts';
  import Icon from './Icon.svelte';
  import ListingArtwork from './ListingArtwork.svelte';
  let { listing }: { listing: ApiListing } = $props();

  const initials = $derived(
    listing.owner.display_name
      .split(/\s+/)
      .map((word) => word[0])
      .join('')
      .slice(0, 2)
      .toUpperCase(),
  );
</script>

<article class="listing-card live-listing">
  <a href={`/listings/${listing.id}`} class="card-art-link" tabindex="-1" aria-hidden="true"
    ><ListingArtwork category={listing.category} /></a
  >
  <div class="card-content">
    <div class="card-category">
      <span>{getCategory(listing.category).name}</span><span
        class:request={listing.type === 'request'}
        class="type-badge">{listing.type === 'offer' ? 'Offer' : 'Ad request'}</span
      >
    </div>
    <h3><a href={`/listings/${listing.id}`}>{listing.title}</a></h3>
    <div class="card-owner">
      <span class="avatar">{initials}</span><span>{listing.owner.display_name}</span>
    </div>
    <div class="card-bottom">
      <span
        ><span class="price-prefix">{listing.type === 'request' ? 'Budget' : 'Price'}</span><strong
          >{formatUah(Number(listing.price_uah))}</strong
        ></span
      ><span class="card-arrow"><Icon name="arrow" size={18} /></span>
    </div>
  </div>
</article>
