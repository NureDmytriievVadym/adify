<script lang="ts">
  import Icon from '#lib/components/Icon.svelte';
  import LiveListingCard from '#lib/components/LiveListingCard.svelte';
  import { session } from '#lib/accounts/session.svelte.ts';
  import { fetchListings, type ListResult } from '#lib/listings/api.ts';

  let result: ListResult | null = $state(null);

  $effect(() => {
    if (!session.account) return;
    result = null;
    fetchListings({ mine: true }).then((next) => (result = next));
  });
</script>

<svelte:head><title>My listings — Adify</title></svelte:head>

<div class="container page-content">
  <div class="page-intro">
    <span class="eyebrow">YOUR LISTINGS</span>
    <h1>My <span>listings.</span></h1>
    <p>Everything you have published. Other users can open each one from the marketplace.</p>
  </div>

  {#if !session.account && session.restored}
    <p class="field-hint">Sign in to see your listings.</p>
    <a class="button button-dark" href="/sign-in">Sign in <Icon name="arrow" /></a>
  {:else if !session.account || !result}
    <p class="field-hint" role="status">Loading your listings…</p>
  {:else if !result.ok}
    <p class="form-alert" role="alert">{result.message}</p>
  {:else if result.items.length === 0}
    <p class="field-hint">You have not published anything yet.</p>
    <a class="button button-dark" href="/listings/new">Create a listing <Icon name="arrow" /></a>
  {:else}
    <div class="listing-grid marketplace-grid">
      {#each result.items as listing (listing.id)}<LiveListingCard {listing} />{/each}
    </div>
  {/if}
</div>
