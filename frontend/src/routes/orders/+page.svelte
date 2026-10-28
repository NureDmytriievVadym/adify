<script lang="ts">
  import Icon from '#lib/components/Icon.svelte';
  import PreviewNotice from '#lib/components/PreviewNotice.svelte';
</script>

<svelte:head
  ><title>Orders preview — Adify</title><meta
    name="description"
    content="A preview of the space where Adify customers and providers will manage their advertising orders."
  /></svelte:head
>

<div class="container page-content">
  <div class="page-intro">
    <span class="eyebrow">FROM AN IDEA TO A PLACEMENT</span>
    <h1>A shared space<br /><span>for the work ahead.</span></h1>
    <p>Your advertising orders will live here.</p>
  </div>
  <PreviewNotice />
  <section class="empty-state" aria-labelledby="orders-preview-title">
    <span class="empty-icon"><Icon name="article" size={36} /></span><span class="eyebrow"
      >ORDERS PREVIEW</span
    >
    <h2 id="orders-preview-title">Every great collaboration<br />needs a place to start.</h2>
    <p>
      This is a preview of the order area. Take a look at a sample order to see the layout for
      requirements, stages, and agreed details.
    </p>
    <a href="/orders/demo" class="button button-dark"
      >Explore a sample order <Icon name="arrow" size={18} /></a
    ><a href="/listings" class="text-link">Back to the marketplace</a>
  </section>
</div>
