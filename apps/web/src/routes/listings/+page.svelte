<script lang="ts">
  import { categories, demoListings } from '#lib/demo/marketplace.ts';
  import ListingCard from '#lib/components/ListingCard.svelte';
  import PreviewNotice from '#lib/components/PreviewNotice.svelte';
  import Icon from '#lib/components/Icon.svelte';
</script>

<svelte:head
  ><title>Marketplace — Adify</title><meta
    name="description"
    content="Explore the Adify marketplace preview: advertising offers and requests across six internet advertising categories."
  /></svelte:head
>

<div class="container page-content">
  <div class="page-intro">
    <span class="eyebrow">THE MARKETPLACE</span>
    <h1>A space for your<br /><span>next big idea.</span></h1>
    <p>
      From a thoughtful post to a new video collaboration.<br class="desktop-break" /> Discover what your
      next advertising partnership could look like.
    </p>
  </div>
  <PreviewNotice />
  <div class="marketplace-toolbar">
    <div><Icon name="search" /><span>Search and filters are coming soon</span></div>
    <span>6 sample listings · Offers & requests</span>
  </div>
  <div class="listing-grid marketplace-grid">
    {#each demoListings as listing (listing.slug)}<div
        id={listing.categoryId}
        class="listing-anchor"
      >
        <ListingCard {listing} />
      </div>{/each}
  </div>
  <aside class="category-directory">
    <h2>Six ways to get your brand out there.</h2>
    <div class="category-description-grid">
      {#each categories as category (category.id)}<a href={`#${category.id}`}
          ><Icon name={category.icon} size={22} />
          <div>
            <h3>{category.name}</h3>
            <p>{category.description}</p>
          </div></a
        >{/each}
    </div>
  </aside>
</div>
