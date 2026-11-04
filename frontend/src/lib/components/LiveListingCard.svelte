<script lang="ts">
  import { categoryName, formatUah } from '#lib/listings/catalog.ts';
  import type { ApiListing } from '#lib/listings/api.ts';
  import Icon from './Icon.svelte';
  import ListingArtwork from './ListingArtwork.svelte';
  let { listing, editable = false }: { listing: ApiListing; editable?: boolean } = $props();

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
      <span>{categoryName(listing.category)}</span>
      <span class="card-badges"
        >{#if listing.status === 'paused' || listing.status === 'expired'}<span
            class="listing-state"
            class:expired={listing.status === 'expired'}
            >{listing.status === 'paused' ? 'Paused' : 'Expired'}</span
          >{/if}<span class:request={listing.type === 'request'} class="type-badge"
          >{listing.type === 'offer' ? 'Offer' : 'Ad request'}</span
        ></span
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
    {#if editable}
      <a class="text-link card-edit" href={`/listings/${listing.id}/edit`}
        >Edit<span class="visually-hidden"> {listing.title}</span></a
      >
    {/if}
  </div>
</article>
