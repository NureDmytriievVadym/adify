<script lang="ts">
  import { categories, demoListings } from '#lib/demo/marketplace.ts';
  import ListingCard from '#lib/components/ListingCard.svelte';
  import PreviewNotice from '#lib/components/PreviewNotice.svelte';
  import Icon from '#lib/components/Icon.svelte';
  import LiveListingCard from '#lib/components/LiveListingCard.svelte';
  import { fetchListings, type ListResult, type ListingType } from '#lib/listings/api.ts';

  const filters: { label: string; type?: ListingType }[] = [
    { label: 'All' },
    { label: 'Offers', type: 'offer' },
    { label: 'Ad requests', type: 'request' },
  ];

  let type: ListingType | undefined = $state();
  let live: ListResult | null = $state(null);

  $effect(() => {
    live = null;
    const current = type;
    fetchListings({ type: current }).then((result) => {
      if (type === current) live = result;
    });
  });
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
  <section aria-labelledby="live-title">
    <h2 id="live-title" class="account-title">Latest listings</h2>
    <div class="filter-bar" role="group" aria-label="Listing type">
      {#each filters as filter (filter.label)}
        <button
          class="button button-outline button-small"
          type="button"
          aria-pressed={type === filter.type}
          onclick={() => (type = filter.type)}>{filter.label}</button
        >
      {/each}
    </div>
    {#if !live}
      <p class="field-hint" role="status">Loading listings…</p>
    {:else if !live.ok}
      <p class="form-alert" role="alert">{live.message}</p>
    {:else if live.items.length === 0}
      <p class="field-hint">No listings yet. <a href="/listings/new">Publish the first one.</a></p>
    {:else}
      <div class="listing-grid marketplace-grid live-grid">
        {#each live.items as listing (listing.id)}<LiveListingCard {listing} />{/each}
      </div>
    {/if}
  </section>
  <h2 class="account-title sample-heading">Example listings</h2>
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
