<script lang="ts">
  import { untrack } from 'svelte';
  import Icon from '#lib/components/Icon.svelte';
  import { categories } from '#lib/listings/catalog.ts';
  import {
    activeFilterCount,
    emptyFilters,
    validateFilters,
    type ListingFilters,
  } from '#lib/listings/filters.ts';

  let {
    filters,
    open = false,
    onapply,
    onclose,
  }: {
    filters: ListingFilters;
    open?: boolean;
    onapply: (next: ListingFilters) => void;
    onclose?: () => void;
  } = $props();

  const clone = (source: ListingFilters): ListingFilters => ({
    ...source,
    traits: [...source.traits],
  });

  const current = $derived(clone(filters));
  let draft = $state<ListingFilters>(untrack(() => clone(filters)));
  let traitsText = $state(untrack(() => filters.traits.join(', ')));
  let error = $state('');

  // Re-sync when the URL changes from the search box, a chip, or browser history.
  $effect(() => {
    void current;
    draft = clone(filters);
    traitsText = filters.traits.join(', ');
    error = '';
  });

  const draftTraits = $derived(
    traitsText
      .split(',')
      .map((trait) => trait.trim())
      .filter(Boolean),
  );
  const count = $derived(activeFilterCount({ ...draft, traits: draftTraits }));

  function apply(event?: SubmitEvent) {
    event?.preventDefault();
    error = validateFilters(draft) ?? '';
    if (error) return;
    const traits = traitsText
      .split(',')
      .map((trait) => trait.trim().slice(0, 50))
      .filter(Boolean)
      .slice(0, 20);
    onapply({ ...draft, traits });
  }

  function reset() {
    const cleared = emptyFilters();
    cleared.q = draft.q;
    draft = cleared;
    traitsText = '';
    error = '';
    onapply(cleared);
  }
</script>

<aside id="listing-filters" class:open class="filter-sidebar" aria-labelledby="filters-title">
  <form onsubmit={apply}>
    <div class="filter-head">
      <h2 id="filters-title">
        Filters {#if count}<span class="filter-count">{count}</span>{/if}
      </h2>
      <button
        class="filter-close"
        type="button"
        aria-label="Close filters"
        onclick={() => onclose?.()}><Icon name="close" size={18} /></button
      >
    </div>

    {#if error}
      <p class="field-error" role="alert">{error}</p>
    {/if}

    <fieldset class="filter-group">
      <legend>Listing type</legend>
      {#each [{ label: 'All listings', value: undefined }, { label: 'Offers', value: 'offer' }, { label: 'Ad requests', value: 'request' }] as option (option.label)}
        <label class="filter-radio">
          <input
            type="radio"
            name="filter-type"
            checked={draft.type === option.value}
            onchange={() => (draft.type = option.value as ListingFilters['type'])}
          />
          <span>{option.label}</span>
        </label>
      {/each}
    </fieldset>

    <div class="filter-group">
      <label for="filter-category">Category</label>
      <select id="filter-category" bind:value={draft.category}>
        <option value={undefined}>All categories</option>
        {#each categories as category (category.id)}
          <option value={category.id}>{category.name}</option>
        {/each}
      </select>
    </div>

    <fieldset class="filter-group">
      <legend>Price or budget (UAH)</legend>
      <div class="filter-pair">
        <div>
          <label for="filter-price-min">From</label>
          <input
            id="filter-price-min"
            type="number"
            min="0"
            step="1"
            placeholder="1 000"
            bind:value={draft.priceMin}
          />
        </div>
        <div>
          <label for="filter-price-max">To</label>
          <input
            id="filter-price-max"
            type="number"
            min="0"
            step="1"
            placeholder="5 000"
            bind:value={draft.priceMax}
          />
        </div>
      </div>
    </fieldset>

    <div class="filter-group">
      <label for="filter-delivery">Delivery time</label>
      <select id="filter-delivery" bind:value={draft.deliveryMax}>
        <option value="">Any delivery time</option>
        <option value="1">Up to 1 day</option>
        <option value="3">Up to 3 days</option>
        <option value="7">Up to 7 days</option>
        <option value="14">Up to 14 days</option>
        <option value="30">Up to 30 days</option>
      </select>
    </div>

    <fieldset class="filter-group">
      <legend>Target audience</legend>
      <div class="filter-pair">
        <div>
          <label for="filter-age-min">Age from</label>
          <input
            id="filter-age-min"
            type="number"
            min="0"
            max="120"
            placeholder="18"
            bind:value={draft.ageMin}
          />
        </div>
        <div>
          <label for="filter-age-max">Age to</label>
          <input
            id="filter-age-max"
            type="number"
            min="0"
            max="120"
            placeholder="34"
            bind:value={draft.ageMax}
          />
        </div>
      </div>

      <label for="filter-country">Country</label>
      <input
        id="filter-country"
        type="text"
        maxlength="100"
        placeholder="Ukraine"
        bind:value={draft.country}
      />

      <label for="filter-socioeconomic">Socioeconomic background</label>
      <input
        id="filter-socioeconomic"
        type="text"
        maxlength="100"
        placeholder="Middle income"
        bind:value={draft.socioeconomic}
      />

      <label for="filter-traits">Traits</label>
      <input
        id="filter-traits"
        type="text"
        maxlength="300"
        placeholder="Gamers, students"
        bind:value={traitsText}
        aria-describedby="filter-traits-hint"
      />
      <p class="field-hint" id="filter-traits-hint">Separate traits with commas.</p>
    </fieldset>

    <fieldset class="filter-group">
      <legend>Owner track record</legend>
      <div class="filter-pair">
        <div>
          <label for="filter-owner-completed-min">Completed orders (at least)</label>
          <input
            id="filter-owner-completed-min"
            type="number"
            min="0"
            max="100000"
            step="1"
            placeholder="Any"
            bind:value={draft.ownerCompletedMin}
            aria-describedby="filter-owner-hint"
          />
        </div>
        <div>
          <label for="filter-owner-disputed-max">Disputed orders (at most)</label>
          <input
            id="filter-owner-disputed-max"
            type="number"
            min="0"
            max="100000"
            step="1"
            placeholder="Any"
            bind:value={draft.ownerDisputedMax}
            aria-describedby="filter-owner-hint"
          />
        </div>
      </div>
      <p class="field-hint" id="filter-owner-hint">
        Completed orders reached done; disputed orders are currently in dispute.
      </p>
    </fieldset>

    <div class="filter-actions">
      <button class="button button-dark" type="submit">Apply filters</button>
      <button class="text-button" type="button" onclick={reset}>Clear all</button>
    </div>
  </form>
</aside>
