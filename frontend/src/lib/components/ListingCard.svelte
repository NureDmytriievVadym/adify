<script lang="ts">
  import { getCategory, formatUah, type DemoListing } from '#lib/demo/marketplace.ts';
  import Icon from './Icon.svelte';
  import ListingArtwork from './ListingArtwork.svelte';
  let { listing }: { listing: DemoListing } = $props();
</script>

<article class="listing-card">
  <a href={`/listings/${listing.slug}`} class="card-art-link" tabindex="-1" aria-hidden="true"
    ><ListingArtwork category={listing.categoryId} /></a
  >
  <div class="card-content">
    <div class="card-category">
      <span>{getCategory(listing.categoryId).name}</span><span
        class:request={listing.type === 'request'}
        class="type-badge">{listing.type === 'offer' ? 'Offer' : 'Ad request'}</span
      >
    </div>
    <h3><a href={`/listings/${listing.slug}`}>{listing.title}</a></h3>
    <div class="card-owner">
      <span class="avatar">{listing.initials}</span><span>{listing.owner}</span><span
        class="sample-label">Sample</span
      >
    </div>
    <div class="card-bottom">
      <span
        ><span class="price-prefix">{listing.type === 'request' ? 'Budget' : 'Price'}</span><strong
          >{formatUah(listing.price)}</strong
        ></span
      ><span class="card-arrow"><Icon name="arrow" size={18} /></span>
    </div>
  </div>
</article>
