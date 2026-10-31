<script lang="ts">
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { onDestroy, untrack } from 'svelte';
  import Icon from '#lib/components/Icon.svelte';
  import LiveListingCard from '#lib/components/LiveListingCard.svelte';
  import { fetchListings, type ListResult, type ListingType } from '#lib/listings/api.ts';
  import { categories, categoryName } from '#lib/listings/catalog.ts';

  const filters: { label: string; type?: ListingType }[] = [
    { label: 'All' },
    { label: 'Offers', type: 'offer' },
    { label: 'Ad requests', type: 'request' },
  ];

  const initial = untrack(() => {
    const requested = page.url.searchParams.get('type');
    const requestedCategory = page.url.searchParams.get('category');
    return {
      type: (requested === 'offer' || requested === 'request' ? requested : undefined) as
        ListingType | undefined,
      category: categories.some((item) => item.id === requestedCategory)
        ? requestedCategory!
        : undefined,
      query: (page.url.searchParams.get('q') ?? '').slice(0, 100),
    };
  });
  let type: ListingType | undefined = $state(initial.type);
  let category = $state<string | undefined>(initial.category);
  let query = $state(initial.query);
  let applied = $state(initial.query.trim());
  let live: ListResult | null = $state(null);
  let timer: ReturnType<typeof setTimeout> | undefined;

  $effect(() => {
    const current = { type, category, search: applied };
    let active = true;
    live = null;
    fetchListings(current).then((result) => {
      if (active) live = result;
    });
    return () => {
      active = false;
    };
  });

  onDestroy(() => clearTimeout(timer));

  function apply(value: string) {
    applied = value.trim().slice(0, 100);
    query = value.slice(0, 100);
    const params: Record<string, string> = Object.fromEntries(page.url.searchParams);
    for (const [key, item] of [
      ['q', applied],
      ['type', type],
      ['category', category],
    ] as const) {
      if (item) params[key] = item;
      else delete params[key];
    }
    const search = Object.entries(params)
      .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
      .join('&');
    goto(`${page.url.pathname}${search ? `?${search}` : ''}`, {
      replace: true,
      reset: false,
    });
  }

  function searchLater() {
    clearTimeout(timer);
    timer = setTimeout(() => apply(query), 300);
  }

  function submit(event: SubmitEvent) {
    event.preventDefault();
    clearTimeout(timer);
    apply(query);
  }

  function clearSearch() {
    clearTimeout(timer);
    apply('');
  }

  function chooseType(next?: ListingType) {
    type = next;
    apply(query);
  }

  function clearCategory() {
    category = undefined;
    apply(query);
  }

  const resultLabel = $derived.by(() => {
    if (!live?.ok) return '';
    if (!applied) return `${live.total} ${live.total === 1 ? 'listing' : 'listings'}`;
    return `${live.total} ${live.total === 1 ? 'result' : 'results'} for “${applied}”`;
  });
</script>

<svelte:head
  ><title>{applied ? `${applied} — Marketplace — Adify` : 'Marketplace — Adify'}</title><meta
    name="description"
    content="Browse and search internet advertising offers and requests on Adify: website banners, sponsored articles, social media, video, stream, and in-app advertising."
  /></svelte:head
>

<div class="container page-content">
  <div class="page-intro">
    <span class="eyebrow">THE MARKETPLACE</span>
    <h1>A space for your<br /><span>next big idea.</span></h1>
    <p>
      Browse advertising offers and requests from across the Adify marketplace. Guests can browse
      and search every public listing without signing in.
    </p>
  </div>

  <form class="search-bar" role="search" action="/listings" method="GET" onsubmit={submit}>
    <label class="visually-hidden" for="listing-search">Search listings</label>
    <span class="search-field">
      <Icon name="search" size={19} />
      <input
        id="listing-search"
        name="q"
        type="search"
        maxlength="100"
        autocomplete="off"
        placeholder="Try “banner”, “article”, or “video”"
        bind:value={query}
        oninput={searchLater}
      />
      {#if query}
        <button
          class="search-clear"
          type="button"
          aria-label="Clear search field"
          onclick={clearSearch}><Icon name="close" size={16} /></button
        >
      {/if}
    </span>
    <button class="button button-dark" type="submit">Search</button>
    {#if type}<input type="hidden" name="type" value={type} />{/if}
    {#if category}<input type="hidden" name="category" value={category} />{/if}
  </form>

  {#if category}
    <p class="active-filter">
      Category: <strong>{categoryName(category)}</strong>
      <button class="text-link" type="button" onclick={clearCategory}>Clear category</button>
    </p>
  {/if}

  <div class="filter-bar" role="group" aria-label="Listing type">
    {#each filters as filter (filter.label)}
      <button
        class="button button-outline button-small"
        type="button"
        aria-pressed={type === filter.type}
        onclick={() => chooseType(filter.type)}>{filter.label}</button
      >
    {/each}
  </div>

  <section aria-labelledby="results-title">
    <div class="results-heading">
      <h2 id="results-title" class="account-title">
        {applied ? 'Search results' : 'Latest listings'}
      </h2>
      <p class="results-count" aria-live="polite">{resultLabel}</p>
    </div>

    {#if !live}
      <p class="field-hint" role="status">Loading listings…</p>
    {:else if !live.ok}
      <p class="form-alert" role="alert">{live.message}</p>
    {:else if live.items.length === 0}
      <div class="empty-state listings-empty">
        <span class="empty-icon"><Icon name="search" size={30} /></span>
        {#if applied}
          <h2>No listings match “{applied}”.</h2>
          <p>Try a different word, or browse everything currently on the marketplace.</p>
          <div class="empty-actions">
            <button class="button button-dark" type="button" onclick={clearSearch}
              >Clear search</button
            >
            <a class="text-link" href="/listings">Browse all listings</a>
          </div>
        {:else}
          <h2>No listings yet.</h2>
          <p>Be the first to publish an advertising offer or request.</p>
          <a class="button button-dark" href="/listings/new"
            >Create a listing <Icon name="arrow" /></a
          >
        {/if}
      </div>
    {:else}
      <div class="listing-grid marketplace-grid">
        {#each live.items as listing (listing.id)}<LiveListingCard {listing} />{/each}
      </div>
    {/if}
  </section>
</div>
