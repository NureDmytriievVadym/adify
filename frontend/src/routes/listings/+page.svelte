<script lang="ts">
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { onDestroy, untrack } from 'svelte';
  import Icon from '#lib/components/Icon.svelte';
  import LiveListingCard from '#lib/components/LiveListingCard.svelte';
  import FilterSidebar from '#lib/components/FilterSidebar.svelte';
  import { fetchListings, type ListResult } from '#lib/listings/api.ts';
  import {
    SORT_OPTIONS,
    activeFilterCount,
    emptyFilters,
    filtersFromParams,
    hasFilterValue,
    paramsFromFilters,
    type ListingFilters,
  } from '#lib/listings/filters.ts';
  import { categoryName } from '#lib/listings/catalog.ts';

  const initial = untrack(() => filtersFromParams(page.url.searchParams));
  let filters = $state<ListingFilters>(initial);
  let live: ListResult | null = $state(null);
  let timer: ReturnType<typeof setTimeout> | undefined;
  let panel = $state(false);

  $effect(() => {
    const query = { ...filters, traits: [...filters.traits] };
    let active = true;
    live = null;
    fetchListings({
      search: query.q,
      type: query.type,
      category: query.category,
      priceMin: query.priceMin,
      priceMax: query.priceMax,
      deliveryMax: query.deliveryMax,
      ageMin: query.ageMin,
      ageMax: query.ageMax,
      country: query.country,
      socioeconomic: query.socioeconomic,
      traits: query.traits,
      ownerCompletedMin: query.ownerCompletedMin,
      ownerDisputedMax: query.ownerDisputedMax,
      sort: query.sort,
    }).then((result) => {
      if (active) live = result;
    });
    return () => {
      active = false;
    };
  });

  onDestroy(() => clearTimeout(timer));

  function sync(next: ListingFilters) {
    filters = next;
    const search = paramsFromFilters(next);
    goto(`${page.url.pathname}${search ? `?${search}` : ''}`, { replace: true, reset: false });
  }

  function applyFilters(next: ListingFilters) {
    sync(next);
    panel = false;
  }

  function update(patch: Partial<ListingFilters>) {
    sync({ ...filters, ...patch });
  }

  function searchLater() {
    clearTimeout(timer);
    timer = setTimeout(() => update({ q: filters.q.trim() }), 300);
  }

  function submit(event: SubmitEvent) {
    event.preventDefault();
    clearTimeout(timer);
    update({ q: filters.q.trim() });
  }

  function clearAll() {
    clearTimeout(timer);
    sync({ ...emptyFilters(), sort: filters.sort });
  }

  const filterCount = $derived(activeFilterCount(filters));
  const ownerCompletedLabel = $derived(
    hasFilterValue(filters.ownerCompletedMin)
      ? `Owner: ${filters.ownerCompletedMin}+ completed orders`
      : '',
  );
  const ownerDisputedLabel = $derived.by(() => {
    if (!hasFilterValue(filters.ownerDisputedMax)) return '';
    return String(filters.ownerDisputedMax) === '0'
      ? 'Owner: no disputed orders'
      : `Owner: up to ${filters.ownerDisputedMax} disputed orders`;
  });
  const resultLabel = $derived.by(() => {
    if (!live?.ok) return '';
    const noun = live.total === 1 ? 'listing' : 'listings';
    return filters.q ? `${live.total} ${noun} for “${filters.q}”` : `${live.total} ${noun}`;
  });
</script>

<svelte:head
  ><title>{filters.q ? `${filters.q} — Marketplace — Adify` : 'Marketplace — Adify'}</title><meta
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
        bind:value={filters.q}
        oninput={searchLater}
      />
      {#if filters.q}
        <button
          class="search-clear"
          type="button"
          aria-label="Clear search field"
          onclick={() => update({ q: '' })}><Icon name="close" size={16} /></button
        >
      {/if}
    </span>
    <button class="button button-dark" type="submit">Search</button>
  </form>

  <div class="marketplace-layout">
    <button
      class="button button-outline filter-toggle"
      type="button"
      aria-expanded={panel}
      aria-controls="listing-filters"
      onclick={() => (panel = !panel)}
    >
      <Icon name="menu" size={17} /> Filters{#if filterCount}<span class="filter-count"
          >{filterCount}</span
        >{/if}
    </button>

    <FilterSidebar {filters} open={panel} onapply={applyFilters} onclose={() => (panel = false)} />

    <section class="marketplace-results" aria-labelledby="results-title">
      <div class="results-heading">
        <h2 id="results-title" class="account-title">
          {filters.q ? 'Search results' : 'Latest listings'}
        </h2>
        <div class="results-tools">
          <p class="results-count" aria-live="polite">{resultLabel}</p>
          <label class="sort-control">
            <span>Sort</span>
            <select
              value={filters.sort}
              onchange={(event) =>
                update({
                  sort: (event.currentTarget as HTMLSelectElement).value as ListingFilters['sort'],
                })}
            >
              {#each SORT_OPTIONS as option (option.value)}
                <option value={option.value}>{option.label}</option>
              {/each}
            </select>
          </label>
        </div>
      </div>

      {#if filterCount}
        <div class="active-filters" aria-label="Active filters">
          {#if filters.type}<button
              type="button"
              class="filter-chip"
              onclick={() => update({ type: undefined })}
              >{filters.type === 'offer' ? 'Offers' : 'Ad requests'}
              <Icon name="close" size={13} /></button
            >{/if}
          {#if filters.category}<button
              type="button"
              class="filter-chip"
              onclick={() => update({ category: undefined })}
              >{categoryName(filters.category)} <Icon name="close" size={13} /></button
            >{/if}
          {#if filters.priceMin || filters.priceMax}<button
              type="button"
              class="filter-chip"
              onclick={() => update({ priceMin: '', priceMax: '' })}
              >{filters.priceMin || '0'}–{filters.priceMax || 'any'} UAH <Icon
                name="close"
                size={13}
              /></button
            >{/if}
          {#if filters.deliveryMax}<button
              type="button"
              class="filter-chip"
              onclick={() => update({ deliveryMax: '' })}
              >Up to {filters.deliveryMax} days <Icon name="close" size={13} /></button
            >{/if}
          {#if filters.ageMin || filters.ageMax}<button
              type="button"
              class="filter-chip"
              onclick={() => update({ ageMin: '', ageMax: '' })}
              >Age {filters.ageMin || '0'}–{filters.ageMax || 'any'}
              <Icon name="close" size={13} /></button
            >{/if}
          {#if filters.country}<button
              type="button"
              class="filter-chip"
              onclick={() => update({ country: '' })}
              >{filters.country} <Icon name="close" size={13} /></button
            >{/if}
          {#if filters.socioeconomic}<button
              type="button"
              class="filter-chip"
              onclick={() => update({ socioeconomic: '' })}
              >{filters.socioeconomic} <Icon name="close" size={13} /></button
            >{/if}
          {#if filters.traits.length}<button
              type="button"
              class="filter-chip"
              onclick={() => update({ traits: [] })}
              >{filters.traits.join(', ')} <Icon name="close" size={13} /></button
            >{/if}
          {#if ownerCompletedLabel}<button
              type="button"
              class="filter-chip"
              onclick={() => update({ ownerCompletedMin: '' })}
              >{ownerCompletedLabel} <Icon name="close" size={13} /></button
            >{/if}
          {#if ownerDisputedLabel}<button
              type="button"
              class="filter-chip"
              onclick={() => update({ ownerDisputedMax: '' })}
              >{ownerDisputedLabel} <Icon name="close" size={13} /></button
            >{/if}
          <button type="button" class="text-button" onclick={clearAll}>Clear all</button>
        </div>
      {/if}

      {#if !live}
        <p class="field-hint" role="status">Loading listings…</p>
      {:else if !live.ok}
        <p class="form-alert" role="alert">{live.message}</p>
      {:else if live.items.length === 0}
        <div class="empty-state listings-empty">
          <span class="empty-icon"><Icon name="search" size={30} /></span>
          {#if filterCount || filters.q}
            <h2>No listings match these filters.</h2>
            <p>Try widening the price range, delivery time, or audience.</p>
            <div class="empty-actions">
              {#if filterCount}
                <button class="button button-dark" type="button" onclick={clearAll}
                  >Clear all filters</button
                >
              {/if}
              {#if filters.q}
                <button class="text-link" type="button" onclick={() => update({ q: '' })}
                  >Clear search</button
                >
              {:else}
                <a class="text-link" href="/listings">Browse all listings</a>
              {/if}
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
</div>
