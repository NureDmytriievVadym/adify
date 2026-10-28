<script lang="ts">
  import { page } from '$app/state';
  import Icon from '#lib/components/Icon.svelte';
</script>

<svelte:head><title>{page.status} — Adify</title></svelte:head>
<div class="container error-page">
  <span class="eyebrow">{page.status}</span>
  <h1>{page.status === 404 ? 'A little off the path.' : 'Something went wrong.'}</h1>
  <p>
    {page.status === 404
      ? 'We could not find that page. Your next connection might be in the marketplace.'
      : 'Please try again in a moment.'}
  </p>
  <a class="button button-dark" href="/listings"
    >Explore the marketplace <Icon name="arrow" size={18} /></a
  >
</div>
